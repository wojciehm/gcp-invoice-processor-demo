import vertexai
from vertexai import model_garden
import sys

PROJECT_ID = "wojciech-genai-demo"
REGION = "europe-west3"

vertexai.init(project=PROJECT_ID, location=REGION)

models_to_deploy = [
    {
        "name": "Gemma 4",
        "publisher_model": "publishers/google/models/gemma4@gemma-4-26b-a4b-it"
    },
    {
        "name": "Qwen 3.6",
        "publisher_model": "publishers/qwen/models/qwen3-6@qwen3.6-35b-a3b"
    },
    {
        "name": "Mixtral",
        "publisher_model": "publishers/mistralai/models/mixtral-8x7b-instruct-v0.1"
    }
]

print("Starting endpoint deployment test...")

for m in models_to_deploy:
    print(f"\n--- Attempting to deploy {m['name']} ---")
    print(f"Publisher Model Name: {m['publisher_model']}")
    try:
        model = model_garden.OpenModel(m['publisher_model'])
        print(f"Deploying... this may take 20-30 minutes if quota permits.")
        endpoint = model.deploy(accept_eula=True)
        print(f"SUCCESS! {m['name']} deployed at: {endpoint.resource_name}")
    except Exception as e:
        print(f"FAILED to deploy {m['name']}:")
        print(e)
        sys.exit(1)

print("\nAll models deployed successfully!")
