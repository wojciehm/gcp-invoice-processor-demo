#!/bin/bash
set -e

if [ -f .env ]; then
    export $(cat .env | grep -v '#' | awk '/=/ {print $1}')
else
    echo "Error: .env file not found in repository root. Please copy .env.example to .env and configure it."
    exit 1
fi

PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
PUBSUB_SA="service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"

echo "Ensuring Pub/Sub Service Agent can generate auth tokens for Push subscriptions..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PUBSUB_SA}" \
  --role="roles/iam.serviceAccountTokenCreator" || true

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
  --no-allow-unauthenticated \
  --set-env-vars="PROJECT_ID=${PROJECT_ID},REGION=${REGION},BUCKET_PREFIX=${BUCKET_PREFIX}"

echo "Granting Eventarc Service Account permission to invoke Gemini Flash Cloud Function..."
gcloud functions add-iam-policy-binding gemini-flash-cf \
  --region=$REGION \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/cloudfunctions.invoker"

echo "Fetching URLs for Open-Source Models..."
GEMMA_URL=$(gcloud run services describe gemma4-12b --region=$REGION --format='value(status.url)' 2>/dev/null || echo "")
QWEN_URL=$(gcloud run services describe qwen3-5-9b --region=$REGION --format='value(status.url)' 2>/dev/null || echo "")
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
  --no-cpu-throttling \
  --max-instances=1 \
  --set-env-vars="PROJECT_ID=${PROJECT_ID},BUCKET_PREFIX=${BUCKET_PREFIX},GEMMA_URL=${GEMMA_URL},QWEN_URL=${QWEN_URL},MISTRAL_URL=${MISTRAL_URL}"

echo "Granting Eventarc Service Account permission to invoke Open-Source Ensemble..."
gcloud run services add-iam-policy-binding os-ensemble-cr \
  --region=$REGION \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/run.invoker"

echo "Creating Eventarc Trigger for Open-Source Ensemble..."
gcloud eventarc triggers create os-ensemble-cr-trigger \
  --location=$REGION \
  --destination-run-service=os-ensemble-cr \
  --destination-run-region=$REGION \
  --event-filters="type=google.cloud.storage.object.v1.finalized" \
  --event-filters="bucket=${BUCKET_PREFIX}-raw-invoices" \
  --service-account=${SERVICE_ACCOUNT}

echo "Deploying Dashboard Worker..."
gcloud functions deploy dashboard-worker \
  --gen2 \
  --runtime=python311 \
  --region=$REGION \
  --source=dashboard-worker \
  --entry-point=process_command \
  --trigger-topic=dashboard-commands \
  --no-allow-unauthenticated \
  --set-env-vars="BUCKET_PREFIX=${BUCKET_PREFIX}"

echo "Granting Pub/Sub permission to invoke Dashboard Worker..."
gcloud functions add-iam-policy-binding dashboard-worker \
  --region=$REGION \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/cloudfunctions.invoker"

echo "Deploying Dashboard UI..."
gcloud run deploy dashboard-ui \
  --source=dashboard \
  --region=$REGION \
  --allow-unauthenticated \
  --port=8501 \
  --set-env-vars="PROJECT_ID=${PROJECT_ID},BUCKET_PREFIX=${BUCKET_PREFIX}"

echo "Deployment complete!"
