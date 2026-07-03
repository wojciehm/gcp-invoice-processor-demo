#!/bin/bash

echo "Creating Cloud Storage Buckets..."
gcloud storage buckets create gs://invoice-demo-raw-invoices --location=europe-west4 || true
gcloud storage buckets create gs://invoice-demo-spare-invoices --location=europe-west4 || true
gcloud storage buckets create gs://invoice-demo-ge-processed-results --location=europe-west4 || true
gcloud storage buckets create gs://invoice-demo-os-processed-results --location=europe-west4 || true

echo "Deploying Gmail Ingestion Cloud Function..."
gcloud functions deploy gmail-ingestion-cf \
  --gen2 \
  --runtime=python311 \
  --region=europe-west4 \
  --source=gmail-ingestion-cf \
  --entry-point=process_gmail_event \
  --trigger-topic=gmail-inbound \
  --allow-unauthenticated

echo "Deploying Gemini Flash Extraction Cloud Function..."
gcloud functions deploy gemini-flash-cf \
  --gen2 \
  --runtime=python311 \
  --region=europe-west4 \
  --source=gemini-flash-cf \
  --entry-point=process_invoice \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=invoice-demo-raw-invoices" \
  --allow-unauthenticated

echo "Deploying Open-Source Ensemble on Cloud Run..."
gcloud run deploy os-ensemble-cr \
  --source=os-ensemble-cr \
  --region=europe-west4 \
  --no-allow-unauthenticated \
  --port=8080 \
  --timeout=3600s \
  --min-instances=0 \
  --set-env-vars="GEMMA_URL=https://gemma4-12b-884389213001.europe-west4.run.app,QWEN_URL=https://qwen3-6-27b-884389213001.europe-west4.run.app,MISTRAL_URL=https://mistral-7b-884389213001.europe-west4.run.app"

echo "Creating Eventarc Trigger for Open-Source Ensemble..."
gcloud eventarc triggers create os-ensemble-cr-trigger \
  --location=europe-west4 \
  --destination-run-service=os-ensemble-cr \
  --destination-run-region=europe-west4 \
  --event-filters="type=google.cloud.storage.object.v1.finalized" \
  --event-filters="bucket=invoice-demo-raw-invoices" \
  --service-account=884389213001-compute@developer.gserviceaccount.com

echo "Deployment complete!"
