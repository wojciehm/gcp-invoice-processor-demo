# ---------------------------------------------------------------------------
# OPEN-SOURCE ENSEMBLE ORCHESTRATOR
# ---------------------------------------------------------------------------
# This file is a FastAPI application running on Google Cloud Run.
# It acts as the "manager" (orchestrator) for our Open-Source LLMs.
# 
# How it works:
# 1. It receives a notification from Eventarc that a new PDF was uploaded.
# 2. It downloads the PDF and uses PyMuPDF (fitz) to extract the text.
# 3. It sends this extracted text to three separate LLMs (Gemma, Qwen, Mistral) 
#    at the exact same time (in parallel).
# 4. It waits for all three models to reply, and then performs a "majority vote"
#    to decide which answer is the most accurate.
# 5. Finally, it saves the consensus result to a Google Cloud Storage bucket.
# ---------------------------------------------------------------------------

import asyncio
import json
import time
import os
from fastapi import FastAPI, BackgroundTasks, Request
from google.cloud import storage
import uvicorn
import fitz
import httpx
import google.auth
import google.auth.transport.requests
import google.oauth2.id_token

app = FastAPI()

PROJECT_ID = os.environ.get('PROJECT_ID')
BUCKET_PREFIX = os.environ.get('BUCKET_PREFIX')

SOURCE_BUCKET = f"{BUCKET_PREFIX}-raw-invoices"
DEST_BUCKET = f"{BUCKET_PREFIX}-os-processed-results"

# ---------------------------------------------------------------------------
# URLs for the three separate Cloud Run services hosting the open-source models
# ---------------------------------------------------------------------------
MODEL_URLS = {
    "gemma4-12b": os.environ.get("GEMMA_URL"),
    "qwen3-6-27b": os.environ.get("QWEN_URL"),
    "mistral-7b": os.environ.get("MISTRAL_URL")
}

# The specific internal names (tags) Ollama uses to identify the models
MODEL_TAGS = {
    "gemma4-12b": "gemma4:12b",
    "qwen3-6-27b": "qwen3.6:27b",
    "mistral-7b": "mistral:7b"
}

