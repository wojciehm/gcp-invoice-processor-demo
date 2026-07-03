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

MODELS=("gemma4:12b" "qwen3.6:27b" "mistral:7b")

for MODEL in "${MODELS[@]}"; do
    # Replace colon and dot with dash for the service name
    SERVICE_NAME=$(echo $MODEL | sed 's/[:.]/-/g')
    IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}"
    
    echo "========================================="
    echo "Starting parallel deployment for $MODEL"
    echo "========================================="
    
    (
        # Create a temporary directory for the build context
        BUILD_DIR=$(mktemp -d)
        
        # Create the Dockerfile
        cat <<EOF > $BUILD_DIR/Dockerfile
FROM ollama/ollama
ENV OLLAMA_HOST=0.0.0.0:8080
RUN nohup bash -c "ollama serve &" && sleep 5 && ollama pull ${MODEL}
EOF
        
        echo "Building image for $MODEL in background..."
        gcloud builds submit $BUILD_DIR --tag $IMAGE_URI --region=$REGION --timeout=3600s
        
        echo "Deploying $SERVICE_NAME to Cloud Run..."
        gcloud run deploy $SERVICE_NAME \
            --image=$IMAGE_URI \
            --region=$REGION \
            --gpu=1 \
            --gpu-type=nvidia-l4 \
            --cpu=8 \
            --memory=32Gi \
            --max-instances=1 \
            --min-instances=0 \
            --concurrency=80 \
            --no-gpu-zonal-redundancy \
            --no-allow-unauthenticated \
            --port=8080 \
            --timeout=3600s
        
        echo "Granting OS Ensemble access to $SERVICE_NAME..."
        PROJECT_NUMBER=\$(gcloud projects describe \$PROJECT_ID --format="value(projectNumber)")
        gcloud run services add-iam-policy-binding \$SERVICE_NAME \
            --region=\$REGION \
            --member="serviceAccount:\${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
            --role="roles/run.invoker" || true
        
        # Clean up build directory
        rm -rf $BUILD_DIR
        echo "Finished deployment for $MODEL"
    ) &
done

echo "Waiting for all parallel deployments to finish..."
wait
echo "All deployments finished!"
