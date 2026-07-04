# ---------------------------------------------------------------------------
# GEMINI ENTERPRISE CLOUD FUNCTION
# ---------------------------------------------------------------------------
# This file contains the code for a Google Cloud Function that automatically
# triggers whenever a new PDF invoice is uploaded to our raw-invoices bucket.
# It uses the native, multimodal capabilities of Google's Gemini LLM to 
# directly read the PDF and extract structured data (like total and tax) 
# into JSON format, without needing any complex preprocessing.
# ---------------------------------------------------------------------------

import os
import json
import time
import functions_framework
from google.cloud import storage
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from tenacity import retry, wait_random_exponential, stop_after_attempt, retry_if_exception_type
from google.api_core.exceptions import TooManyRequests, InternalServerError, ServiceUnavailable

# Get configuration from environment variables
PROJECT_ID = os.environ.get('PROJECT_ID')
REGION = os.environ.get('REGION', 'europe-west4')
BUCKET_PREFIX = os.environ.get('BUCKET_PREFIX')

DEST_BUCKET = f'{BUCKET_PREFIX}-ge-processed-results'

# ---------------------------------------------------------------------------
# RETRY LOGIC: If the AI model is busy or returns an error, we automatically
# wait a few seconds and try again. This makes the system resilient.
# ---------------------------------------------------------------------------
@retry(wait=wait_random_exponential(multiplier=1, max=60), stop=stop_after_attempt(10), retry=retry_if_exception_type((TooManyRequests, InternalServerError, ServiceUnavailable)))
def generate_content_with_retry(model, pdf_part, prompt, response_schema):
    return model.generate_content(
        [pdf_part, prompt],
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": response_schema
        }
    )

# ---------------------------------------------------------------------------
# MAIN FUNCTION: This is the entry point that Eventarc calls automatically
# whenever a new file appears in the Google Cloud Storage bucket.
# ---------------------------------------------------------------------------
@functions_framework.cloud_event
def process_invoice(cloud_event):
    # Step 1: Figure out which file was just uploaded from the event data
    data = cloud_event.data
    bucket_name = data["bucket"]
    file_name = data["name"]

    print(f"Processing gs://{bucket_name}/{file_name}")

    # Step 2: Initialize connection to Google Vertex AI
    vertexai.init(project=PROJECT_ID, location="global")
    model = GenerativeModel("gemini-3.5-flash")

    # Step 3: Point Gemini directly to the PDF file in Cloud Storage. 
    # (Notice we don't have to download or extract text from it ourselves!)
    pdf_part = Part.from_uri(f"gs://{bucket_name}/{file_name}", mime_type="application/pdf")

    # Step 4: Give the AI instructions on what to extract
    prompt = """
    First, think step-by-step about where to find each field in the invoice text and clearly explain your reasoning.
    Store your detailed reasoning in the '_reasoning' field.
    Then, extract the following details from this invoice.
    """

    # Step 5: Define the exact structure (JSON) we want the AI to return.
    # This guarantees the output will always match our database/dashboard needs.
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "_reasoning": {"type": "STRING", "description": "Step-by-step reasoning for extracting the values"},
            "invoice_id": {"type": "STRING"},
            "total": {"type": "INTEGER"},
            "tax": {"type": "NUMBER"},
            "issuer": {"type": "STRING"},
            "confidence": {"type": "NUMBER", "description": "Confidence score of extraction between 0.0 and 1.0"}
        },
        "required": ["_reasoning", "invoice_id", "total", "tax", "issuer", "confidence"]
    }

    # Step 6: Start a timer and ask Gemini to process the document
    import time
    start_time = time.time()
    
    response = generate_content_with_retry(model, pdf_part, prompt, response_schema)

    end_time = time.time()
    processing_time = round(end_time - start_time, 2)

    # Step 7: Convert the AI's text response into a standard Python dictionary
    try:
        result_dict = json.loads(response.text)
    except json.JSONDecodeError:
        result_dict = {}

    # Step 8: Add some metadata for our dashboard
    result_dict["processing_time_seconds"] = processing_time
    result_dict["architecture"] = "Gemini Enterprise"
    
    final_json_string = json.dumps(result_dict, indent=2)
    print(f"Extracted data: {final_json_string}")

    # Step 9: Save the final JSON result back into our "processed" bucket
    storage_client = storage.Client()
    bucket = storage_client.bucket(DEST_BUCKET)
    
    # Change the extension from .pdf to .json
    dest_file_name = file_name.rsplit('.', 1)[0] + '.json'
    blob = bucket.blob(dest_file_name)
    blob.upload_from_string(final_json_string, content_type='application/json')
    
    print(f"Saved results to gs://{DEST_BUCKET}/{dest_file_name}")
