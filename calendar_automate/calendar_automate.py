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
from tkinter import filedialog, simpledialog, messagebox
from jproperties import Properties

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from requests.exceptions import ConnectionError, Timeout
import time
from tenacity import retry, stop_after_attempt, wait_exponential

# Define the scopes
SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/drive',
          'https://www.googleapis.com/auth/drive.file']

# Determine the base path
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.abspath(".")

# Read the properties file
properties = Properties()
properties_path = os.path.join(base_path, 'property_files', 'calendar_api_properties.properties')
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
service_account_file = os.path.join(base_path, 'property_files', properties.get('SERVICE_ACCOUNT_FILE',
                                                                                'calendar-automate-srvc-account-ref-file.json'))

# Load credentials from the service account file
credentials = service_account.Credentials.from_service_account_file(
    service_account_file, scopes=SCOPES)

# Build the services
calendar_service = build('calendar', 'v3', credentials=credentials)
drive_service = build('drive', 'v3', credentials=credentials)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=30),
    reraise=True
)
def list_calendar_events():
    try:
        # Example: List the next 10 events from the primary calendar
        print(" List the next 10 events ...list_calendar_events() .")

        # Get events list
        events_result = calendar_service.events().list(
            calendarId='giventauser@gmail.com',
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute(num_retries=3)

        events = events_result.get('items', [])

        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(start, event['summary'])

    except HttpError as e:
        logging.error(f"HTTP Error in list_calendar_events: {e}")
        if e.resp.status in [403, 404]:
            # Handle permission or not found errors
            messagebox.showerror("Error", "Calendar access error. Please check permissions.")
            raise
        else:
            # Retry other HTTP errors
            raise
    except (ConnectionError, Timeout) as e:
        logging.error(f"Connection error in list_calendar_events: {e}")
        messagebox.showerror("Connection Error",
                             "Failed to connect to Google Calendar. Please check your internet connection.")
        raise
    except Exception as e:
        logging.error(f"Unexpected error in list_calendar_events: {e}")
        messagebox.showerror("Error", f"An unexpected error occurred:\n{str(e)}")
        raise


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

def get_event_input():
    root = tk.Tk()
    root.withdraw()

    choice = messagebox.askquestion("Input Method", "Do you want to enter event details as text?")

    if choice == 'yes':
        dialog = tk.Toplevel()
        dialog.title("Event Details")
        text_area = tk.Text(dialog, width=60, height=20)
        text_area.pack(padx=10, pady=10)

        event_text = ""

        def on_ok():
            nonlocal event_text
            event_text = text_area.get("1.0", tk.END).strip()
            dialog.destroy()

        ok_button = tk.Button(dialog, text="OK", command=on_ok)
        ok_button.pack(pady=10)

        dialog.geometry("500x650")
        dialog.wait_window()

        if not event_text:
            print("No event details entered. Exiting.")
            sys.exit(1)

        image_choice = messagebox.askquestion("Image Upload", "Do you want to upload an image for this event?")
        image_path = None
        if image_choice == 'yes':
            image_path = filedialog.askopenfilename(
                title="Select Image File",
                filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp")]
            )

        return "text", event_text, image_path
    else:
        image_path = filedialog.askopenfilename(
            title="Select Image File",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp")]
        )
        if not image_path:
            print("No file selected. Exiting.")
            sys.exit(1)

        print(f"Selected file: {image_path}")
        return "image", None, image_path


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def extract_event_details(input_type, event_text, image_path):
    try:
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")

        properties_path = os.path.join(base_path, 'property_files', 'calendar_api_properties.properties')
        with open(properties_path, 'r') as f:
            properties = dict(line.strip().split('=') for line in f if '=' in line)
        api_key = properties.get('ANTHROPIC_API_KEY')
        print(f"Using Anthropic API key from {properties_path}")
        client = anthropic.Anthropic(api_key=api_key)

        prompt = "Please extract the following information from this {}: event name, date, time, venue, and contacts. iF there is no year sypplied default it as current year. Format the response as a JSON object. For the date and time, please provide them in the format 'YYYY-MM-DD HH:MM AM/PM'. For contacts, provide a list of objects with 'name' and 'phone' fields."

        if input_type == "image":
            base64_image = encode_image(image_path)
            message = client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt.format("image")
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
        else:  # input_type == "text"
            message = client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt.format("text") + "\n\n" + event_text
                            }
                        ]
                    }
                ]
            )

        try:
            result = message.content[0].text
            # Clean up the response text to ensure it's valid JSON
            result = result.strip()
            if result.startswith('```json'):
                result = result.split('```json')[1]
            if result.endswith('```'):
                result = result.split('```')[0]
            result = result.strip()
            
            try:
                event_details = json.loads(result)
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse JSON: {result}")
                logging.error(f"JSON Error: {str(e)}")
                # Provide default event details
                event_details = {
                    'eventName': 'Unnamed Event',
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'time': '9:30 AM',
                    'venue': '@home_default',
                    'contacts': [{'name': 'Default Contact', 'phone': 'N/A'}]
                }

            logging.info(f"Extracted event details: {event_details}")

            # Parse date and time with defaults
            date = event_details.get('date', datetime.now().strftime('%Y-%m-%d'))
            
            # Try to get time from different possible fields
            try:
                start_time = None
                end_time = None
                
                # Try to get time from different possible fields
                time_value = None
                for time_field in ['startTime', 'timeStart', 'start', 'endTime', 'timeEnd', 'end', 'time']:
                    if time_field in event_details:
                        time_value = event_details[time_field]
                        logging.info(f"Found time in field: {time_field}")
                        break
                
                if time_value is None:
                    # Default to 9:30 AM if no time found
                    time_value = "9:30 AM"
                    logging.info("No time found in event details, using default time: 9:30 AM")

                # Parse the time
                start_date_str = f"{date} {time_value}"
                for fmt in ['%Y-%m-%d %I:%M %p', '%Y-%m-%d %H:%M', '%Y-%m-%d %I:%M%p']:
                    try:
                        event_datetime = datetime.strptime(start_date_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    # If parsing fails, use default time
                    event_datetime = datetime.strptime(f"{date} 9:30 AM", '%Y-%m-%d %I:%M %p')
                    logging.warning("Failed to parse time. Using default: 9:30 AM")

                # Set end time to 1 hour after start time
                event_end_datetime = event_datetime + timedelta(hours=1)
                logging.info(f"Start time: {event_datetime}, End time: {event_end_datetime}")
                    
            except (ValueError, KeyError) as e:
                # Default to 9:30 AM if any parsing fails
                event_datetime = datetime.strptime(f"{date} 9:30 AM", '%Y-%m-%d %I:%M %p')
                logging.warning(f"Failed to parse time ({str(e)}). Using default: 9:30 AM")
        except Exception as e:
            logging.error(f"Error processing event details: {str(e)}")
            raise
        except ValueError:
            event_datetime = datetime.now().replace(hour=10, minute=30, second=0, microsecond=0)
            logging.warning(f"Failed to parse date and time. Using default: {event_datetime}")

        # If the year is in the past, set it to the current year
        current_year = datetime.now().year
        if event_datetime.year < current_year:
            event_datetime = event_datetime.replace(year=current_year)

        event_name = event_details.get('eventName', 'Unnamed Event')
        venue = event_details.get('venue')
        if venue is None:
            venue = '@home_default'
        # Handle contacts with better error handling
        contacts = event_details.get('contacts', [])
        contact_list = []
        for contact in contacts:
            try:
                name = contact.get('name', 'Unknown')
                phone = contact.get('phone', 'N/A')
                contact_list.append(f"{name} - {phone}")
            except (KeyError, AttributeError) as e:
                logging.warning(f"Error processing contact: {str(e)}")
                contact_list.append("Unknown Contact - N/A")
        
        # If no valid contacts were found, add a default contact
        if not contact_list:
            contact_list = ["Default Contact - N/A"]

        logging.info(f"Extracted event: {event_name}, Date: {event_datetime}, Venue: {venue}, Contacts: {contact_list}")

        return event_name, event_datetime, event_end_datetime, venue, contact_list
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON response: {str(e)}")
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error", f"Failed to parse event details:\n{str(e)}\n\nUsing default values.")
        # Return default values
        default_datetime = datetime.now()
        default_end = default_datetime + timedelta(hours=1)
        return "Default Event", default_datetime, default_end, "@home_default", ["Contact 1 - N/A"]
    except Exception as e:
        logging.error(f"Error in extract_event_details: {str(e)}")
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error", f"An error occurred while processing the event:\n{str(e)}")
        raise


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=30),
    reraise=True
)
def create_calendar_event(calendar_service, drive_service, event_name, event_datetime, event_end_datetime, venue, contact_list,
                          file_path=None):
    try:
        logging.info(f"Creating calendar event with name: {event_name}")
        contacts_str = "\n".join(contact_list)
        description = f"""
Event: {event_name}
Start Time: {event_datetime.strftime('%Y-%m-%d %I:%M %p')}
End Time: {event_end_datetime.strftime('%Y-%m-%d %I:%M %p')}
Venue: {venue}

Contacts:
{contacts_str}
"""
        # Create the new event title with event name first, followed by year, month name, day of the month, and weekday
        event_title = f"{event_name} - {event_datetime.year} {calendar.month_name[event_datetime.month]} {event_datetime.day} ({calendar.day_name[event_datetime.weekday()]})"
        logging.info(f"Event title: {event_title}")

        # Ensure end time is after start time
        if event_end_datetime <= event_datetime:
            event_end_datetime = event_datetime + timedelta(hours=1)
            logging.warning(f"Adjusted end time to be 1 hour after start time: {event_end_datetime}")

        event = {
            'summary': event_title,
            'location': venue,
            'description': description,
            'start': {
                'dateTime': event_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
                'timeZone': 'America/New_York',
            },
            'end': {
                'dateTime': event_end_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
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

        event = calendar_service.events().insert(calendarId='giventauser@gmail.com', body=event,
                                                 supportsAttachments=True).execute()
        print(f'Event created: {event.get("htmlLink")}')

        # Create reminders for a week before, a day before, and at 9:00 AM on the day of the event
        week_before = event_datetime - timedelta(days=7)
        day_before = event_datetime - timedelta(days=1)
        day_of_event_9am = event_datetime.replace(hour=9, minute=0, second=0, microsecond=0)

        for reminder_date in [week_before, day_before, day_of_event_9am]:
            # Ensure reminder start time is not in the past
            if reminder_date <= datetime.now():
                logging.warning(f"Skipping reminder for {reminder_date} as it's in the past")
                continue
                
            reminder_title = f"{event_datetime.year} {calendar.month_name[event_datetime.month]} {event_datetime.day} ({calendar.day_name[event_datetime.weekday()]}) - Reminder: {event_name}"
            reminder_start = reminder_date.replace(microsecond=0)
            reminder_end = reminder_start + timedelta(minutes=30)
            
            reminder_event = {
                'summary': reminder_title,
                'description': f"Reminder for the upcoming event:\n\n{description}",
                'location': venue,
                'start': {
                    'dateTime': reminder_start.strftime("%Y-%m-%dT%H:%M:%S"),
                    'timeZone': 'America/New_York',
                },
                'end': {
                    'dateTime': reminder_end.strftime("%Y-%m-%dT%H:%M:%S"),
                    'timeZone': 'America/New_York',
                },
                'reminders': {
                    'useDefault': True,
                },
            }
        if file_attachment:
            reminder_event['attachments'] = [file_attachment]

        calendar_service.events().insert(calendarId='giventauser@gmail.com', body=reminder_event,
                                         supportsAttachments=True).execute()
        print(f'Reminder event created for {reminder_date.strftime("%Y-%m-%d %I:%M %p")}: {reminder_title}')
    except Exception as e:
        logging.error(f"Error in create_calendar_event: {str(e)}")
        messagebox.showerror("Error", f"Failed to create calendar event:\n{str(e)}")
        raise
    finally:
        if 'media' in locals():
            media.close()


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
    try:
        # Get user input
        input_type, event_text, image_path = get_event_input()

        # Extract event details
        event_name, event_datetime, event_end_datetime, venue, contact_list = extract_event_details(input_type, event_text, image_path)

        # Print the extracted details for confirmation
        print(f"Extracted Event: {event_name}")
        print(f"Date and Time: {event_datetime}")
        print(f"Venue: {venue}")
        print(f"Contact List: {contact_list}")

        # List calendar events using service account
        print("\nListing calendar events:")
        list_calendar_events()

        # Create calendar event using service account
        print("\nCreating calendar event:")
        create_calendar_event(calendar_service, drive_service, event_name, event_datetime, event_end_datetime, venue, contact_list,
                              file_path=image_path)

        # Show success message
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("Success", "Calendar entry added successfully!")
    except Exception as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error", f"An unexpected error occurred:\n\n{str(e)}")
        logging.error(f"Main function error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
