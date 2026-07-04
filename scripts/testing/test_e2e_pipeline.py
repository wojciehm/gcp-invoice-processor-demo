import os
import sys
import time
import json
import uuid
import warnings
from dotenv import load_dotenv

# Suppress warnings
warnings.filterwarnings("ignore")

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path)

from google.cloud import storage

# Import PDF generator
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'data_generation'))
from generate_pdf import create_kreditantrag_pdf

def run_e2e_test():
    print("🚀 Starting End-to-End Integration Test...")
    
    project_id = os.environ.get('PROJECT_ID')
    bucket_prefix = os.environ.get('BUCKET_PREFIX')
    
    if not project_id or not bucket_prefix:
        print("❌ Error: Missing PROJECT_ID or BUCKET_PREFIX in .env")
        sys.exit(1)
        
    raw_bucket_name = f"{bucket_prefix}-raw-invoices"
    os_bucket_name = f"{bucket_prefix}-os-processed-results"
    ge_bucket_name = f"{bucket_prefix}-ge-processed-results"
    
    storage_client = storage.Client()
    
    # 1. Generate a mock invoice
    test_id = str(uuid.uuid4())[:8]
    invoice_id = f"TEST-INV-{test_id}"
    total = "1234"
    tax = "234"
    issuer = "Test E2E Corp GmbH"
    filename = f"/tmp/{invoice_id}.pdf"
    
    print(f"📄 Generating Test PDF: {invoice_id}")
    create_kreditantrag_pdf(filename, invoice_id, total, tax, issuer)
    
    # 2. Upload to Raw Bucket
    raw_bucket = storage_client.bucket(raw_bucket_name)
    blob = raw_bucket.blob(f"{invoice_id}.pdf")
    print(f"☁️ Uploading to gs://{raw_bucket_name}/{invoice_id}.pdf")
    blob.upload_from_filename(filename)
    
    # 3. Poll for results (Max 10 minutes)
    print("⏳ Waiting for Eventarc pipelines to process (timeout=600s)...")
    timeout = 600
    ge_success = False
    os_success = False
    ge_output = None
    os_output = None
    
    for attempt in range(200):
        time.sleep(3)
        
        # Check GE Bucket
        if not ge_success:
            ge_bucket = storage_client.bucket(ge_bucket_name)
            ge_blob = ge_bucket.blob(f"{invoice_id}.json")
            if ge_blob.exists():
                data = json.loads(ge_blob.download_as_string())
                if data.get('invoice_id') == invoice_id:
                    print("✅ Gemini Enterprise Pipeline: SUCCESS")
                    ge_success = True
                    ge_output = json.dumps(data, indent=2)
                else:
                    print(f"❌ Gemini Enterprise Pipeline: FAILED DATA VALIDATION - {data}")
                    break
        
        # Check OS Bucket
        if not os_success:
            os_bucket = storage_client.bucket(os_bucket_name)
            os_blob = os_bucket.blob(f"{invoice_id}.json")
            if os_blob.exists():
                data = json.loads(os_blob.download_as_string())
                if data.get('invoice_id') == invoice_id:
                    print("✅ Open-Source Ensemble Pipeline: SUCCESS")
                    os_success = True
                    os_output = json.dumps(data, indent=2)
                else:
                    print(f"❌ Open-Source Pipeline: FAILED DATA VALIDATION - {data}")
                    break
                    
        if ge_success and os_success:
            break
            
    # Cleanup
    try:
        os.remove(filename)
    except:
        pass
        
    print("\n--- TEST RESULTS ---")
    if ge_success and os_success:
        print("🎉 ALL PIPELINES PASSED!")
        print("\n--- GEMINI ENTERPRISE OUTPUT ---")
        print(ge_output)
        print("\n--- OPEN-SOURCE ENSEMBLE OUTPUT ---")
        print(os_output)
        sys.exit(0)
    else:
        if not ge_success:
            print("❌ Gemini Enterprise Pipeline: TIMED OUT OR FAILED")
        if not os_success:
            print("❌ Open-Source Pipeline: TIMED OUT OR FAILED")
        sys.exit(1)

if __name__ == "__main__":
    run_e2e_test()
