import os
import sys
import base64
import requests
import json
import calendar
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import anthropic
import logging
import tkinter as tk
from tkinter import filedialog
from jproperties import Properties

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Define the scopes
SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/drive','https://www.googleapis.com/auth/drive.file']

# Read the properties file
properties = Properties()
properties_path = os.path.join('property_files', 'calendar_api_properties.properties')
try:
    with open(properties_path, 'rb') as config_file:
        properties.load(config_file)
except FileNotFoundError:
    print(f"Error: Properties file not found at {properties_path}")
    sys.exit(1)
except Exception as e:
    print(f"Error reading properties file: {str(e)}")
    sys.exit(1)

# Get the service account file path from the properties file
service_account_file = os.path.join('property_files', properties.get('SERVICE_ACCOUNT_FILE', 'calendar-automate-srvc-account-ref-file.json'))

# Load credentials from the service account file
credentials = service_account.Credentials.from_service_account_file(
    service_account_file, scopes=SCOPES)

# Build the services
calendar_service = build('calendar', 'v3', credentials=credentials)
drive_service = build('drive', 'v3', credentials=credentials)

def list_calendar_events():
    # Example: List the next 10 events from the primary calendar
    print(" List the next 10 events ...list_calendar_events() .")
    events_result = calendar_service.events().list(calendarId='giventauser@gmail.com', maxResults=10, singleEvents=True, orderBy='startTime').execute()
    events = events_result.get('items', [])

    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        print(start, event['summary'])

def ensure_credentials_file():
    if not os.path.exists('credentials.json'):
        print("credentials.json not found. Please make sure you have the correct client configuration file.")
        raise FileNotFoundError("credentials.json is missing")
    else:
        print("credentials.json found.")

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Anthropic API key will be read from .env file at runtime

# Create a root window and hide it
root = tk.Tk()
root.withdraw()

# Open file dialog to select the image file
image_path = filedialog.askopenfilename(
    title="Select Image File",
    filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp")]
)

if not image_path:
    print("No file selected. Exiting.")
    sys.exit(1)

print(f"Selected file: {image_path}")

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def extract_event_details(image_path):
    try:
        base64_image = encode_image(image_path)
        
        properties_path = os.path.join('property_files', 'calendar_api_properties.properties')
        with open(properties_path, 'r') as f:
            properties = dict(line.strip().split('=') for line in f if '=' in line)
        api_key = properties.get('ANTHROPIC_API_KEY')
        print(f"Using Anthropic API key from {properties_path}")
        client = anthropic.Anthropic(api_key=api_key)
        
        message = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please extract the following information from this image: event name, date, time, venue, and contacts. Format the response as a JSON object. For the date and time, please provide them in the format 'YYYY-MM-DD HH:MM AM/PM'. For contacts, provide a list of objects with 'name' and 'phone' fields."
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": base64_image
                            }
                        }
                    ]
                }
            ]
        )
        
        result = message.content[0].text
        event_details = json.loads(result)
        
        logging.info(f"Extracted event details: {event_details}")
        
        # Parse date and time
        date_time_str = f"{event_details.get('date', '')} {event_details.get('time', '')}"
        try:
            event_datetime = datetime.strptime(date_time_str, '%Y-%m-%d %I:%M %p')
            # If the year is in the past, set it to the current year
            current_year = datetime.now().year
            if event_datetime.year < current_year:
                event_datetime = event_datetime.replace(year=current_year)
        except ValueError:
            logging.warning(f"Failed to parse date and time: {date_time_str}")
            # If parsing fails, ask the API to correct the format
            correction_message = client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": f"Please convert this date and time '{date_time_str}' to the format 'YYYY-MM-DD HH:MM AM/PM'. If the year is not present or is in the past, use the current year. Only respond with the formatted date and time, nothing else."
                    }
                ]
            )
            corrected_date_time = correction_message.content[0].text.strip()
            logging.info(f"Corrected date and time: {corrected_date_time}")
            event_datetime = datetime.strptime(corrected_date_time, '%Y-%m-%d %I:%M %p')
            # Double-check if the year is still in the past after correction
            current_year = datetime.now().year
            if event_datetime.year < current_year:
                event_datetime = event_datetime.replace(year=current_year)
        
        event_name = event_details.get('event_name') or event_details.get('eventName', 'Unnamed Event')
        venue = event_details.get('venue', 'No venue specified')
        contacts = event_details.get('contacts', [])
        contact_list = [f"{contact['name']} - {contact['phone']}" for contact in contacts]
        
        logging.info(f"Extracted event: {event_name}, Date: {event_datetime}, Venue: {venue}, Contacts: {contact_list}")
        
        return event_name, event_datetime, venue, contact_list
    except Exception as e:
        logging.error(f"Error in extract_event_details: {str(e)}")
        raise

