import os
import sys
import base64
import requests
import json
import calendar
from datetime import datetime, timedelta
import logging
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from jproperties import Properties
import httpx

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('calendar_automate.log')
    ]
)

try:
    logging.info("Starting application...")
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    import anthropic
    from oauth_setup import get_oauth_credentials
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    from requests.exceptions import ConnectionError, Timeout
    import time
    from tenacity import retry, stop_after_attempt, wait_exponential

    logging.info("Successfully imported all required modules")
except Exception as e:
    logging.error(f"Error importing modules: {str(e)}")
    if not getattr(sys, 'frozen', False):
        raise
    else:
        # If running as exe, show error dialog
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Import Error", f"Failed to import required modules:\n\n{str(e)}")
        sys.exit(1)

# Define the scopes
SCOPES = ['https://www.googleapis.com/auth/calendar',
          'https://www.googleapis.com/auth/drive',
          'https://www.googleapis.com/auth/drive.file',
          'https://www.googleapis.com/auth/contacts']

# Determine the base path and set up paths for properties
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    properties_dir = 'property_files'  # Directory inside the executable
else:
    # Get the directory where the script is located and go up one level
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    properties_dir = 'property_files'

# Read the properties file
properties = Properties()
properties_path = os.path.join(base_path, properties_dir, 'calendar_api_properties.properties')

try:
    logging.info(f"Attempting to read properties file from: {properties_path}")
    with open(properties_path, 'rb') as config_file:
        properties.load(config_file)
    logging.info("Successfully loaded properties file")
except FileNotFoundError:
    error_msg = f"Error: Properties file not found at {properties_path}"
    logging.error(error_msg)
    if not getattr(sys, 'frozen', False):
        print(error_msg)
        sys.exit(1)
    else:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error", error_msg)
        sys.exit(1)
except Exception as e:
    error_msg = f"Error reading properties file: {str(e)}"
    logging.error(error_msg)
    if not getattr(sys, 'frozen', False):
        print(error_msg)
        sys.exit(1)
    else:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error", error_msg)
        sys.exit(1)

# Get the service account file path from the properties file
service_account_file = os.path.join(base_path, properties_dir,
                               properties.get('SERVICE_ACCOUNT_FILE').data if properties.get('SERVICE_ACCOUNT_FILE')
                               else 'calendar-automate-srvc-account-ref-file.json')

logging.info(f"Service account file path: {service_account_file}")

# Get OAuth2 credentials
credentials = get_oauth_credentials()

# Build the services
calendar_service = build('calendar', 'v3', credentials=credentials)
drive_service = build('drive', 'v3', credentials=credentials)
people_service = build('people', 'v1', credentials=credentials)


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


# Anthropic API key will be read from .env file at runtime

def show_initial_dialog():
    root = tk.Tk()
    root.withdraw()
    dialog = tk.Toplevel(root)
    dialog.title("")  # Empty title as we'll use custom title bar

    # Calculate screen dimensions and desired dialog size
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    dialog_width = int(screen_width * 3/8)
    dialog_height = int(screen_height * 3/8)

    # Custom title bar style
    title_frame = tk.Frame(dialog, bg='#2c3e50', height=40)
    title_frame.pack(fill='x')
    title_frame.pack_propagate(False)

    title_label = tk.Label(title_frame, text="Daily Tasks Automation",
                          fg='white', bg='#2c3e50',
                          font=('Helvetica', 14, 'bold'))
    title_label.pack(pady=5)

    # Main content frame with padding
    content_frame = tk.Frame(dialog, bg='#ecf0f1', padx=20, pady=20)
    content_frame.pack(fill='both', expand=True)

    result = {'choice': None}

    # Button styles
    button_style = {
        'font': ('Helvetica', 12),
        'width': 20,
        'height': 2,
        'relief': 'raised',
        'borderwidth': 3
    }

    def on_calendar():
        result['choice'] = 'calendar'
        dialog.destroy()

    def on_contacts():
        result['choice'] = 'contacts'
        dialog.destroy()

    def on_laundry():
        result['choice'] = 'laundry'
        dialog.destroy()

    # Create and style buttons
    calendar_btn = tk.Button(content_frame, text="Calendar Entry",
                           bg='#3498db', fg='white',
                           activebackground='#2980b9',
                           command=on_calendar, **button_style)
    calendar_btn.pack(pady=10)

    contacts_btn = tk.Button(content_frame, text="Contact Entry",
                           bg='#2ecc71', fg='white',
                           activebackground='#27ae60',
                           command=on_contacts, **button_style)
    contacts_btn.pack(pady=10)

    laundry_btn = tk.Button(content_frame, text="Laundry",
                           bg='#e74c3c', fg='white',
                           activebackground='#c0392b',
                           command=on_laundry, **button_style)
    laundry_btn.pack(pady=10)

    # Center dialog
    x = (screen_width - dialog_width) // 2
    y = (screen_height - dialog_height) // 2
    dialog.geometry(f'{dialog_width}x{dialog_height}+{x}+{y}')

    # Make dialog modal
    dialog.grab_set()
    dialog.wait_window()
    root.destroy()

    return result['choice']

