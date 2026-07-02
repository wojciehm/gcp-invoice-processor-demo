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

PROJECT_ID = 'wojciech-genai-demo'
LOCATION = 'europe-west3'
SOURCE_BUCKET = 'skp-raw-invoices'
DEST_BUCKET = 'skp-os-processed-results'

# URLs will be provided via environment variables when deployed
MODEL_URLS = {
    "gemma4-12b": os.environ.get("GEMMA_URL"),
    "qwen3-6-27b": os.environ.get("QWEN_URL"),
    "mistral-7b": os.environ.get("MISTRAL_URL")
}

# The actual Ollama tags
MODEL_TAGS = {
    "gemma4-12b": "gemma4:12b",
    "qwen3-6-27b": "qwen3.6:27b",
    "mistral-7b": "mistral:7b"
}

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

async def call_model(model_key: str, pdf_text: str):
    target_url = MODEL_URLS.get(model_key)
    if not target_url:
        print(f"URL not configured for {model_key}")
        return {}
        
    model_tag = MODEL_TAGS.get(model_key)

    try:
        # Get auth token
        token = await get_oidc_token(target_url)
        headers = {"Content-Type": "application/json"}
        if token:
            print(f"Successfully generated token for {model_key} (length: {len(token)})")
            headers["Authorization"] = f"Bearer {token}"
        else:
            print(f"Warning: No token generated for {model_key}")
            
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

def majority_vote(results, key):
    values = [r.get(key) for r in results if r.get(key) is not None]
    if not values:
        return None
    return max(set(values), key=values.count)

def consensus_score(results, key):
    values = [r.get(key) for r in results if r.get(key) is not None]
    if not values:
        return 0.0
    most_common = max(set(values), key=values.count)
    return values.count(most_common) / len(results)

async def process_file_background(file_name: str):
    print(f"Starting ensemble processing for {file_name}")
    start_time = time.time()
    
    storage_client = storage.Client()
    bucket = storage_client.bucket(SOURCE_BUCKET)
    blob = bucket.blob(file_name)
    
    try:
        file_data = blob.download_as_bytes()
    except Exception as e:
        print(f"Error downloading {file_name}: {e}")
        return
        
    pdf_text = extract_text_from_pdf(file_data)
    
    # Query all three OSS models in parallel
    results = await asyncio.gather(
        call_model("gemma4-12b", pdf_text),
        call_model("qwen3-6-27b", pdf_text),
        call_model("mistral-7b", pdf_text)
    )
    
    end_time = time.time()
    processing_time = round(end_time - start_time, 2)
    
    print(f"Results before voting: {results}")
    
    scores = [
        consensus_score(results, "invoice_id"),
        consensus_score(results, "total"),
        consensus_score(results, "tax"),
        consensus_score(results, "issuer")
    ]
    total_confidence = sum(scores) / len(scores) if scores else 0.0
    
    # Consensus voting
    final_result = {
        "invoice_id": majority_vote(results, "invoice_id"),
        "total": majority_vote(results, "total"),
        "tax": majority_vote(results, "tax"),
        "issuer": majority_vote(results, "issuer"),
        "confidence": total_confidence,
        "processing_time_seconds": processing_time,
        "architecture": "Open-Source Ensemble"
    }
    
    dest_bucket = storage_client.bucket(DEST_BUCKET)
    dest_file_name = file_name.rsplit('.', 1)[0] + '.json'
    dest_blob = dest_bucket.blob(dest_file_name)
    dest_blob.upload_from_string(json.dumps(final_result, indent=2), content_type='application/json')
    print(f"Ensemble processing complete for {file_name}. Saved to gs://{DEST_BUCKET}/{dest_file_name}")

@app.post("/")
async def process_invoice(request: Request):
    data = await request.json()
    
    if "message" in data and "data" in data["message"]:
        import base64
        gcs_event = json.loads(base64.b64decode(data["message"]["data"]).decode('utf-8'))
        file_name = gcs_event.get("name")
    else:
        file_name = data.get("name")
        
    if not file_name:
        return {"status": "error", "message": "No file name found in event"}
        
    await process_file_background(file_name)
    return {"status": "processed", "file": file_name}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
