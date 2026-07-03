import os
import base64
import functions_framework
from google.auth import default
from googleapiclient.discovery import build
from google.cloud import storage

# Get configuration from environment variables
BUCKET_PREFIX = os.environ.get('BUCKET_PREFIX')
BUCKET_NAME = f'{BUCKET_PREFIX}-raw-invoices'
USER_EMAIL = os.environ.get('GMAIL_USER')
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

@functions_framework.cloud_event
def process_gmail_event(cloud_event):
    print(f"Received event: {cloud_event.data}")
    
    # Authenticate using ADC
    credentials, project = default(scopes=SCOPES)
    if hasattr(credentials, 'with_subject'):
        credentials = credentials.with_subject(USER_EMAIL)
    else:
        print("Warning: Credentials do not support Domain-Wide Delegation (with_subject). Attempting without it.")

    service = build('gmail', 'v1', credentials=credentials)
    
    # Query unread emails with subject 'invoice' or 'INBOX'
    query = 'is:unread (subject:invoice OR subject:INBOX) has:attachment'
    results = service.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])
    
    if not messages:
        print("No new invoice emails found.")
        return
    
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    
    for msg in messages:
        msg_id = msg['id']
        message = service.users().messages().get(userId='me', id=msg_id).execute()
        
        # Extract attachments
        for part in message.get('payload', {}).get('parts', []):
            if part.get('filename') and part['filename'].lower().endswith('.pdf'):
                attachment_id = part['body'].get('attachmentId')
                if attachment_id:
                    attachment = service.users().messages().attachments().get(
                        userId='me', messageId=msg_id, id=attachment_id).execute()
                    
                    file_data = base64.urlsafe_b64decode(attachment['data'])
                    
                    blob = bucket.blob(part['filename'])
                    blob.upload_from_string(file_data, content_type='application/pdf')
                    print(f"Uploaded {part['filename']} to {BUCKET_NAME}")
        
        # Mark as read
        service.users().messages().modify(
            userId='me', id=msg_id, body={'removeLabelIds': ['UNREAD']}
        ).execute()
        print(f"Marked message {msg_id} as read.")
