#!/bin/bash
set -e

if [ -f ../../.env ]; then
    export $(cat ../../.env | grep -v '#' | awk '/=/ {print $1}')
else
    echo "Error: .env file not found in repository root. Please copy .env.example to .env and configure it."
    exit 1
fi

PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "Creating Cloud Storage Buckets..."
gcloud storage buckets create gs://${BUCKET_PREFIX}-raw-invoices --location=$REGION || true
gcloud storage buckets create gs://${BUCKET_PREFIX}-spare-invoices --location=$REGION || true
gcloud storage buckets create gs://${BUCKET_PREFIX}-ge-processed-results --location=$REGION || true
gcloud storage buckets create gs://${BUCKET_PREFIX}-os-processed-results --location=$REGION || true

echo "Deploying Gmail Ingestion Cloud Function..."
gcloud functions deploy gmail-ingestion-cf \
  --gen2 \
  --runtime=python311 \
  --region=$REGION \
  --source=gmail-ingestion-cf \
  --entry-point=process_gmail_event \
  --trigger-topic=gmail-inbound \
  --allow-unauthenticated \
  --set-env-vars="BUCKET_PREFIX=${BUCKET_PREFIX},GMAIL_USER=${GMAIL_USER}"

echo "Deploying Gemini Flash Extraction Cloud Function..."
gcloud functions deploy gemini-flash-cf \
  --gen2 \
  --runtime=python311 \
  --region=$REGION \
  --source=gemini-flash-cf \
  --entry-point=process_invoice \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=${BUCKET_PREFIX}-raw-invoices" \
  --allow-unauthenticated \
  --set-env-vars="PROJECT_ID=${PROJECT_ID},REGION=${REGION},BUCKET_PREFIX=${BUCKET_PREFIX}"

echo "Fetching URLs for Open-Source Models..."
GEMMA_URL=$(gcloud run services describe gemma4-12b --region=$REGION --format='value(status.url)' 2>/dev/null || echo "")
QWEN_URL=$(gcloud run services describe qwen3-6-27b --region=$REGION --format='value(status.url)' 2>/dev/null || echo "")
MISTRAL_URL=$(gcloud run services describe mistral-7b --region=$REGION --format='value(status.url)' 2>/dev/null || echo "")

if [ -z "$GEMMA_URL" ] || [ -z "$QWEN_URL" ] || [ -z "$MISTRAL_URL" ]; then
    echo "Warning: One or more OSS models are not deployed. Ensure deploy_oss_models.sh is run first."
fi

echo "Deploying Open-Source Ensemble on Cloud Run..."
gcloud run deploy os-ensemble-cr \
  --source=os-ensemble-cr \
  --region=$REGION \
  --no-allow-unauthenticated \
  --port=8080 \
  --timeout=3600s \
  --min-instances=0 \
  --set-env-vars="PROJECT_ID=${PROJECT_ID},BUCKET_PREFIX=${BUCKET_PREFIX},GEMMA_URL=${GEMMA_URL},QWEN_URL=${QWEN_URL},MISTRAL_URL=${MISTRAL_URL}"

echo "Creating Eventarc Trigger for Open-Source Ensemble..."
gcloud eventarc triggers create os-ensemble-cr-trigger \
  --location=$REGION \
  --destination-run-service=os-ensemble-cr \
  --destination-run-region=$REGION \
  --event-filters="type=google.cloud.storage.object.v1.finalized" \
  --event-filters="bucket=${BUCKET_PREFIX}-raw-invoices" \
  --service-account=${SERVICE_ACCOUNT}

echo "Deploying Dashboard Worker..."
gcloud run deploy dashboard-worker \
  --source=dashboard-worker \
  --region=$REGION \
  --no-allow-unauthenticated \
  --set-env-vars="BUCKET_PREFIX=${BUCKET_PREFIX}"

echo "Creating Eventarc Trigger for Dashboard Worker..."
gcloud eventarc triggers create dashboard-worker-trigger \
  --location=$REGION \
  --destination-run-service=dashboard-worker \
  --destination-run-region=$REGION \
  --event-filters="type=google.cloud.pubsub.topic.v1.messagePublished" \
  --transport-topic="projects/${PROJECT_ID}/topics/dashboard-commands" \
  --service-account=${SERVICE_ACCOUNT}

echo "Deploying Dashboard UI..."
gcloud run deploy dashboard-ui \
  --source=dashboard \
  --region=$REGION \
  --allow-unauthenticated \
  --port=8501 \
  --set-env-vars="PROJECT_ID=${PROJECT_ID},BUCKET_PREFIX=${BUCKET_PREFIX}"

echo "Deployment complete!"
