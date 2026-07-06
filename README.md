# AI Document Processing Architecture Comparison

This repository demonstrates two distinct architectural approaches for extracting structured data (JSON) from unstructured documents (PDF invoices) on Google Cloud. It compares an **Open-Source Ensemble** approach (using Qwen, Mistral, and Gemma) against a **Gemini Enterprise** approach.

## Overview

When an invoice (PDF) is dropped into a Google Cloud Storage (GCS) bucket, Eventarc triggers two parallel extraction pipelines. Both pipelines extract the following fields from the invoice:
- `invoice_id`
- `total`
- `tax`
- `issuer`

The extraction results, including processing time and a calculated confidence score, are saved into two separate GCS buckets. A real-time Streamlit dashboard visualizes the results, comparing the latency, confidence, and complexity of both architectures.

## Data Ingestion Methods

There are three ways to get PDF invoices into the `<YOUR_BUCKET_PREFIX>-raw-invoices` bucket to trigger the pipelines:

1. **Dashboard UI Simulation (Bulk Testing):** Click the "🚀 Initiate Test" button in the Streamlit dashboard to dispatch a background worker that copies 100 sample PDFs from a spare bucket into the raw bucket simultaneously. This is used to test the auto-scaling and parallel processing capabilities of the architectures.
2. **Gmail Ingestion (Real-World Automation):** A background Cloud Function (`gmail-ingestion-cf`) continuously monitors a designated Google Workspace inbox. If it receives an unread email with "invoice" in the subject line, it automatically extracts the PDF attachment, drops it into the raw bucket, and marks the email as read.
3. **Manual Upload:** You can manually drag-and-drop a PDF into the bucket via the Google Cloud Console or upload it using the `gcloud storage cp` CLI tool.

## Architecture

```mermaid
flowchart TD
    %% Modern Sleek Styling
    classDef user fill:#1E88E5,stroke:#0D47A1,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef bucket fill:#FFB300,stroke:#FF6F00,stroke-width:2px,color:#000,rx:8,ry:8;
    classDef compute fill:#43A047,stroke:#1B5E20,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef model fill:#8E24AA,stroke:#4A148C,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef dashboard fill:#E53935,stroke:#b71c1c,stroke-width:2px,color:#fff,rx:8,ry:8;

    User([User / System]):::user -->|Uploads PDF| RawBucket[(<YOUR_BUCKET_PREFIX>-raw-invoices)]:::bucket
    
    RawBucket -->|Eventarc Trigger| GEM_CF[Gemini Flash Function]:::compute
    RawBucket -->|Eventarc Trigger| OS_CF[OS Ensemble Orchestrator]:::compute
    
    subgraph "Gemini Enterprise Architecture"
        GEM_CF -->|Native Extraction| Gemini[Gemini 3.5 Flash]:::model
        Gemini -->|Returns JSON| GEM_CF
    end
    
    subgraph "Open-Source Ensemble Architecture"
        OS_CF -->|Parallel HTTP| Model1[Cloud Run: Gemma 4 12B]:::model
        OS_CF -->|Parallel HTTP| Model2[Cloud Run: Qwen 3.5 9B]:::model
        OS_CF -->|Parallel HTTP| Model3[Cloud Run: Mistral 7B]:::model
        
        Model1 -->|JSON| OS_CF
        Model2 -->|JSON| OS_CF
        Model3 -->|JSON| OS_CF
        
        OS_CF -->|Majority Vote Logic| OS_CF
    end
    
    GEM_CF -->|Saves Result| GEBucket[(<YOUR_BUCKET_PREFIX>-ge-processed-results)]:::bucket
    OS_CF -->|Saves Result| OSBucket[(<YOUR_BUCKET_PREFIX>-os-processed-results)]:::bucket
    
    GEBucket -.-> Dashboard[Streamlit Dashboard]:::dashboard
    OSBucket -.-> Dashboard
```

## Key Architectural Insights for Customers

This demo is designed to highlight the hidden overheads in traditional text-based AI pipelines versus modern multimodal approaches.