def get_contact_input():
    root = tk.Tk()
    root.withdraw()

    dialog = tk.Toplevel()
    dialog.title("Contact Details")
    text_area = tk.Text(dialog, width=60, height=20)
    text_area.pack(padx=10, pady=10)

    contact_text = ""

    def on_ok():
        nonlocal contact_text
        contact_text = text_area.get("1.0", tk.END).strip()
        dialog.destroy()

    ok_button = tk.Button(dialog, text="OK", command=on_ok)
    ok_button.pack(pady=10)

    dialog.geometry("500x650")
    dialog.wait_window()

    if not contact_text:
        print("No contact details entered. Exiting.")
        sys.exit(1)

    return contact_text

def show_error_dialog(title, message):
    """Shows a styled error dialog with warning theme."""
    root = tk.Tk()
    root.withdraw()

    # Create error dialog
    dialog = tk.Toplevel(root)
    dialog.title("")  # Empty title as we'll use custom title bar
    dialog.configure(bg='#FFF3E0')  # Light orange background for entire dialog

    # Calculate screen dimensions and dialog size (1/4 of screen)
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    dialog_width = int(screen_width * 1/4)
    dialog_height = int(screen_height * 1/4)

    # Custom title bar style with warning color
    title_frame = tk.Frame(dialog, bg='#FF7043', height=50)  # Deep orange color for warning
    title_frame.pack(fill='x')
    title_frame.pack_propagate(False)

    # Warning icon (⚠️) and title in the same row
    icon_label = tk.Label(title_frame, text="⚠️",
                         fg='white', bg='#FF7043',
                         font=('Helvetica', 16))
    icon_label.pack(side='left', padx=10)

    title_label = tk.Label(title_frame, text=title,
                          fg='white', bg='#FF7043',
                          font=('Helvetica', 14, 'bold'))
    title_label.pack(side='left', pady=10)

    # Main content frame with padding
    content_frame = tk.Frame(dialog, bg='#FFF3E0', padx=25, pady=25)
    content_frame.pack(fill='both', expand=True)

    # Message label with word wrap
    msg_label = tk.Label(content_frame, text=message,
                        bg='#FFF3E0', fg='#D84315',  # Dark orange text
                        font=('Helvetica', 11),
                        wraplength=dialog_width-60,
                        justify='center')  # Center-align text
    msg_label.pack(pady=(20, 30))

    # Create a frame for the button to add a hover effect
    button_frame = tk.Frame(content_frame, bg='#FFF3E0')
    button_frame.pack(pady=(0, 20))

    # Styled OK button - match success dialog size
    ok_button = tk.Button(button_frame, text="OK",
                         bg='#FF7043', fg='white',  # Deep orange button
                         activebackground='#F4511E',  # Darker orange when clicked
                         font=('Helvetica', 16, 'bold'),  # Same size as success dialog
                         width=25, height=2,  # Same size as success dialog
                         relief='raised',
                         borderwidth=4,  # Same border as success dialog
                         cursor='hand2')  # Hand cursor on hover
    ok_button.pack(pady=10, ipady=10)  # Same padding as success dialog

    # Add hover effect
    def on_enter(e):
        ok_button['background'] = '#F4511E'

    def on_leave(e):
        ok_button['background'] = '#FF7043'

    ok_button.bind("<Enter>", on_enter)
    ok_button.bind("<Leave>", on_leave)
    ok_button['command'] = dialog.destroy

    # Center dialog
    x = (screen_width - dialog_width) // 2
    y = (screen_height - dialog_height) // 2
    dialog.geometry(f'{dialog_width}x{dialog_height}+{x}+{y}')

    # Make dialog modal
    dialog.grab_set()
    dialog.wait_window()
    root.destroy()

