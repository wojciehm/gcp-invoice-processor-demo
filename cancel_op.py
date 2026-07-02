from google.cloud import aiplatform

aiplatform.init(project="wojciech-genai-demo", location="europe-west3")
client = aiplatform.gapic.EndpointServiceClient(
    client_options={"api_endpoint": "europe-west3-aiplatform.googleapis.com"}
)
op = client.transport.operations_client.cancel_operation(
    name="projects/884389213001/locations/europe-west3/operations/5590964675316547584"
)
print("Cancelled")