### 1. The Multimodal Advantage (Zero Preprocessing)
- **Gemini Enterprise Pipeline:** Gemini 3.5 Flash is **natively multimodal**. The Cloud Function simply passes the raw PDF bytes directly to the Vertex AI API. No third-party parsing libraries, no OCR, and no layout-reconstruction logic is required. This drastically reduces cold starts and code complexity.
- **Open-Source Ensemble:** The OSS models (Mistral, Qwen, Gemma) hosted on Cloud Run via Ollama are **text-only**. The orchestrator *must* incur the compute overhead of running `PyMuPDF` to parse the binary PDF, extract the text, and inject it into the prompt. This introduces latency and risks losing document structure/layout context.

### 2. Serverless Simplicity
By leveraging **Google Cloud Functions (gen2)** for the Gemini pipeline, we eliminate the need for container management, Dockerfiles, and complex orchestration. Eventarc seamlessly triggers the serverless function the millisecond a document lands in Cloud Storage.

## Pipeline Flow Comparison

```mermaid
flowchart LR
    %% Modern Sleek Styling
    classDef bucket fill:#FFB300,stroke:#FF6F00,stroke-width:2px,color:#000,rx:8,ry:8;
    classDef compute fill:#43A047,stroke:#1B5E20,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef model fill:#8E24AA,stroke:#4A148C,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef logic fill:#546E7A,stroke:#263238,stroke-width:2px,color:#fff,rx:8,ry:8;
    classDef result fill:#1E88E5,stroke:#0D47A1,stroke-width:2px,color:#fff,rx:8,ry:8;

    subgraph "Gemini Enterprise (Cloud Function)"
        direction LR
        GCS1[(GCS PDF)]:::bucket -->|Eventarc| CF[Cloud Function]:::compute
        CF -->|Raw Bytes| Gemini[Gemini 3.5 Flash]:::model
        Gemini -->|Native JSON| Result1[(JSON Result)]:::result
    end

    subgraph "Open-Source Ensemble (Cloud Run)"
        direction LR
        GCS2[(GCS PDF)]:::bucket -->|Eventarc| CR[Cloud Run Orchestrator]:::compute
        CR -->|PyMuPDF Parsing| Text(Extracted Text):::logic
        Text -->|HTTP Prompt| M1[Mistral]:::model
        Text -->|HTTP Prompt| M2[Qwen]:::model
        Text -->|HTTP Prompt| M3[Gemma]:::model
        M1 --> Vote{Majority Vote}:::logic
        M2 --> Vote
        M3 --> Vote
        Vote -->|Consensus JSON| Result2[(JSON Result)]:::result
    end
```

## Code References (Where does the magic happen?)

For those wanting to explore the code, here are the main files to look at:

- **`gemini-flash-cf/main.py`**: The Cloud Function that receives the Eventarc trigger, connects directly to Vertex AI, and passes the PDF to **Gemini 3.5 Flash** for native multimodal extraction.
- **`os-ensemble-cr/app.py`**: The Cloud Run Orchestrator that receives the Eventarc trigger, extracts text using PyMuPDF, and manages the parallel HTTP requests to the 3 Open-Source LLMs, culminating in the majority-vote consensus logic.
- **`scripts/deployment/deploy.sh`**: The master deployment script that provisions all buckets, deploys the serverless functions, and wires up the Eventarc triggers.
- **`scripts/deployment/deploy_oss_models.sh`**: The script that provisions the three open-source LLMs (Gemma, Qwen, Mistral) on Cloud Run using NVIDIA L4 GPUs and the Ollama runtime.
- **`dashboard/app.py`**: The Streamlit frontend that queries the output buckets and visualizes the extraction confidence, latency, individual model votes, and JSON results. It also contains an **Emergency Stop** button to instantly drain the Eventarc processing queue if GPUs get overwhelmed.

## Features

1. **Gemini Enterprise Pipeline:**
   - Uses a single Cloud Function invoking **Gemini 3.5 Flash** with native JSON structured outputs.
   - Requires no PDF parsing libraries (handles PDFs natively).
   - Near-instantaneous extraction latency.

2. **Open-Source Ensemble Pipeline:**
   - Uses an orchestrator Cloud Run service to invoke three parallel OSS models running on **NVIDIA RTX 6000 GPUs** via Ollama.
   - Implements a **Consensus Mechanism** (majority vote) across all three models to calculate a confidence score and ensure data accuracy without relying on a single model.
   - Secured with `--no-allow-unauthenticated` identity tokens for internal service-to-service communication.

