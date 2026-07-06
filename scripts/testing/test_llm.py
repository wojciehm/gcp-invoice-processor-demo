import asyncio
import urllib.request
import httpx
import time
import os

async def get_oidc_token(audience: str) -> str:
    loop = asyncio.get_running_loop()
    def fetch():
        url = f"http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience={audience}"
        req = urllib.request.Request(url, headers={"Metadata-Flavor": "Google"})
        try:
            response = urllib.request.urlopen(req, timeout=5)
            return response.read().decode('utf-8')
        except Exception as e:
            print(f"Token error: {e}")
            return None
    return await loop.run_in_executor(None, fetch)

async def main():
    target_url = "https://mistral-7b-iibrj6ds7a-ez.a.run.app"
    token = await get_oidc_token(target_url)
    print(f"Token generated: {len(token) if token else 'None'}")
    
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"model": "mistral:7b", "prompt": "Hello", "format": "json", "stream": False}
    
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            print("Sending request...")
            resp = await client.post(f"{target_url}/api/generate", json=payload, headers=headers)
            print(f"Status: {resp.status_code}")
            print(resp.text[:200])
    except Exception as e:
        print(f"Exception: {type(e).__name__}: {e}")
    print(f"Time taken: {time.time() - start:.2f}s")

asyncio.run(main())