def extract_contact_details(contact_text):
    try:
        client = anthropic.Anthropic(api_key=properties.get('ANTHROPIC_API_KEY').data)

        prompt = """Extract contact information from the following text. Format the response as a JSON object with these fields: firstName, lastName, companyName, phonenumbers (array), and notes. If any field is not found, use an empty string or empty array. Include all original text in the notes field.

Return ONLY a valid JSON object in this exact format, with no additional text:
{
  "firstName": "John",
  "lastName": "Smith",
  "companyName": "ACME Corp",
  "email": "hh@gmail.com",
  "phonenumbers": [
    "+1 555-0123",
    "+1 555-4567"
  ],
  "notes": "Original text and any additional details"
}"""

        try:
            message = client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": prompt + "\n\n" + contact_text
                    }
                ]
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 529:
                error_msg = "The AI service is currently overloaded. Please try again in a few moments."
                logging.error(f"Anthropic API overloaded: {str(e)}")
                show_error_dialog("Service Busy", error_msg)
                raise Exception(error_msg)
            else:
                error_msg = f"Error communicating with AI service: {str(e)}"
                logging.error(error_msg)
                show_error_dialog("Service Error", error_msg)
                raise Exception(error_msg)

        result = message.content[0].text.strip()
        contact_details = json.loads(result)

        # Show edit dialog
        root = tk.Tk()
        root.withdraw()
        edit_dialog = tk.Toplevel(root)
        edit_dialog.title("Edit Contact Details")

        fields = {}
        row = 0

        # First Name
        tk.Label(edit_dialog, text="First Name:").grid(row=row, column=0, padx=5, pady=5)
        fields['firstName'] = tk.Entry(edit_dialog, width=40)
        fields['firstName'].insert(0, contact_details.get('firstName', ''))
        fields['firstName'].grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Last Name
        tk.Label(edit_dialog, text="Last Name:").grid(row=row, column=0, padx=5, pady=5)
        fields['lastName'] = tk.Entry(edit_dialog, width=40)
        fields['lastName'].insert(0, contact_details.get('lastName', ''))
        fields['lastName'].grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Company
        tk.Label(edit_dialog, text="Company:").grid(row=row, column=0, padx=5, pady=5)
        fields['companyName'] = tk.Entry(edit_dialog, width=40)
        fields['companyName'].insert(0, contact_details.get('companyName', ''))
        fields['companyName'].grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Email
        tk.Label(edit_dialog, text="Email:").grid(row=row, column=0, padx=5, pady=5)
        fields['email'] = tk.Entry(edit_dialog, width=40)
        fields['email'].insert(0, contact_details.get('email', ''))
        fields['email'].grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Phone Numbers
        tk.Label(edit_dialog, text="Phone Numbers:").grid(row=row, column=0, padx=5, pady=5)
        phone_text = tk.Text(edit_dialog, width=40, height=4)
        phones = contact_details.get('phonenumbers', [])
        phone_text.insert('1.0', '\n'.join(phones))
        phone_text.grid(row=row, column=1, padx=5, pady=5)
        fields['phonenumbers'] = phone_text
        row += 1

        # Notes
        tk.Label(edit_dialog, text="Notes:").grid(row=row, column=0, padx=5, pady=5)
        notes_text = tk.Text(edit_dialog, width=40, height=4)
        notes_text.insert('1.0', contact_details.get('notes', ''))
        notes_text.grid(row=row, column=1, padx=5, pady=5)
        fields['notes'] = notes_text
        row += 1

        def on_submit():
            contact_details['firstName'] = fields['firstName'].get()
            contact_details['lastName'] = fields['lastName'].get()
            contact_details['companyName'] = fields['companyName'].get()
            contact_details['email'] = fields['email'].get()
            contact_details['phonenumbers'] = [p.strip() for p in fields['phonenumbers'].get('1.0', tk.END).split('\n') if p.strip()]
            contact_details['notes'] = fields['notes'].get('1.0', tk.END).strip()
            edit_dialog.destroy()

        tk.Button(edit_dialog, text="Submit", command=on_submit).grid(row=row, column=0, columnspan=2, pady=20)

        edit_dialog.geometry("600x700")
        edit_dialog.grab_set()
        edit_dialog.wait_window()
        root.destroy()

        return contact_details

    except Exception as e:
        logging.error(f"Error extracting contact details: {str(e)}")
        raise

