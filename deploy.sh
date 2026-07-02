#!/bin/bash

echo "Deploying Gmail Ingestion Cloud Function..."
gcloud functions deploy gmail-ingestion-cf \
  --gen2 \
  --runtime=python311 \
  --region=europe-west3 \
  --source=gmail-ingestion-cf \
  --entry-point=process_gmail_event \
  --trigger-topic=gmail-inbound \
  --allow-unauthenticated

echo "Deploying Gemini Flash Extraction Cloud Function..."
gcloud functions deploy gemini-flash-cf \
  --gen2 \
  --runtime=python311 \
  --region=europe-west3 \
  --source=gemini-flash-cf \
  --entry-point=process_invoice \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=skp-raw-invoices" \
  --allow-unauthenticated

echo "Deploying Open-Source Ensemble on Cloud Run..."
gcloud run deploy os-ensemble-cr \
  --source=os-ensemble-cr \
  --region=europe-west3 \
  --allow-unauthenticated \
  --port=8080

echo "Deployment complete!"
