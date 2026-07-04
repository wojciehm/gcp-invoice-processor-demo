#!/bin/bash
set -e

if [ -f .env ]; then
    export $(cat .env | grep -v '#' | awk '/=/ {print $1}')
else
    echo "Error: .env file not found in repository root. Please copy .env.example to .env and configure it."
    exit 1
fi

echo "Destroying Eventarc Triggers..."
gcloud eventarc triggers delete os-ensemble-cr-trigger --location=$REGION --quiet || true

echo "Destroying Cloud Functions..."
gcloud functions delete gmail-ingestion-cf --region=$REGION --gen2 --quiet || true
gcloud functions delete gemini-flash-cf --region=$REGION --gen2 --quiet || true
gcloud functions delete dashboard-worker --region=$REGION --gen2 --quiet || true

echo "Destroying Cloud Run Services..."
gcloud run services delete os-ensemble-cr --region=$REGION --quiet || true
gcloud run services delete dashboard-ui --region=$REGION --quiet || true

echo "Destroying Pub/Sub Topics..."
gcloud pubsub topics delete gmail-inbound --quiet || true
gcloud pubsub topics delete dashboard-commands --quiet || true

echo "Destroying Cloud Storage Buckets..."
# We use --force to delete buckets that contain objects. rm -r does recursive deletion.
gcloud storage rm --recursive gs://${BUCKET_PREFIX}-raw-invoices || true
gcloud storage rm --recursive gs://${BUCKET_PREFIX}-spare-invoices || true
gcloud storage rm --recursive gs://${BUCKET_PREFIX}-ge-processed-results || true
gcloud storage rm --recursive gs://${BUCKET_PREFIX}-os-processed-results || true

echo "Resource destruction complete!"
echo "Note: The Open-Source models (Gemma, Qwen, Mistral) were not deleted by this script."
echo "If you wish to delete them as well, run:"
echo "gcloud run services delete gemma4-12b qwen3-5-9b mistral-7b --region=$REGION --quiet"
