import os
from googleapiclient.discovery import build
from google.oauth2 import service_account

# Use root repo property_files (one folder for all subprojects)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SERVICE_ACCOUNT_FILE = os.path.join(_REPO_ROOT, 'property_files', 'calendar-automate-srvc-account-ref-file.json')
credentials = service_account.Credentials.from_service_account_file(_SERVICE_ACCOUNT_FILE)

# Specify the API service and version
service = build('calendar', 'v3', credentials=credentials, cache_discovery=False)

# Call an API method with timeout (in seconds)
try:
    events_result = service.events().list(calendarId='primary').execute(timeout=30)
    events = events_result.get('items', [])
    for event in events:
        print(event)
except Exception as e:
    print(f"Error: {e}")
