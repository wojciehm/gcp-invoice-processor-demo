import asyncio
import google.auth
import google.auth.transport.requests
from openai import AsyncOpenAI

async def test():
    credentials, project_id = google.auth.default()
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)

    client = AsyncOpenAI(
        base_url=f"https://us-central1-aiplatform.googleapis.com/v1beta1/projects/{project_id}/locations/us-central1/endpoints/openapi",
        api_key=credentials.token,
    )

    models = [
        "mistralai/mistral-large-2407",
        "google/gemma-4-26b-it",
        "qwen/qwen-3-6-35b-instruct"
    ]
    
    for model in models:
        try:
            print(f"Testing {model}...")
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5
            )
            print(f"SUCCESS: {model}")
        except Exception as e:
            print(f"ERROR for {model}: {e}")

asyncio.run(test())
