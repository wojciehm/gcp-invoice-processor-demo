#!/bin/bash

set -e

if [ -f ../../.env ]; then
    export $(cat ../../.env | grep -v '#' | awk '/=/ {print $1}')
else
    echo "Error: .env file not found in repository root. Please copy .env.example to .env and configure it."
    exit 1
fi

REPO_NAME="llm-repo"

echo "Creating Artifact Registry repository $REPO_NAME..."
gcloud artifacts repositories create $REPO_NAME \
    --repository-format=docker \
    --location=$REGION \
    --description="Repository for LLM images" || echo "Repository already exists"

    echo "========================================="
    echo "Starting sequential deployments to RTX 6000..."
    echo "========================================="
    
    MODELS=("gemma4:12b" "qwen3.5:9b" "mistral:7b")

    for MODEL in "${MODELS[@]}"; do
        SERVICE_NAME=$(echo "$MODEL" | tr ':' '-' | tr '.' '-')
        
        echo "========================================="
        echo "Deploying $MODEL to RTX 6000"
        echo "========================================="
        
        gcloud run deploy $SERVICE_NAME \
            --image="ollama/ollama:latest" \
            --project=$PROJECT_ID \
            --region=$REGION \
            --no-allow-unauthenticated \
            --cpu=20 \
            --memory=80Gi \
            --gpu=1 \
            --gpu-type=nvidia-rtx-pro-6000 \
            --no-gpu-zonal-redundancy \
            --max-instances=1 \
            --min-instances=1 \
            --execution-environment=gen2 \
            --add-volume=name=llm-volume,type=cloud-storage,bucket=${BUCKET_PREFIX}-llm-model-weights \
            --add-volume-mount=volume=llm-volume,mount-path=/root/.ollama \
            --concurrency=16 \
            --timeout=600s \
            --set-env-vars="OLLAMA_HOST=0.0.0.0:8080"
        
        echo "Finished deployment for $MODEL"
        
        gcloud run services add-iam-policy-binding $SERVICE_NAME \
          --member="serviceAccount:884389213001-compute@developer.gserviceaccount.com" \
          --role="roles/run.invoker" \
          --region=$REGION \
          --project=$PROJECT_ID
        
        echo "Granting OS Ensemble access to $SERVICE_NAME..."
    done
echo "All deployments finished!"
