import asyncio
import json
import time
from fastapi import FastAPI, BackgroundTasks, Request
from google.cloud import storage
import uvicorn
import fitz
from openai import AsyncOpenAI
import google.auth
import google.auth.transport.requests
from tenacity import retry, wait_random_exponential, stop_after_attempt, retry_if_exception_type
from google.api_core.exceptions import TooManyRequests, InternalServerError, ServiceUnavailable

app = FastAPI()

PROJECT_ID = 'wojciech-genai-demo'
LOCATION = 'europe-west3'
SOURCE_BUCKET = 'skp-raw-invoices'
DEST_BUCKET = 'skp-os-processed-results'

import vertexai
from vertexai.generative_models import GenerativeModel, Part

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location="global")

response_schema = {
    "type": "OBJECT",
    "properties": {
        "invoice_id": {"type": "STRING"},
        "total": {"type": "INTEGER"},
        "tax": {"type": "NUMBER"},
        "issuer": {"type": "STRING"}
    },
    "required": ["invoice_id", "total", "tax", "issuer"]
}

@retry(wait=wait_random_exponential(multiplier=1, max=60), stop=stop_after_attempt(10), retry=retry_if_exception_type((TooManyRequests, InternalServerError, ServiceUnavailable)))
def generate_content_with_retry(model, pdf_part, response_schema):
    return model.generate_content(
        [pdf_part, "Extract the following details from this invoice."],
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": response_schema
        }
    )

async def call_model(model_name: str, file_data: bytes):
    try:
        model = GenerativeModel(model_name)
        
        pdf_part = Part.from_data(data=file_data, mime_type="application/pdf")
        
        # We use sync generate_content in a thread pool to simulate async
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: generate_content_with_retry(model, pdf_part, response_schema)
        )
        
        content = response.text
        return json.loads(content)
    except Exception as e:
        print(f"Error calling {model_name}: {e}")
        return {}

def majority_vote(results, key):
    values = [r.get(key) for r in results if r.get(key) is not None]
    if not values:
        return None
    # Return the most common value
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
    
    # Token refresh not needed for Vertex AI SDK
    
    # Simulate API calls to models with actual Gemini calls to simulate the ensemble
    results = await asyncio.gather(
        call_model("gemini-3.5-flash", file_data),
        call_model("gemini-3.5-flash", file_data),
        call_model("gemini-3.5-flash", file_data)
    )
    
    end_time = time.time()
    processing_time = round(end_time - start_time, 2)
    
    import random
    
    # Simulate disagreement (25% chance model 2 disagrees, 25% chance model 3 disagrees)
    if len(results) == 3:
        if random.random() < 0.25 and "total" in results[1]:
            results[1]["total"] = results[1].get("total", 0) + 1
        if random.random() < 0.25 and "tax" in results[2]:
            results[2]["tax"] = results[2].get("tax", 0.0) + 0.01
        if random.random() < 0.10 and "issuer" in results[1]:
            results[1]["issuer"] = "Unknown"
    
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
