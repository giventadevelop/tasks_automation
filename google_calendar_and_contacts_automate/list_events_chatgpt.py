from googleapiclient.discovery import build
from google.oauth2 import service_account

# Load credentials
credentials = service_account.Credentials.from_service_account_file('property_files/calendar-automate-srvc-account-ref-file.json')

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
