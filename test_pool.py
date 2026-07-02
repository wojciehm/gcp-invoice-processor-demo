import concurrent.futures
import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.cloud import storage
from requests.adapters import HTTPAdapter

credentials, project = google.auth.default()
authed_session = AuthorizedSession(credentials)
adapter = HTTPAdapter(pool_connections=200, pool_maxsize=200)
authed_session.mount('https://', adapter)
authed_session.mount('http://', adapter)

storage_client = storage.Client(project=project, credentials=credentials, _http=authed_session)

def get_blob(i):
    bucket = storage_client.bucket('skp-raw-invoices')
    # just listing to test connection pool
    return i

with concurrent.futures.ThreadPoolExecutor(max_workers=200) as executor:
    list(executor.map(get_blob, range(200)))
print("Success")
