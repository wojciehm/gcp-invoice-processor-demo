import os
import base64
import json
import concurrent.futures
import requests
import google.auth
import time
import functions_framework
from google.auth.transport.requests import AuthorizedSession
from google.cloud import storage
from google.cloud import pubsub_v1
from datetime import datetime, timezone

BUCKET_PREFIX = os.environ.get('BUCKET_PREFIX')
SPARE_BUCKET_NAME = f'{BUCKET_PREFIX}-spare-invoices'
RAW_BUCKET_NAME = f'{BUCKET_PREFIX}-raw-invoices'
OS_BUCKET_NAME = f'{BUCKET_PREFIX}-os-processed-results'
GE_BUCKET_NAME = f'{BUCKET_PREFIX}-ge-processed-results'

# Configure a large connection pool for high concurrency
credentials, project = google.auth.default()
authed_session = AuthorizedSession(credentials)
adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
authed_session.mount('https://', adapter)
authed_session.mount('http://', adapter)

storage_client = storage.Client(project=project, credentials=credentials, _http=authed_session)

def set_status(status, task):
    try:
        bucket = storage_client.bucket(SPARE_BUCKET_NAME)
        blob = bucket.blob('dashboard_status.json')
        blob.upload_from_string(json.dumps({"status": status, "task": task}))
    except Exception as e:
        print(f"Error setting status: {e}")

def handle_initiate_copy():
    set_status("running", "Initiating Copy")
    spare_bucket = storage_client.bucket(SPARE_BUCKET_NAME)
    raw_bucket = storage_client.bucket(RAW_BUCKET_NAME)
    
    blob_names = [b.name for b in spare_bucket.list_blobs() if b.name != 'dashboard_status.json'][:100]
    
    def copy_blob_by_name(blob_name):
        try:
            blob = spare_bucket.blob(blob_name)
            spare_bucket.copy_blob(blob, raw_bucket)
            time.sleep(0.5)
        except Exception as e:
            print(f"Error copying {blob_name}: {e}")

    print(f"Starting copy of {len(blob_names)} invoices...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        list(executor.map(copy_blob_by_name, blob_names))
    print(f"Finished copying {len(blob_names)} invoices.")
    set_status("finished", "Initiating Copy")

def purge_pubsub_queues():
    print("Purging Eventarc Pub/Sub queues...")
    try:
        subscriber = pubsub_v1.SubscriberClient()
        project_path = f"projects/{project}"
        for sub in subscriber.list_subscriptions(request={"project": project_path}):
            sub_name = sub.name
            if "eventarc-" in sub_name and "dashboard-worker" not in sub_name and "gmail" not in sub_name:
                try:
                    request = {"subscription": sub_name, "time": datetime.now(timezone.utc)}
                    subscriber.seek(request=request)
                    print(f"Purged {sub_name}")
                except Exception as e:
                    print(f"Failed to purge {sub_name}: {e}")
    except Exception as e:
        print(f"Error purging queues: {e}")

def handle_kill_processing():
    set_status("running", "Emergency Stop: Emptying Queue")
    
    def delete_blob_by_name(blob_name):
        try:
            storage_client.bucket(RAW_BUCKET_NAME).blob(blob_name).delete()
        except Exception as e:
            pass

    try:
        bucket = storage_client.bucket(RAW_BUCKET_NAME)
        blobs = list(bucket.list_blobs())
        print(f"Emergency stop: Deleting {len(blobs)} queued invoices from raw bucket...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            list(executor.map(lambda b: delete_blob_by_name(b.name), blobs))
        print("Emergency stop completed. Queue cleared.")
        
        # ALSO PURGE PUBSUB!
        purge_pubsub_queues()
        
    except Exception as e:
        print(f"Error during emergency stop: {e}")
        
    set_status("finished", "Emergency Stop (Queue Cleared)")

def handle_clear_data():
    set_status("running", "Clearing Data")
    buckets_to_clear = [
        RAW_BUCKET_NAME,
        OS_BUCKET_NAME,
        GE_BUCKET_NAME
    ]

    def delete_blob_by_name(bucket_name, blob_name):
        try:
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.delete()
        except Exception as e:
            print(f"Error deleting blob {blob_name}: {e}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        for bucket_name in buckets_to_clear:
            try:
                bucket = storage_client.bucket(bucket_name)
                blobs = list(bucket.list_blobs())
                list(executor.map(lambda b: delete_blob_by_name(bucket_name, b.name), blobs))
                print(f"Cleared {len(blobs)} files from {bucket_name}")
            except Exception as e:
                print(f"Error clearing {bucket_name}: {e}")
    print("Finished cleaning up buckets.")
    
    # ALSO PURGE PUBSUB!
    purge_pubsub_queues()
    
    set_status("finished", "Clearing Data")

@functions_framework.cloud_event
def process_command(cloud_event):
    """Triggered from a message on a Cloud Pub/Sub topic."""
    pubsub_message = cloud_event.data["message"]["data"]
    try:
        decoded_msg = base64.b64decode(pubsub_message).decode('utf-8')
        data = json.loads(decoded_msg)
        action = data.get("action")
        
        if action == "initiate_copy":
            handle_initiate_copy()
        elif action == "clear_data":
            handle_clear_data()
        elif action == "kill_processing":
            handle_kill_processing()
        else:
            print(f"Unknown action received: {action}")
    except Exception as e:
        print(f"Error processing message: {e}")
