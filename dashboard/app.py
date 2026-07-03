# ---------------------------------------------------------------------------
# STREAMLIT DASHBOARD
# ---------------------------------------------------------------------------
# This file creates the beautiful web interface you see in your browser.
# It connects to Google Cloud Storage, reads the JSON results generated
# by our AI models, and displays them as metrics and expandable cards.
# ---------------------------------------------------------------------------

import streamlit as st
import pandas as pd
import json
from google.cloud import storage
import concurrent.futures

# Set up the basic layout of the webpage
st.set_page_config(page_title="Document Processing Demo", layout="wide")

st.title("GitOps & Document Processing")
st.subheader("Architecture Battlecard: Open-Source Ensemble vs. Gemini Enterprise")

st.markdown("""
This dashboard compares two architectural approaches to processing inbound invoices. 
Both architectures process invoices dumped into a GCS bucket, but they differ significantly in their implementation complexity, latency, and operational overhead.
""")

# ---------------------------------------------------------------------------
# DATA FETCHING: This function goes into our Google Cloud Storage buckets
# and downloads all the processed JSON files very quickly (using parallel threads).
# The `@st.cache_data` part makes sure we don't redownload the same data 
# multiple times per second, saving cost and time.
# ---------------------------------------------------------------------------

# Initialize GCP Clients
# Streamlit runs in Cloud Run, so ADC is used automatically.
storage_client = storage.Client()

PROJECT_ID = os.environ.get('PROJECT_ID')
TOPIC_ID = "dashboard-commands"
BUCKET_PREFIX = os.environ.get('BUCKET_PREFIX')

@st.cache_data(ttl=5)
def fetch_data():
    os_bucket = storage_client.bucket(f'{BUCKET_PREFIX}-os-processed-results')
    ge_bucket = storage_client.bucket(f'{BUCKET_PREFIX}-ge-processed-results')
    raw_bucket = storage_client.bucket(f'{BUCKET_PREFIX}-raw-invoices')
    
    os_results = []
    ge_results = []
    
    # Count how many invoices were uploaded in total
    total_raw = sum(1 for _ in raw_bucket.list_blobs())
    
    def process_blob(blob):
        try:
            return json.loads(blob.download_as_string())
        except Exception:
            return None

    # Get the list of finished files
    os_blobs = [b for b in os_bucket.list_blobs() if b.name.endswith('.json')]
    ge_blobs = [b for b in ge_bucket.list_blobs() if b.name.endswith('.json')]

    # Download them all simultaneously for speed
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        for res in executor.map(process_blob, os_blobs):
            if res: os_results.append(res)
        for res in executor.map(process_blob, ge_blobs):
            if res: ge_results.append(res)
                
    return os_results, ge_results, total_raw

from google.cloud import pubsub_v1

def publish_command(action):
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
    data = json.dumps({"action": action}).encode("utf-8")
    future = publisher.publish(topic_path, data)
    future.result()

def clear_all_data():
    publish_command("clear_data")

def initiate_copy_from_spare():
    publish_command("initiate_copy")

def fetch_status():
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(f'{BUCKET_PREFIX}-spare-invoices')
        blob = bucket.blob('dashboard_status.json')
        if blob.exists():
            return json.loads(blob.download_as_string())
    except Exception:
        pass
    return {"status": "idle", "task": ""}

status_info = fetch_status()
status_state = status_info.get("status")
is_running = status_state == "running"
is_finished = status_state == "finished"
task_name = status_info.get("task", "")

with st.sidebar:
    st.header("Dashboard Controls")
    
    if is_running:
        st.warning(f"⏳ Please wait for the previous task to finish: **{task_name}**")
    elif is_finished and task_name:
        st.success(f"✅ Task finished: **{task_name}**")
        
    if st.button("🚀 Initiate Test (Copy Data & Recalculate)", type="primary", help="Copies 100 invoices from spare bucket to raw bucket to trigger recalculation and processing", disabled=is_running):
        with st.spinner("Dispatching command..."):
            initiate_copy_from_spare()
        st.cache_data.clear()
        st.success("✅ Command sent! The copy process has started. Once it finishes, the backend processing pipelines will automatically begin.")
        st.rerun()
        
    if st.button("🔄 Refresh UI", type="secondary", help="Fetch the latest processing results from buckets"):
        st.cache_data.clear()
        st.rerun()
        
    if st.button("🧹 Clear All Data", type="primary", help="Deletes all raw and processed invoices", disabled=is_running):
        with st.spinner("Dispatching command..."):
            clear_all_data()
        st.cache_data.clear()
        st.success("🧹 Cleanup command sent to background worker! Buckets will be emptied shortly.")
        st.rerun()

    st.markdown("---")
    auto_refresh = st.toggle("Auto Refresh (every 5s)", value=False)