# ---------------------------------------------------------------------------
# HELPER: Extracts text strings out of a binary PDF file.
# Note: Because open-source models are "text-only", we MUST do this step.
# ---------------------------------------------------------------------------
def extract_text_from_pdf(file_data: bytes) -> str:
    try:
        doc = fitz.open(stream=file_data, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""

# ---------------------------------------------------------------------------
# HELPER: Generates a secure identity token so this service is allowed to
# talk to the deeply secured model endpoints.
# ---------------------------------------------------------------------------
async def get_oidc_token(audience: str) -> str:
    loop = asyncio.get_running_loop()
    def fetch():
        import urllib.request
        url = f"http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience={audience}"
        req = urllib.request.Request(url, headers={"Metadata-Flavor": "Google"})
        try:
            response = urllib.request.urlopen(req, timeout=5)
            return response.read().decode('utf-8')
        except Exception as e:
            print(f"Failed to fetch OIDC token for {audience} via metadata server: {e}")
            return None
    return await loop.run_in_executor(None, fetch)

# ---------------------------------------------------------------------------
# HELPER: Sends the text to a specific AI model and asks it to extract data.
# ---------------------------------------------------------------------------
async def call_model(model_key: str, pdf_text: str):
    target_url = MODEL_URLS.get(model_key)
    if not target_url:
        print(f"URL not configured for {model_key}")
        return {}
        
    model_tag = MODEL_TAGS.get(model_key)

    try:
        # Get secure auth token
        token = await get_oidc_token(target_url)
        headers = {"Content-Type": "application/json"}
        if token:
            print(f"Successfully generated token for {model_key} (length: {len(token)})")
            headers["Authorization"] = f"Bearer {token}"
        else:
            print(f"Warning: No token generated for {model_key}")
            
        # Give the AI its instructions (the "prompt")
        prompt = f"""Extract the following details from this invoice text:
        - invoice_id (string)
        - total (integer)
        - tax (number)
        - issuer (string)
        
        Return ONLY valid JSON matching this structure.
        
        Invoice Text:
        {pdf_text}
        """
        
        payload = {
            "model": model_tag,
            "prompt": prompt,
            "format": "json",
            "stream": False
        }
        
        # Make an HTTP request to the LLM
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(f"{target_url}/api/generate", json=payload, headers=headers)
            if response.status_code != 200:
                print(f"Error {response.status_code} from {model_key}: {response.text}")
                return {}
            data = response.json()
            response_text = data.get("response", "{}")
            return json.loads(response_text)
            
    except Exception as e:
        print(f"Error calling {model_key}: {type(e).__name__} - {e}")
        return {}

# ---------------------------------------------------------------------------
# HELPER: Looks at the answers from all 3 models and picks the most common one.
# For example, if two models say "Total: 100" and one says "Total: 99", 
# the system will confidently select "100".
# ---------------------------------------------------------------------------
def majority_vote(results, key):
    values = [r.get(key) for r in results if r.get(key) is not None]
    if not values:
        return None
    return max(set(values), key=values.count)

# ---------------------------------------------------------------------------
# HELPER: Calculates how confident we are based on how many models agreed.
# (If 3/3 agree = 1.0 confidence. If 2/3 agree = 0.66 confidence.)
# ---------------------------------------------------------------------------
def consensus_score(results, key):
    values = [r.get(key) for r in results if r.get(key) is not None]
    if not values:
        return 0.0
    most_common = max(set(values), key=values.count)
    return values.count(most_common) / len(results)

# ---------------------------------------------------------------------------
# CORE WORKFLOW: Downloads the PDF, queries models, votes, and saves results.
# ---------------------------------------------------------------------------
async def process_file_background(file_name: str):
    print(f"Starting ensemble processing for {file_name}")
    start_time = time.time()
    
    # Step 1: Download the newly uploaded PDF
    storage_client = storage.Client()
    bucket = storage_client.bucket(SOURCE_BUCKET)
    blob = bucket.blob(file_name)
    
    try:
        file_data = blob.download_as_bytes()
    except Exception as e:
        print(f"Error downloading {file_name}: {e}")
        return
        
    # Step 2: Extract text from the PDF (the "Preprocessing Overhead")
    pdf_text = extract_text_from_pdf(file_data)
    
    # Step 3: Query all three OSS models in parallel at the same time
    results = await asyncio.gather(
        call_model("gemma4-12b", pdf_text),
        call_model("qwen3-6-27b", pdf_text),
        call_model("mistral-7b", pdf_text)
    )
    
    end_time = time.time()
    processing_time = round(end_time - start_time, 2)
    
    print(f"Results before voting: {results}")
    
    # Step 4: Calculate confidence scores for every single extracted field
    scores = [
        consensus_score(results, "invoice_id"),
        consensus_score(results, "total"),
        consensus_score(results, "tax"),
        consensus_score(results, "issuer")
    ]
    total_confidence = sum(scores) / len(scores) if scores else 0.0
    
    # Step 5: Perform majority voting to build the final, highly accurate result
    final_result = {
        "invoice_id": majority_vote(results, "invoice_id"),
        "total": majority_vote(results, "total"),
        "tax": majority_vote(results, "tax"),
        "issuer": majority_vote(results, "issuer"),
        "confidence": total_confidence,
        "processing_time_seconds": processing_time,
        "architecture": "Open-Source Ensemble"
    }
    
    # Step 6: Save the final JSON result back to Cloud Storage
    dest_bucket = storage_client.bucket(DEST_BUCKET)
    dest_file_name = file_name.rsplit('.', 1)[0] + '.json'
    dest_blob = dest_bucket.blob(dest_file_name)
    dest_blob.upload_from_string(json.dumps(final_result, indent=2), content_type='application/json')
    print(f"Ensemble processing complete for {file_name}. Saved to gs://{DEST_BUCKET}/{dest_file_name}")

# ---------------------------------------------------------------------------
# WEB SERVER: This listens for HTTP requests from Eventarc
# ---------------------------------------------------------------------------
@app.post("/")
async def process_invoice(request: Request):
    data = await request.json()
    
    # Extract the filename from the Eventarc payload
    if "message" in data and "data" in data["message"]:
        import base64
        gcs_event = json.loads(base64.b64decode(data["message"]["data"]).decode('utf-8'))
        file_name = gcs_event.get("name")
    else:
        file_name = data.get("name")
        
    if not file_name:
        return {"status": "error", "message": "No file name found in event"}
        
    # Kick off the long-running process in the background so we can quickly 
    # acknowledge the Eventarc message and avoid timeouts
    await process_file_background(file_name)
    return {"status": "processed", "file": file_name}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
