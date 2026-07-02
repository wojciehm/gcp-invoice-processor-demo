import vertexai
from vertexai.generative_models import GenerativeModel

PROJECT_ID = "wojciech-genai-demo"

try:
    print("Initializing Vertex AI with global location...")
    vertexai.init(project=PROJECT_ID, location="global")
    
    print("Loading gemini-3.5-flash...")
    model = GenerativeModel("gemini-3.5-flash")
    
    print("Generating content...")
    response = model.generate_content("What is 2+2?")
    
    print(f"Response: {response.text}")
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {e}")
