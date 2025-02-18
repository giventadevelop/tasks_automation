from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
SERVICE_ACCOUNT_FILE = 'property_files/calendar-automate-srvc-account-ref-file.json'

def get_calendar_service():
    """Gets Google Calendar service using service account credentials"""
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    
    service = build('calendar', 'v3', credentials=credentials)
    return service

def list_upcoming_events():
    """Lists the next 10 events on the user's calendar"""
    service = get_calendar_service()
    
    # Call the Calendar API
    now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
    print('Getting upcoming 10 events')
    events_result = service.events().list(
        calendarId='primary',  # 'primary' represents the user's primary calendar
        timeMin=now,
        maxResults=10,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])

    if not events:
        print('No upcoming events found.')
        return

    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        print(f"Event: {event['summary']}")
        print(f"Start: {start}")
        print(f"ID: {event['id']}")
        print("-" * 40)

if __name__ == '__main__':
    try:
        list_upcoming_events()
    except Exception as e:
        print(f"An error occurred: {str(e)}")
