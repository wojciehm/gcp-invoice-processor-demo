#!/bin/bash
gcloud run jobs update pull-models-fast \
  --region europe-west4 \
  --command="bash" \
  --args="-c,export OLLAMA_MODELS=/root/.ollama/models; pull_and_copy() { ollama serve & SERVER_PID=\$!; sleep 5; echo \"Downloading \$1...\"; ollama pull \$1; echo \"Copying \$1 to FUSE...\"; mkdir -p /mnt/gcs/models; cp -rv \$OLLAMA_MODELS/* /mnt/gcs/models/; kill \$SERVER_PID; wait \$SERVER_PID 2>/dev/null || true; rm -rf \$OLLAMA_MODELS/*; }; pull_and_copy gemma4:12b; pull_and_copy qwen3.5:9b; pull_and_copy mistral; echo 'DONE!'"