def create_calendar_event(calendar_service, drive_service, event_name, event_datetime, venue, contact_list, file_path=None):
    contacts_str = "\n".join(contact_list)
    description = f"""
Event: {event_name}
Date: {event_datetime.strftime('%Y-%m-%d %I:%M %p')}
Venue: {venue}

Contacts:
{contacts_str}
"""
    # Create the new event title with event name first, followed by year, month name, day of the month, and weekday
    event_title = f"{event_name} - {event_datetime.year} {calendar.month_name[event_datetime.month]} {event_datetime.day} ({calendar.day_name[event_datetime.weekday()]})"
    
    event = {
        'summary': event_title,
        'location': venue,
        'description': description,
        'start': {
            'dateTime': event_datetime.isoformat(),
            'timeZone': 'America/New_York',
        },
        'end': {
            'dateTime': (event_datetime + timedelta(hours=2)).isoformat(),  # Assuming 2-hour duration
            'timeZone': 'America/New_York',
        },
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'popup', 'minutes': 0},  # On the day of the event
                {'method': 'popup', 'minutes': 60 * 24},  # 1 day before
                {'method': 'popup', 'minutes': 60 * 24 * 7},  # 1 week before
            ],
        },
    }

    file_attachment = None
    if file_path:
        folder_name = 'GAIN_SHARED_API'
        folder_id = get_or_create_folder(drive_service, folder_name)
        
        file_metadata = {
            'name': os.path.basename(file_path),
            'parents': [folder_id]
        }
        media = MediaFileUpload(file_path, resumable=True)
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        
        # Set file permissions to "Anyone with the link can view"
        permission = {
            'type': 'anyone',
            'role': 'reader',
            'allowFileDiscovery': False
        }
        drive_service.permissions().create(fileId=file['id'], body=permission).execute()
        
        file_attachment = {
            'fileUrl': file['webViewLink'],
            'title': os.path.basename(file_path),
            'mimeType': 'application/octet-stream'
        }
        event['attachments'] = [file_attachment]

    event = calendar_service.events().insert(calendarId='giventauser@gmail.com', body=event, supportsAttachments=True).execute()
    print(f'Event created: {event.get("htmlLink")}')

    # Create reminders for a week before, a day before, and at 9:00 AM on the day of the event
    week_before = event_datetime - timedelta(days=7)
    day_before = event_datetime - timedelta(days=1)
    day_of_event_9am = event_datetime.replace(hour=9, minute=0, second=0, microsecond=0)

    for reminder_date in [week_before, day_before, day_of_event_9am]:
        reminder_title = f"{event_datetime.year} {calendar.month_name[event_datetime.month]} {event_datetime.day} ({calendar.day_name[event_datetime.weekday()]}) - Reminder: {event_name}"
        reminder_event = {
            'summary': reminder_title,
            'description': f"Reminder for the upcoming event:\n\n{description}",
            'location': venue,
            'start': {
                'dateTime': reminder_date.isoformat(),
                'timeZone': 'America/New_York',
            },
            'end': {
                'dateTime': (reminder_date + timedelta(minutes=30)).isoformat(),
                'timeZone': 'America/New_York',
            },
            'reminders': {
                'useDefault': True,
            },
        }
        if file_attachment:
            reminder_event['attachments'] = [file_attachment]
        
        calendar_service.events().insert(calendarId='giventauser@gmail.com', body=reminder_event, supportsAttachments=True).execute()
        print(f'Reminder event created for {reminder_date.strftime("%Y-%m-%d %I:%M %p")}: {reminder_title}')

def get_or_create_folder(drive_service, folder_name):
    # Check if folder already exists
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    folders = results.get('files', [])

    if folders:
        return folders[0]['id']
    else:
        # Create folder if it doesn't exist
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = drive_service.files().create(body=folder_metadata, fields='id').execute()
        return folder['id']

def main():
    # Extract event details
    event_name, event_datetime, venue, contact_list = extract_event_details(image_path)
    
    # Print the image path for confirmation
    print(f"Using image file: {image_path}")
    print(f"Extracted Event: {event_name}")
    print(f"Date and Time: {event_datetime}")
    print(f"Venue: {venue}")
    print(f"Contact List: {contact_list}")

    # List calendar events using service account
    print("\nListing calendar events:")
    list_calendar_events()

    # Create calendar event using service account
    print("\nCreating calendar event:")
    create_calendar_event(calendar_service, drive_service, event_name, event_datetime, venue, contact_list, file_path=image_path)

if __name__ == '__main__':
    main()
