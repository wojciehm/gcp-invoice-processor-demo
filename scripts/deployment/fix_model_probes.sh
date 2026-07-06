#!/bin/bash
source .env

echo "Updating mistral-7b..."
gcloud run services update mistral-7b \
  --startup-probe=timeoutSeconds=10,failureThreshold=15,periodSeconds=60,tcpSocket.port=8080 \
  --min-instances=0 \
  --region=$REGION --project=$PROJECT_ID --quiet

echo "Updating gemma4-12b..."
gcloud run services update gemma4-12b \
  --startup-probe=timeoutSeconds=10,failureThreshold=15,periodSeconds=60,tcpSocket.port=8080 \
  --min-instances=0 \
  --region=$REGION --project=$PROJECT_ID --quiet

echo "Updating qwen3-5-9b..."
gcloud run services update qwen3-5-9b \
  --startup-probe=timeoutSeconds=10,failureThreshold=15,periodSeconds=60,tcpSocket.port=8080 \
  --min-instances=0 \
  --region=$REGION --project=$PROJECT_ID --quiet

echo "All probes updated!"