3. **Streamlit Dashboard:**
   - Displays real-time extraction results with interactive expanders showing individual model votes.
   - Includes a **Raw Data Inspector**: Clicking an invoice expander reveals tabbed views separating the clean Consensus Result from the raw JSON payload and the individual model voting data.
   - Highlights confidence scores with color-coded indicators (🟢, 🟡, 🔴).
   - Allows users to simulate scale by pushing 100+ invoices simultaneously.
   - Includes an **Emergency Stop** feature to fast-fail and drain the Eventarc queue.

## Deployment

To deploy this project to your own Google Cloud environment, follow these steps:

### Prerequisites
- A Google Cloud Project with Billing enabled.
- `gcloud` CLI installed and authenticated.
- Enable necessary APIs: `run.googleapis.com`, `cloudfunctions.googleapis.com`, `eventarc.googleapis.com`, `storage.googleapis.com`.

### 1. Configuration
Create a `.env` file at the root of the repository to configure your unique environment parameters.
```bash
cp .env.example .env
```
Edit `.env` to set your `PROJECT_ID`, `REGION`, `BUCKET_PREFIX` (must be globally unique across GCP), and `GMAIL_USER`.

### 2. Deploy the Open-Source Models
The ensemble relies on three LLMs running on Cloud Run. Run the deployment script to provision them:
```bash
chmod +x scripts/deployment/deploy_oss_models.sh
./scripts/deployment/deploy_oss_models.sh
```
*Note: This script actively downloads the heavy model weights (Gemma, Qwen, Mistral) into a custom Docker image and pushes it to your Google Cloud Artifact Registry before deploying them to Cloud Run with NVIDIA RTX 6000 GPUs. This ensures that when the Cloud Run instances scale up, they do not have to redownload the multi-gigabyte models from the internet.*

> [!IMPORTANT]
> **GPU Quota & Scaling Limitations**
> The deployment script explicitly configures `--min-instances=1`, `--max-instances=1`, and `--gpu=1` for each of the three models. Because GPU virtual machines experience a severe 3-5 minute "hardware cold start" penalty when scaling from 0, setting `min-instances=1` is critical to prevent startup probe timeouts. Furthermore, limiting `max-instances=1` prevents auto-scaling events from accidentally exceeding your region's GPU quota during heavy traffic spikes.

### 2. Deploy Orchestrators & Functions
Run the primary deployment script to provision the storage buckets, the Gemini Cloud Function, the OS Orchestrator, and the Streamlit dashboard:
```bash
chmod +x scripts/deployment/deploy.sh
./scripts/deployment/deploy.sh
```

### 3. Cleanup

To destroy all deployed resources and prevent ongoing charges, run the destruction script:
```bash
chmod +x scripts/deployment/destroy.sh
./scripts/deployment/destroy.sh
```
*Note: This script removes the core pipeline resources but leaves the Open-Source models intact. If you wish to delete the models, run: `gcloud run services delete gemma4-12b qwen3-5-9b mistral-7b --region=$REGION`*

## Testing

You can test the system locally or directly through the Cloud console.

1. **Generate Test Invoices**: Run the included `scripts/data_generation/generate_pdf.py` script to generate sample German invoices. *(Note: These are explicitly truncated to 4 pages, omitting terms and signatures, to optimize Open-Source text parsing speed).*
2. **End-to-End Test**: Upload a generated PDF to the `<YOUR_BUCKET_PREFIX>-raw-invoices` bucket.
3. **View Results**: Visit the URL for your deployed `dashboard-ui` Cloud Run service to see the extraction results appear in real-time.

Alternatively, you can test the OS Ensemble inference directly from your terminal (if authenticated with `gcloud`):
```bash
python3 scripts/testing/test_inference.py
```

To run 10 end-to-end tests automatically and ensure bucket clearing before the run, use:
```bash
./scripts/testing/run_10_tests.sh
```

To test the specific LLMs directly:
```bash
python3 scripts/testing/test_llm.py
```

To apply probe fixes or update Cloud Run jobs directly, utilize the scripts provided in `scripts/deployment`:
```bash
./scripts/deployment/fix_model_probes.sh
./scripts/deployment/update_job.sh
```