if auto_refresh:
    import time
    time.sleep(5)
    st.cache_data.clear()
    st.rerun()

os_results, ge_results, total_raw = fetch_data()

os_avg_time = sum([r.get('processing_time_seconds', 0) for r in os_results]) / len(os_results) if os_results else 0
ge_avg_time = sum([r.get('processing_time_seconds', 0) for r in ge_results]) / len(ge_results) if ge_results else 0

os_avg_confidence = sum([r.get('confidence', 0) for r in os_results]) / len(os_results) if os_results else 0
ge_avg_confidence = sum([r.get('confidence', 0) for r in ge_results]) / len(ge_results) if ge_results else 0

col1, col2 = st.columns(2)

with col1:
    st.header("Open-Source Ensemble")
    st.markdown("**(Qwen 3.6 + Mistral + Gemma 4)**")
    
    if total_raw > 0:
        os_progress = min(len(os_results) / total_raw, 1.0)
        st.progress(os_progress, text=f"{len(os_results)} of {total_raw} invoices processed")
    else:
        st.progress(0.0, text="0 of 0 invoices processed")
    
    st.metric(label="Average Latency", value=f"{os_avg_time:.2f}s" if os_avg_time else "N/A", delta=f"+{os_avg_time - ge_avg_time:.2f}s" if (os_avg_time and ge_avg_time) else None, delta_color="inverse")
    st.metric(label="Processed Documents", value=len(os_results))
    st.metric(label="Consensus Logic", value="Required (Majority Vote)", delta="Complex", delta_color="inverse")
    if os_results:
        st.metric(label="Average Confidence", value=f"{os_avg_confidence * 100:.1f}%")
    
    st.info("""
    **Characteristics:**
    - High computational overhead
    - Complex error handling and logging (3 separate endpoints)
    - Vulnerable to model disagreements requiring manual review
    - PyMuPDF preprocessing overhead
    """)
    if os_results:
        st.markdown("### Processed Invoices")
        for res in sorted(os_results, key=lambda x: str(x.get('invoice_id', ''))):
            conf = res.get('confidence', 0)
            icon = "🟢" if conf >= 0.99 else "🟡" if conf >= 0.5 else "🔴"
            invoice_id = res.get('invoice_id', 'Unknown')
            
            with st.expander(f"{icon} {invoice_id} (Confidence: {conf*100:.0f}%)"):
                st.json(res)

with col2:
    st.header("Gemini Enterprise")
    st.markdown("**(Gemini 3.5 Flash)**")
    
    if total_raw > 0:
        ge_progress = min(len(ge_results) / total_raw, 1.0)
        st.progress(ge_progress, text=f"{len(ge_results)} of {total_raw} invoices processed")
    else:
        st.progress(0.0, text="0 of 0 invoices processed")
    
    st.metric(label="Average Latency", value=f"{ge_avg_time:.2f}s" if ge_avg_time else "N/A", delta=f"{ge_avg_time - os_avg_time:.2f}s" if (os_avg_time and ge_avg_time) else None, delta_color="normal")
    st.metric(label="Processed Documents", value=len(ge_results))
    st.metric(label="Consensus Logic", value="Not Required (Built-in)", delta="Simple", delta_color="normal")
    if ge_results:
        st.metric(label="Average Confidence", value=f"{ge_avg_confidence * 100:.1f}%")
    
    st.success("""
    **Characteristics:**
    - 1-pass extraction with native structured output (JSON)
    - Low latency and minimal infrastructure overhead
    - Single API log for compliance and debugging
    - Built-in multi-modal reasoning
    """)
    if ge_results:
        st.markdown("### Processed Invoices")
        for res in sorted(ge_results, key=lambda x: str(x.get('invoice_id', ''))):
            conf = res.get('confidence', 0)
            icon = "🟢" if conf >= 0.99 else "🟡" if conf >= 0.5 else "🔴"
            invoice_id = res.get('invoice_id', 'Unknown')
            
            with st.expander(f"{icon} {invoice_id} (Confidence: {conf*100:.0f}%)"):
                st.json(res)
