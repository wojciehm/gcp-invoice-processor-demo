# ---------------------------------------------------------------------------
# STREAMLIT DASHBOARD
# ---------------------------------------------------------------------------
# This file creates the beautiful web interface you see in your browser.
# It connects to Google Cloud Storage, reads the JSON results generated
# by our AI models, and displays them as metrics and expandable cards.
# ---------------------------------------------------------------------------

import os
import streamlit as st
import pandas as pd
import json
from google.cloud import storage
import concurrent.futures

# Set up the basic layout of the webpage
st.set_page_config(page_title="Document Processing Demo", layout="wide", page_icon="📄")

st.markdown("""
<style>
/* Add a sleek gradient and pulse to the primary button */
button[kind="primary"] {
    background: linear-gradient(135deg, #6e8efb, #a777e3);
    color: white;
    border: none;
    transition: all 0.3s ease;
    animation: pulse 2s infinite;
}
button[kind="primary"]:hover {
    transform: scale(1.05);
    background: linear-gradient(135deg, #5c7cfa, #975ce3);
    box-shadow: 0 4px 15px rgba(167, 119, 227, 0.4);
}
@keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(167, 119, 227, 0.7); }
    70% { box-shadow: 0 0 0 10px rgba(167, 119, 227, 0); }
    100% { box-shadow: 0 0 0 0 rgba(167, 119, 227, 0); }
}

/* Secondary Button Hover */
button[kind="secondary"]:hover {
    transform: scale(1.02);
    border-color: #6e8efb;
    color: #6e8efb;
}

/* Glassmorphism for info boxes */
div[data-testid="stAlert"] {
    backdrop-filter: blur(10px);
    background-color: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

st.title("Document Processing")
st.subheader("Open-Source Ensemble vs. Gemini Enterprise")

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

def kill_processing():
    publish_command("kill_processing")

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
        colA, colB = st.columns([0.8, 0.2])
        with colA:
            st.success(f"✅ Task finished: **{task_name}**")
        with colB:
            if st.button("✖️", key="dismiss_status", help="Dismiss this notification"):
                try:
                    storage_client = storage.Client()
                    storage_client.bucket(f'{BUCKET_PREFIX}-spare-invoices').blob('dashboard_status.json').delete()
                except:
                    pass
                st.rerun()
        
    if st.button("🚀 Initiate Test (Copy Data & Recalculate)", type="primary", help="Copies 100 invoices from spare bucket to raw bucket to trigger recalculation and processing", disabled=is_running):
        with st.spinner("Dispatching command..."):
            initiate_copy_from_spare()
        st.cache_data.clear()
        st.success("✅ Command sent! The copy process has started. Once it finishes, the backend processing pipelines will automatically begin.")
        import time
        time.sleep(2)
        st.rerun()
        
    if st.button("🔄 Refresh UI", type="secondary", help="Fetch the latest processing results from buckets"):
        st.cache_data.clear()
        st.rerun()
        
    if st.button("🧹 Clear All Data", type="primary", help="Deletes all raw and processed invoices", disabled=is_running):
        with st.spinner("Dispatching command..."):
            clear_all_data()
        st.cache_data.clear()
        st.success("🧹 Cleanup command sent to background worker! Buckets will be emptied shortly.")
        import time
        time.sleep(2)
        st.rerun()

    if st.button("🛑 EMERGENCY STOP", type="primary", help="Instantly drains the remaining invoice queue without touching already processed data. In-flight requests will finish.", disabled=is_running):
        with st.spinner("Dispatching emergency stop command..."):
            kill_processing()
        st.cache_data.clear()
        st.success("🛑 Emergency stop command sent! The queue will be cleared momentarily.")
        import time
        time.sleep(2)
        st.rerun()

    st.markdown("---")
    auto_refresh = st.toggle("Auto Refresh (every 5s)", value=False)

if auto_refresh:
    import streamlit.components.v1 as components
    components.html(
        """
        <script>
        setTimeout(function() {
            const buttons = window.parent.document.querySelectorAll('button');
            for (const button of buttons) {
                if (button.innerText.includes('Refresh UI')) {
                    button.click();
                    break;
                }
            }
        }, 5000);
        </script>
        """,
        height=0,
        width=0,
    )

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
    else:
        st.metric(label="Average Confidence", value="N/A")
    
    st.info("""
    **Characteristics:**
    - High computational overhead
    - Complex error handling and logging (3 separate endpoints)
    - Vulnerable to model disagreements requiring manual review
    - PyMuPDF preprocessing overhead
    """)

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
    else:
        st.metric(label="Average Confidence", value="N/A")
    
    st.success("""
    **Characteristics:**
    - 1-pass extraction with native structured output (JSON)
    - Low latency and minimal infrastructure overhead
    - Single API log for compliance and debugging
    - Built-in multi-modal reasoning
    """)

st.markdown("---")
st.header("📊 Performance Analytics")

all_invoices = set([r.get('invoice_id') for r in os_results if r.get('invoice_id')] + [r.get('invoice_id') for r in ge_results if r.get('invoice_id')])

chart_data = []
for inv_id in all_invoices:
    os_res = next((r for r in os_results if r.get('invoice_id') == inv_id), None)
    ge_res = next((r for r in ge_results if r.get('invoice_id') == inv_id), None)
    
    chart_data.append({
        "Invoice ID": inv_id,
        "OS Latency (s)": os_res.get('processing_time_seconds', 0) if os_res else 0,
        "Gemini Latency (s)": ge_res.get('processing_time_seconds', 0) if ge_res else 0,
        "OS Confidence": (os_res.get('confidence', 0) * 100) if os_res else 0,
        "Gemini Confidence": (ge_res.get('confidence', 0) * 100) if ge_res else 0
    })

if chart_data:
    df = pd.DataFrame(chart_data).set_index("Invoice ID")
    
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.subheader("Latency Comparison (seconds)")
        st.bar_chart(df[["OS Latency (s)", "Gemini Latency (s)"]], color=["#ff7f0e", "#1f77b4"])
        
    with chart_col2:
        st.subheader("Confidence Comparison (%)")
        st.line_chart(df[["OS Confidence", "Gemini Confidence"]], color=["#ff7f0e", "#1f77b4"])

st.markdown("---")
st.header("📄 Processed Invoices (Side-by-Side Comparison)")

if not all_invoices:
    st.info("No invoices processed yet. Click 'Initiate Test' to begin.")
else:
    for inv_id in sorted(list(all_invoices)):
        os_res = next((r for r in os_results if r.get('invoice_id') == inv_id), None)
        ge_res = next((r for r in ge_results if r.get('invoice_id') == inv_id), None)
        
        os_done = os_res is not None
        ge_done = ge_res is not None
        
        if os_done and ge_done:
            status_icon = "✅"
        elif ge_done:
            status_icon = "⏳ (OS Pending)"
        elif os_done:
            status_icon = "⏳ (Gemini Pending)"
        else:
            status_icon = "⏳"
            
        with st.expander(f"{status_icon} {inv_id}"):
            header_col1, header_col2 = st.columns(2)
            
            with header_col1:
                st.subheader("Open-Source Ensemble")
                if not os_done:
                    st.info("⏳ Waiting for Open-Source Ensemble to finish processing...")
                else:
                    conf = os_res.get('confidence', 0)
                    icon = "🟢" if conf >= 0.99 else "🟡" if conf >= 0.5 else "🔴"
                    st.markdown(f"**Confidence:** {icon} {conf*100:.0f}% | **Latency:** {os_res.get('processing_time_seconds', 0):.2f}s")
                    
            with header_col2:
                st.subheader("Gemini Enterprise")
                if not ge_done:
                    st.info("⏳ Waiting for Gemini Enterprise to finish processing...")
                else:
                    conf = ge_res.get('confidence', 0)
                    icon = "🟢" if conf >= 0.99 else "🟡" if conf >= 0.5 else "🔴"
                    st.markdown(f"**Confidence:** {icon} {conf*100:.0f}% | **Latency:** {ge_res.get('processing_time_seconds', 0):.2f}s")

            st.markdown("---")
            tab1, tab2, tab3 = st.tabs(["Clean Result", "Raw JSON", "Model Details"])
            
            with tab1:
                t1_col1, t1_col2 = st.columns(2)
                with t1_col1:
                    if os_done:
                        clean_res = {k:v for k,v in os_res.items() if k != 'model_votes'}
                        st.json(clean_res)
                with t1_col2:
                    if ge_done:
                        clean_res = {k:v for k,v in ge_res.items() if k != '_reasoning'}
                        st.json(clean_res)
                        
            with tab2:
                t2_col1, t2_col2 = st.columns(2)
                with t2_col1:
                    if os_done:
                        import copy
                        raw_res = copy.deepcopy(os_res)
                        if 'model_votes' in raw_res:
                            for mv in raw_res['model_votes'].values():
                                mv.pop('_reasoning', None)
                        st.markdown(f"**📂 Source:** `gs://{BUCKET_PREFIX}-os-processed-results/{inv_id}.json`")
                        st.download_button("📥 Download Raw JSON", data=json.dumps(raw_res, indent=2), file_name=f"{inv_id}_os.json", mime="application/json", key=f"dl_os_{inv_id}")
                        st.json(raw_res)
                with t2_col2:
                    if ge_done:
                        raw_res = {k:v for k,v in ge_res.items() if k != '_reasoning'}
                        st.markdown(f"**📂 Source:** `gs://{BUCKET_PREFIX}-ge-processed-results/{inv_id}.json`")
                        st.download_button("📥 Download Raw JSON", data=json.dumps(raw_res, indent=2), file_name=f"{inv_id}_ge.json", mime="application/json", key=f"dl_ge_{inv_id}")
                        st.json(raw_res)
                        
            with tab3:
                t3_col1, t3_col2 = st.columns(2)
                with t3_col1:
                    if os_done:
                        if 'model_votes' in os_res:
                            for model_name, vote_data in os_res['model_votes'].items():
                                st.markdown(f"#### {model_name}")
                                reasoning = vote_data.pop('_reasoning', None)
                                if reasoning:
                                    st.markdown(f"**🧠 {model_name} Reasoning Log:**")
                                    st.info(reasoning)
                        else:
                            st.info("No model votes available.")
                with t3_col2:
                    if ge_done:
                        st.markdown("#### Gemini 3.5 Flash")
                        reasoning = ge_res.get('_reasoning')
                        if reasoning:
                            st.markdown("**🧠 Gemini Reasoning Log:**")
                            st.info(reasoning)
                        else:
                            st.info("No reasoning log available.")