def create_contact(contact_details):
    try:
        # Prepare phone numbers
        phone_numbers = []
        for number in contact_details['phonenumbers']:
            phone_numbers.append({
                'value': number,
                'type': 'other'
            })

        # Create contact body for personal contacts
        contact_body = {
            'names': [
                {
                    'givenName': contact_details['firstName'],
                    'familyName': contact_details['lastName']
                }
            ],
            'organizations': [
                {
                    'name': contact_details['companyName'],
                    'type': 'work'
                }
            ] if contact_details['companyName'] else [],
            'emailAddresses': [
                {
                    'value': contact_details['email'],
                    'type': 'work'
                }
            ] if contact_details.get('email') else [],
            'phoneNumbers': phone_numbers,
            'biographies': [
                {
                    'value': contact_details.get('notes', ''),
                    'contentType': 'TEXT_PLAIN'
                }
            ] if contact_details.get('notes') else []
        }

        # Log the request details
        logging.info("Creating contact in personal Google Contacts")
        logging.info(f"Contact body: {json.dumps(contact_body, indent=2)}")

        # Create the contact using People API with person fields
        result = people_service.people().createContact(
            body=contact_body,
            personFields='names,emailAddresses,phoneNumbers,organizations,biographies'
        ).execute()

        # Get the contact URL from resourceName
        resource_name = result.get('resourceName', '')
        contact_url = ''
        if resource_name and resource_name.startswith('people/'):
            contact_id = resource_name.split('/')[-1]
            contact_url = f"https://contacts.google.com/person/{contact_id}"
            logging.info(f"Contact created successfully. URL: {contact_url}")

        # Log the response
        logging.info(f"Contact creation response: {json.dumps(result, indent=2)}")

        return result, contact_url

    except Exception as e:
        logging.error(f"Error creating contact: {str(e)}")
        raise

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
    global event_details
    try:
        # Get base path and properties directory
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
            properties_dir = 'property_files'
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            properties_dir = 'property_files'

        # Read properties file
        properties_path = os.path.join(base_path, properties_dir, 'calendar_api_properties.properties')
        logging.info(f"Reading properties from: {properties_path}")

        try:
            with open(properties_path, 'r') as f:
                properties = dict(line.strip().split('=') for line in f if '=' in line)
            api_key = properties.get('ANTHROPIC_API_KEY')
            logging.info("Successfully read properties file")
        except Exception as e:
            error_msg = f"Error reading properties file: {str(e)}"
            logging.error(error_msg)
            raise Exception(error_msg)

        if not api_key:
            error_msg = "ANTHROPIC_API_KEY not found in properties file"
            logging.error(error_msg)
            raise Exception(error_msg)

        logging.info("Initializing Anthropic client")
        client = anthropic.Anthropic(api_key=api_key)

        prompt = """Please extract the following information from this {}: event name, date, time, venue, and contacts. If there is no year supplied, default it as the current year. Format the response as a JSON object. For the date and time, please provide them in the format 'YYYY-MM-DD HH:MM AM/PM'. For contacts, provide a list of objects with 'name' and 'phone' fields.
In otherDetails field fill in any meeting links or zoom meeting info and any extra information
if there is no time supplied start time set it as 09:30 AM
if no month provided default to current month for example if the input is 6th call John
 then return the date 6th of current month
Return ONLY a valid JSON object in this exact format, with no additional text:
{{"eventName": "Example Event Name",
  "date": "2024-11-04",
  "startTime": "09:30 AM",
  "endTime": "10:30 AM",
  "venue": "Example Venue",
  "contacts": [
    {{"name": "Contact Name",
      "phone": "123-456-7890"}}
  ],
  "otherDetails": "meeting links and any extra information"
}}"""

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

        # Extract the response text from the message and clean it
        result = message.content[0].text.strip()

        # Find the JSON content within the response
        try:
            # First try to parse the entire response as JSON
            event_details = json.loads(result)
        except json.JSONDecodeError:
            # If that fails, try to extract and clean JSON from the response
            json_start = result.find('{')
            json_end = result.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                logging.error("No JSON content found in response")
                raise ValueError("Invalid response format")

            json_str = result[json_start:json_end]

            # More aggressive cleanup of common formatting issuesn
            json_str = (json_str
                       .replace('\n', '')
                       .replace('            ', '')
                       .replace('        ', '')
                       .replace('    ', '')
                       .strip())

            # Remove any trailing commas before closing braces
            json_str = json_str.replace(',}', '}').replace(',]', ']')

            try:
                event_details = json.loads(json_str)

                # Create and show edit dialog
                root = tk.Tk()
                root.withdraw()  # Hide the main window
                edit_dialog = tk.Toplevel(root)
                edit_dialog.title("Edit Event Details")
                edit_dialog.lift()  # Bring dialog to front
                edit_dialog.focus_force()  # Force focus on dialog

                # Create form fields
                fields = {}
                row = 0

                # Event Name
                tk.Label(edit_dialog, text="Event Name:").grid(row=row, column=0, padx=5, pady=5)
                fields['eventName'] = tk.Entry(edit_dialog, width=40)
                fields['eventName'].insert(0, event_details.get('eventName', ''))
                fields['eventName'].grid(row=row, column=1, padx=5, pady=5)
                row += 1

                # Date
                tk.Label(edit_dialog, text="Date (YYYY-MM-DD):").grid(row=row, column=0, padx=5, pady=5)
                fields['date'] = tk.Entry(edit_dialog, width=40)
                fields['date'].insert(0, event_details.get('date', ''))
                fields['date'].grid(row=row, column=1, padx=5, pady=5)
                row += 1

                # Start Time
                tk.Label(edit_dialog, text="Start Time (HH:MM AM/PM):").grid(row=row, column=0, padx=5, pady=5)
                fields['startTime'] = tk.Entry(edit_dialog, width=40)
                fields['startTime'].insert(0, event_details.get('startTime', ''))
                fields['startTime'].grid(row=row, column=1, padx=5, pady=5)
                row += 1

                # End Time
                tk.Label(edit_dialog, text="End Time (HH:MM AM/PM):").grid(row=row, column=0, padx=5, pady=5)
                fields['endTime'] = tk.Entry(edit_dialog, width=40)
                fields['endTime'].insert(0, event_details.get('endTime', ''))
                fields['endTime'].grid(row=row, column=1, padx=5, pady=5)
                row += 1

                # Venue
                tk.Label(edit_dialog, text="Venue:").grid(row=row, column=0, padx=5, pady=5)
                fields['venue'] = tk.Entry(edit_dialog, width=40)
                fields['venue'].insert(0, event_details.get('venue', ''))
                fields['venue'].grid(row=row, column=1, padx=5, pady=5)
                row += 1

                # Contacts
                tk.Label(edit_dialog, text="Contacts:").grid(row=row, column=0, padx=5, pady=5)
                contacts_text = tk.Text(edit_dialog, width=40, height=4)
                contacts = event_details.get('contacts', [])
                contacts_str = '\n'.join([f"{c.get('name', '')}-{c.get('phone', '')}" for c in contacts])
                contacts_text.insert('1.0', contacts_str)
                contacts_text.grid(row=row, column=1, padx=5, pady=5)
                fields['contacts'] = contacts_text
                row += 1

                # Other Details
                tk.Label(edit_dialog, text="Other Details:").grid(row=row, column=0, padx=5, pady=5)
                other_details = tk.Text(edit_dialog, width=40, height=4)
                other_details.insert('1.0', event_details.get('otherDetails', ''))
                other_details.grid(row=row, column=1, padx=5, pady=5)
                fields['otherDetails'] = other_details
                row += 1

                def on_submit():
                    # Update event_details with edited values
                    event_details['eventName'] = fields['eventName'].get()
                    event_details['date'] = fields['date'].get()
                    event_details['startTime'] = fields['startTime'].get()
                    event_details['endTime'] = fields['endTime'].get()
                    event_details['venue'] = fields['venue'].get()

                    # Parse contacts from text
                    contacts_text = fields['contacts'].get('1.0', tk.END).strip()
                    contacts = []
                    for line in contacts_text.split('\n'):
                        if '-' in line:
                            name, phone = line.split('-', 1)
                            contacts.append({'name': name.strip(), 'phone': phone.strip()})
                    event_details['contacts'] = contacts

                    # Get other details
                    event_details['otherDetails'] = fields['otherDetails'].get('1.0', tk.END).strip()

                    edit_dialog.destroy()

                # Submit button
                submit_btn = tk.Button(edit_dialog, text="Submit", command=on_submit)
                submit_btn.grid(row=row, column=0, columnspan=2, pady=20)

                # Center the dialog
                edit_dialog.geometry("600x700")
                edit_dialog.update_idletasks()
                width = edit_dialog.winfo_width()
                height = edit_dialog.winfo_height()
                x = (edit_dialog.winfo_screenwidth() // 2) - (width // 2)
                y = (edit_dialog.winfo_screenheight() // 2) - (height // 2)
                edit_dialog.geometry(f'{width}x{height}+{x}+{y}')

                # Wait for dialog to close
                edit_dialog.grab_set()  # Make dialog modal
                edit_dialog.wait_window()
                root.destroy()  # Clean up the root window

            except json.JSONDecodeError as e:
                # If still failing, try an even more aggressive cleanup
                json_str = ''.join(c for c in json_str if not c.isspace())
                try:
                    event_details = json.loads(json_str)
                except json.JSONDecodeError:
                    logging.error(f"Failed to parse JSON after cleanup: {json_str}")
                    logging.error(f"JSON Error: {str(e)}")
                    # Instead of raising an error, return default values
                    event_details = {
                        'eventName': 'Unnamed Event',
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'startTime': '09:30 AM',
                        'endTime': '10:30 AM',
                        'venue': '@home_default',
                        'contacts': [{'name': 'Default Contact', 'phone': 'N/A'}],
                        'otherDetails': 'No additional details provided'
                    }
        except json.JSONDecodeError as e:
            logging.error(f"JSON Error: {str(e)}")
            # Provide default event details
            event_details = {
                'eventName': 'Unnamed Event',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'startTime': '09:30 AM',
                'endTime': '10:30 AM',
                'venue': '@home_default',
                'contacts': [{'name': 'Default Contact', 'phone': 'N/A'}]
            }

        # Check for both possible event name keys
        event_name = event_details.get('eventName') or event_details.get('event_name', 'Unnamed Event')
        event_details['eventName'] = event_name  # Normalize to eventName

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
            event_datetime = None
            for fmt in ['%Y-%m-%d %I:%M %p', '%Y-%m-%d %H:%M', '%Y-%m-%d %I:%M%p']:
                try:
                    event_datetime = datetime.strptime(start_date_str, fmt)
                    break
                except ValueError:
                    continue

            if event_datetime is None:
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
            event_end_datetime = event_end_datetime.replace(year=current_year)


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
def create_calendar_event(calendar_service, drive_service, event_details, file_path=None):
    try:
        # Parse dates and check year before showing the form
        try:
            date_str = event_details.get('date', '').strip()
            start_time_str = event_details.get('startTime', '09:30 AM').strip()
            end_time_str = event_details.get('endTime', '10:30 AM').strip()

            event_datetime = datetime.strptime(f"{date_str} {start_time_str}", '%Y-%m-%d %I:%M %p')
            event_end_datetime = datetime.strptime(f"{date_str} {end_time_str}", '%Y-%m-%d %I:%M %p')

            # Check and update year if needed
            current_year = datetime.now().year
            if event_datetime.year < current_year:
                event_datetime = event_datetime.replace(year=current_year)
                event_end_datetime = event_end_datetime.replace(year=current_year)
                # Update the date in event_details with the corrected year
                event_details['date'] = event_datetime.strftime('%Y-%m-%d')
                logging.info(f"Updated year to current year: {current_year}")
        except ValueError as e:
            logging.warning(f"Error parsing date/time: {e}. Using current date with default times.")
            current_date = datetime.now()
            event_datetime = current_date.replace(hour=9, minute=30)
            event_end_datetime = current_date.replace(hour=10, minute=30)

        # Create and show edit dialog
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        edit_dialog = tk.Toplevel(root)
        edit_dialog.title("Edit Event Details")
        edit_dialog.lift()  # Bring dialog to front
        edit_dialog.focus_force()  # Force focus on dialog

        # Create form fields
        fields = {}
        row = 0

        # Event Name
        tk.Label(edit_dialog, text="Event Name:").grid(row=row, column=0, padx=5, pady=5)
        fields['eventName'] = tk.Entry(edit_dialog, width=40)
        fields['eventName'].insert(0, event_details.get('eventName', ''))
        fields['eventName'].grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Date
        tk.Label(edit_dialog, text="Date (YYYY-MM-DD):").grid(row=row, column=0, padx=5, pady=5)
        fields['date'] = tk.Entry(edit_dialog, width=40)
        fields['date'].insert(0, event_details.get('date', ''))
        fields['date'].grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Start Time
        tk.Label(edit_dialog, text="Start Time (HH:MM AM/PM):").grid(row=row, column=0, padx=5, pady=5)
        fields['startTime'] = tk.Entry(edit_dialog, width=40)
        fields['startTime'].insert(0, event_details.get('startTime', ''))
        fields['startTime'].grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # End Time
        tk.Label(edit_dialog, text="End Time (HH:MM AM/PM):").grid(row=row, column=0, padx=5, pady=5)
        fields['endTime'] = tk.Entry(edit_dialog, width=40)
        fields['endTime'].insert(0, event_details.get('endTime', ''))
        fields['endTime'].grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Venue
        tk.Label(edit_dialog, text="Venue:").grid(row=row, column=0, padx=5, pady=5)
        fields['venue'] = tk.Entry(edit_dialog, width=40)
        fields['venue'].insert(0, event_details.get('venue', ''))
        fields['venue'].grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Contacts
        tk.Label(edit_dialog, text="Contacts:").grid(row=row, column=0, padx=5, pady=5)
        contacts_text = tk.Text(edit_dialog, width=40, height=4)
        contacts = event_details.get('contacts', [])
        contacts_str = '\n'.join([f"{c.get('name', '')}-{c.get('phone', '')}" for c in contacts])
        contacts_text.insert('1.0', contacts_str)
        contacts_text.grid(row=row, column=1, padx=5, pady=5)
        fields['contacts'] = contacts_text
        row += 1

        # Other Details
        tk.Label(edit_dialog, text="Other Details:").grid(row=row, column=0, padx=5, pady=5)
        other_details = tk.Text(edit_dialog, width=40, height=4)
        other_details.insert('1.0', event_details.get('otherDetails', ''))
        other_details.grid(row=row, column=1, padx=5, pady=5)
        fields['otherDetails'] = other_details
        row += 1

        def on_submit():
            # Update event_details with edited values
            event_details['eventName'] = fields['eventName'].get()
            event_details['date'] = fields['date'].get()
            event_details['startTime'] = fields['startTime'].get()
            event_details['endTime'] = fields['endTime'].get()
            event_details['venue'] = fields['venue'].get()

            # Parse contacts from text
            contacts_text = fields['contacts'].get('1.0', tk.END).strip()
            contacts = []
            for line in contacts_text.split('\n'):
                if '-' in line:
                    name, phone = line.split('-', 1)
                    contacts.append({'name': name.strip(), 'phone': phone.strip()})
            event_details['contacts'] = contacts

            # Get other details
            event_details['otherDetails'] = fields['otherDetails'].get('1.0', tk.END).strip()

            edit_dialog.destroy()

        # Submit button
        submit_btn = tk.Button(edit_dialog, text="Submit", command=on_submit)
        submit_btn.grid(row=row, column=0, columnspan=2, pady=20)

        # Center the dialog
        edit_dialog.geometry("600x700")
        edit_dialog.update_idletasks()
        width = edit_dialog.winfo_width()
        height = edit_dialog.winfo_height()
        x = (edit_dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (edit_dialog.winfo_screenheight() // 2) - (height // 2)
        edit_dialog.geometry(f'{width}x{height}+{x}+{y}')

        # Wait for dialog to close
        edit_dialog.grab_set()  # Make dialog modal
        edit_dialog.wait_window()
        root.destroy()  # Clean up the root window

        # Parse the dates and times with better error handling
        try:
            # Clean up any extra whitespace in the date and time strings
            date_str = event_details['date'].strip()
            start_time_str = event_details['startTime'].strip()
            end_time_str = event_details['endTime'].strip()

            # If time is missing, set default times
            if not start_time_str:
                start_time_str = "09:30 AM"
            if not end_time_str:
                end_time_str = "10:30 AM"

            # Attempt to parse the datetime
            event_datetime = datetime.strptime(f"{date_str} {start_time_str}", '%Y-%m-%d %I:%M %p')
            event_end_datetime = datetime.strptime(f"{date_str} {end_time_str}", '%Y-%m-%d %I:%M %p')
        except ValueError:
            # If parsing fails, use current date with default times
            current_date = datetime.now().strftime('%Y-%m-%d')
            event_datetime = datetime.strptime(f"{current_date} 09:30 AM", '%Y-%m-%d %I:%M %p')
            event_end_datetime = datetime.strptime(f"{current_date} 10:30 AM", '%Y-%m-%d %I:%M %p')
            logging.warning("Failed to parse date/time. Using default values.")

        # Ensure end time is after start time
        if event_end_datetime <= event_datetime:
            event_end_datetime = event_datetime + timedelta(hours=1)
            logging.warning(f"Adjusted end time to be 1 hour after start time: {event_end_datetime}")

        logging.info(f"Creating calendar event with name: {event_details['eventName']}")
        contacts_str = "\n".join([f"{c['name']} - {c['phone']}" for c in event_details['contacts']])
        description = f"""
Event: {event_details['eventName']}
Start Time: {event_datetime.strftime('%Y-%m-%d %I:%M %p')}
End Time: {event_end_datetime.strftime('%Y-%m-%d %I:%M %p')}
Venue: {event_details['venue']}

Contacts:
{contacts_str}

Other Details:
{event_details.get('otherDetails', 'No additional details provided')}
"""
        # Create the new event title with event name first, followed by year, month name, day of the month, and weekday
        event_title = f"{event_details['eventName']} - {event_datetime.year} {calendar.month_name[event_datetime.month]} {event_datetime.day} ({calendar.day_name[event_datetime.weekday()]})"
        logging.info(f"Event title: {event_title}")

        # Ensure end time is after start time
        if event_end_datetime <= event_datetime:
            event_end_datetime = event_datetime + timedelta(hours=1)
            logging.warning(f"Adjusted end time to be 1 hour after start time: {event_end_datetime}")



        event = {
            'summary': event_title,
            'location': event_details['venue'],
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
                'overrides': [],
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


        # Create the main event first
        event = calendar_service.events().insert(calendarId='giventauser@gmail.com', body=event,
                                               supportsAttachments=True).execute()
        print(f'Event created: {event.get("htmlLink")}')

        # Create reminders for a week before, a day before, and at 9:00 AM on the day of the event
        week_before = event_datetime - timedelta(days=7)
        day_before = event_datetime - timedelta(days=1)
        day_of_event_9am = event_datetime.replace(hour=9, minute=0, second=0, microsecond=0)

        # Create reminders for each date
        for reminder_date in [week_before, day_before, day_of_event_9am]:
            reminder_title = f"{event_datetime.year} {calendar.month_name[event_datetime.month]} {event_datetime.day} ({calendar.day_name[event_datetime.weekday()]}) - Reminder: {event_details['eventName']}"
            reminder_start = reminder_date.replace(microsecond=0)
            reminder_end = reminder_start + timedelta(minutes=30)

            reminder_event = {
                'summary': reminder_title,
                'description': f"Reminder for the upcoming event:\n\n{description}",
                'location': event_details['venue'],
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

            try:
                calendar_service.events().insert(
                    calendarId='giventauser@gmail.com',
                    body=reminder_event,
                    supportsAttachments=True
                ).execute()
                print(f'Reminder event created for {reminder_date.strftime("%Y-%m-%d %I:%M %p")}: {reminder_title}')
            except Exception as e:
                logging.warning(f"Failed to create reminder for {reminder_date}: {str(e)}")
                continue
    except Exception as e:
        logging.error(f"Error in create_calendar_event: {str(e)}")
        messagebox.showerror("Error", f"Failed to create calendar event:\n{str(e)}")
        raise
    finally:
        # MediaFileUpload doesn't need explicit cleanup
        pass


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


def show_success_dialog(title, message):
    """Shows a styled success dialog."""
    root = tk.Tk()
    root.withdraw()

    # Create success dialog
    dialog = tk.Toplevel(root)
    dialog.title("")  # Empty title as we'll use custom title bar

    # Calculate screen dimensions and dialog size (1/4 of screen)
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    dialog_width = int(screen_width * 1/4)
    dialog_height = int(screen_height * 1/4)

    # Custom title bar style
    title_frame = tk.Frame(dialog, bg='#2c3e50', height=40)
    title_frame.pack(fill='x')
    title_frame.pack_propagate(False)

    title_label = tk.Label(title_frame, text=title,
                          fg='white', bg='#2c3e50',
                          font=('Helvetica', 14, 'bold'))
    title_label.pack(pady=5)

    # Main content frame with padding
    content_frame = tk.Frame(dialog, bg='#ecf0f1', padx=20, pady=20)
    content_frame.pack(fill='both', expand=True)

    # Message label with word wrap
    msg_label = tk.Label(content_frame, text=message,
                        bg='#ecf0f1', fg='#2c3e50',
                        font=('Helvetica', 11),
                        wraplength=dialog_width-60)
    msg_label.pack(pady=(20, 30))

    # Styled OK button
    ok_button = tk.Button(content_frame, text="OK",
                         bg='#3498db', fg='white',
                         activebackground='#2980b9',
                         font=('Helvetica', 12, 'bold'),
                         width=15, height=1,
                         relief='raised',
                         borderwidth=3,
                         command=dialog.destroy)
    ok_button.pack(pady=(0, 20))

    # Center dialog
    x = (screen_width - dialog_width) // 2
    y = (screen_height - dialog_height) // 2
    dialog.geometry(f'{dialog_width}x{dialog_height}+{x}+{y}')

    # Make dialog modal
    dialog.grab_set()
    dialog.wait_window()
    root.destroy()


def show_contact_url_dialog(title, message):
    """Shows a styled dialog with a bigger OK button for contact URL."""
    root = tk.Tk()
    root.withdraw()

    # Create success dialog
    dialog = tk.Toplevel(root)
    dialog.title("")  # Empty title as we'll use custom title bar
    dialog.configure(bg='#ecf0f1')  # Set background color for entire dialog

    # Calculate screen dimensions and dialog size (1/4 of screen)
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    dialog_width = int(screen_width * 1/4)
    dialog_height = int(screen_height * 1/4)

    # Custom title bar style
    title_frame = tk.Frame(dialog, bg='#2c3e50', height=50)  # Increased height
    title_frame.pack(fill='x')
    title_frame.pack_propagate(False)

    title_label = tk.Label(title_frame, text=title,
                          fg='white', bg='#2c3e50',
                          font=('Helvetica', 14, 'bold'))
    title_label.pack(pady=10)

    # Main content frame with padding
    content_frame = tk.Frame(dialog, bg='#ecf0f1', padx=25, pady=25)
    content_frame.pack(fill='both', expand=True)

    # Message label with word wrap
    msg_label = tk.Label(content_frame, text=message,
                        bg='#ecf0f1', fg='#2c3e50',
                        font=('Helvetica', 11),
                        wraplength=dialog_width-60,
                        justify='center')  # Center-align text
    msg_label.pack(pady=(20, 30))

    # Create a frame for the button to add a hover effect
    button_frame = tk.Frame(content_frame, bg='#ecf0f1')
    button_frame.pack(pady=(0, 20))

    # Styled OK button - much bigger size
    ok_button = tk.Button(button_frame, text="OK",
                         bg='#3498db', fg='white',
                         activebackground='#2980b9',
                         font=('Helvetica', 16, 'bold'),  # Increased font size
                         width=25, height=2,  # Increased width and height
                         relief='raised',
                         borderwidth=4,  # Thicker border
                         cursor='hand2')  # Hand cursor on hover
    ok_button.pack(pady=10, ipady=10)  # Added internal padding

    # Add hover effect
    def on_enter(e):
        ok_button['background'] = '#2980b9'

    def on_leave(e):
        ok_button['background'] = '#3498db'

    ok_button.bind("<Enter>", on_enter)
    ok_button.bind("<Leave>", on_leave)
    ok_button['command'] = dialog.destroy

    # Center dialog
    x = (screen_width - dialog_width) // 2
    y = (screen_height - dialog_height) // 2
    dialog.geometry(f'{dialog_width}x{dialog_height}+{x}+{y}')

    # Make dialog modal
    dialog.grab_set()
    dialog.wait_window()
    root.destroy()


def main():
    try:
        global event_details
        # Show initial dialog
        choice = show_initial_dialog()

        if choice == 'calendar':
            # Get user input for calendar
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
            create_calendar_event(calendar_service, drive_service, event_details, file_path=image_path)

            # Show success message
            show_success_dialog("Success", "Calendar entry added successfully!")

        elif choice == 'contacts':
            # Get contact input
            contact_text = get_contact_input()

            # Extract and process contact details
            contact_details = extract_contact_details(contact_text)

            # Create the contact and get the URL
            result, contact_url = create_contact(contact_details)

            # Show success message
            show_success_dialog("Success", "Contact created successfully!")
            if contact_url:
                show_contact_url_dialog("Contact URL", f"View contact at:\n{contact_url}")

        elif choice == 'laundry':
            print("\nStarting Laundry Automation...")
            logging.info("Starting Laundry Automation...")

            try:
                if getattr(sys, 'frozen', False):
                    # If running as exe, import directly
                    import laundry_automation
                else:
                    # If running from IDE, add Laundry_TryCents to path
                    laundry_path = os.path.join(base_path, 'Laundry_TryCents')
                    if laundry_path not in sys.path:
                        sys.path.append(laundry_path)
                    import laundry_automation

                logging.info("Imported laundry automation module")

                # Run the main function
                laundry_automation.main()
                print("Laundry automation completed.")
                logging.info("Laundry automation completed.")
                time.sleep(20)  # Wait 20 seconds before exiting
            except ImportError as e:
                error_msg = f"Failed to import laundry automation module: {e}\nPaths: {sys.path}"
                logging.error(error_msg)
                messagebox.showerror("Error", error_msg)
            except Exception as e:
                error_msg = f"Unexpected error in laundry automation: {e}"
                logging.error(error_msg)
                messagebox.showerror("Error", error_msg)
            finally:
                print("Exiting program...")
                logging.info("Exiting program...")
                sys.exit(0)

    except Exception as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error", f"An unexpected error occurred:\n\n{str(e)}")
        logging.error(f"Main function error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
