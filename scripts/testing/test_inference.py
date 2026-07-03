import json
import subprocess
import requests
import os

def get_identity_token(audience):
    result = subprocess.run(
        ["gcloud", "auth", "print-identity-token", f"--audiences={audience}"],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip()

def run_test():
    BUCKET_PREFIX = os.environ.get('BUCKET_PREFIX', 'invoice-demo')
    ensemble_url = os.environ.get('ENSEMBLE_URL', 'https://os-ensemble-cr-884389213001.europe-west4.run.app')
    print(f"Fetching identity token for {ensemble_url}...")
    token = get_identity_token(ensemble_url)
    
    print("Sending test request to the ensemble with INV-1001.pdf (via Eventarc payload simulation)...")
    
    # We simulate the Eventarc pubsub payload format that the service expects
    import base64
    gcs_event = {
        "name": "INV-1001.pdf",
        "bucket": f"{BUCKET_PREFIX}-raw-invoices"
    }
    
    encoded_data = base64.b64encode(json.dumps(gcs_event).encode('utf-8')).decode('utf-8')
    
    payload = {
        "message": {
            "data": encoded_data
        }
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(ensemble_url, json=payload, headers=headers)
    
    print(f"Response Status: {response.status_code}")
    try:
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response Text: {response.text}")
        
    print(f"\nCheck Google Cloud Storage bucket '{BUCKET_PREFIX}-os-processed-results' for the final output!")

if __name__ == "__main__":
    run_test()
