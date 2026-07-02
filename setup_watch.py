import json
from google.auth import default
from googleapiclient.discovery import build

USER_EMAIL = 'wmarusiak@gcp.altostrat.com'
TOPIC_NAME = 'projects/wojciech-genai-demo/topics/gmail-inbound'
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def setup_gmail_watch():
    credentials, project = default(scopes=SCOPES)
    if hasattr(credentials, 'with_subject'):
        credentials = credentials.with_subject(USER_EMAIL)
        
    service = build('gmail', 'v1', credentials=credentials)
    
    request_body = {
        'labelIds': ['INBOX'],
        'topicName': TOPIC_NAME
    }
    
    print(f"Setting up watch for {USER_EMAIL} to publish to {TOPIC_NAME}...")
    response = service.users().watch(userId='me', body=request_body).execute()
    print("Watch setup successful!")
    print(json.dumps(response, indent=2))

if __name__ == '__main__':
    setup_gmail_watch()
