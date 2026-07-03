import json
import functions_framework
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.cloud import storage
from tenacity import retry, wait_random_exponential, stop_after_attempt, retry_if_exception_type
from google.api_core.exceptions import TooManyRequests, InternalServerError, ServiceUnavailable

PROJECT_ID = 'wojciech-genai-demo'
LOCATION = 'europe-west3'
DEST_BUCKET = 'invoice-demo-ge-processed-results'

@retry(wait=wait_random_exponential(multiplier=1, max=60), stop=stop_after_attempt(10), retry=retry_if_exception_type((TooManyRequests, InternalServerError, ServiceUnavailable)))
def generate_content_with_retry(model, pdf_part, prompt, response_schema):
    return model.generate_content(
        [pdf_part, prompt],
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": response_schema
        }
    )

@functions_framework.cloud_event
def process_invoice(cloud_event):
    data = cloud_event.data

    bucket_name = data["bucket"]
    file_name = data["name"]

    print(f"Processing gs://{bucket_name}/{file_name}")

    vertexai.init(project=PROJECT_ID, location="global")

    model = GenerativeModel("gemini-3.5-flash")

    pdf_part = Part.from_uri(f"gs://{bucket_name}/{file_name}", mime_type="application/pdf")

    prompt = """
    Extract the following details from this invoice.
    """

    response_schema = {
        "type": "OBJECT",
        "properties": {
            "invoice_id": {"type": "STRING"},
            "total": {"type": "INTEGER"},
            "tax": {"type": "NUMBER"},
            "issuer": {"type": "STRING"},
            "confidence": {"type": "NUMBER", "description": "Confidence score of extraction between 0.0 and 1.0"}
        },
        "required": ["invoice_id", "total", "tax", "issuer", "confidence"]
    }

    import time
    start_time = time.time()
    
    response = generate_content_with_retry(model, pdf_part, prompt, response_schema)

    end_time = time.time()
    processing_time = round(end_time - start_time, 2)

    try:
        result_dict = json.loads(response.text)
    except json.JSONDecodeError:
        result_dict = {}

    result_dict["processing_time_seconds"] = processing_time
    result_dict["architecture"] = "Gemini Enterprise"
    
    final_json_string = json.dumps(result_dict, indent=2)

    print(f"Extracted data: {final_json_string}")

    storage_client = storage.Client()
    bucket = storage_client.bucket(DEST_BUCKET)
    
    dest_file_name = file_name.rsplit('.', 1)[0] + '.json'
    blob = bucket.blob(dest_file_name)
    blob.upload_from_string(final_json_string, content_type='application/json')
    
    print(f"Saved results to gs://{DEST_BUCKET}/{dest_file_name}")
