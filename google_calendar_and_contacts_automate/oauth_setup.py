import json
import os
import sys
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from jproperties import Properties

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/contacts.other.readonly',
    'https://www.googleapis.com/auth/contacts'
]

def get_oauth_credentials():
    """Gets valid user credentials from storage or initiates OAuth2 flow."""
    creds = None

    # Get the directory where this script is located
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        properties_dir = 'property_files'
    else:
        # Get the directory where the script is located and go up one level
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        properties_dir = 'property_files'

    # Read the properties file from the property_files directory
    properties = Properties()
    properties_path = os.path.join(base_path, properties_dir, 'calendar_api_properties.properties')

    try:
        with open(properties_path, 'rb') as config_file:
            properties.load(config_file)
    except FileNotFoundError:
        print(f"Error: Properties file not found at {properties_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading properties file: {str(e)}")
        sys.exit(1)

    # Get credentials from properties file
    email = properties.get('GOOGLE_EMAIL').data
    password = properties.get('GOOGLE_APP_PASSWORD').data

    # Create or use existing client secrets file
    client_secrets_file = os.path.join(base_path, properties_dir, 'google_desktop_oauth_client_contacts_api.json')

    # Verify client secrets file exists
    if not os.path.exists(client_secrets_file):
        print(f"Error: Client secrets file not found at {client_secrets_file}")
        sys.exit(1)

    token_path = os.path.join(base_path, properties_dir, 'token.pickle')

    # Check if we have valid credentials in the token file
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Token refresh failed: {str(e)}")
                print("Initiating new authentication flow...")
                # Delete invalid token file
                if os.path.exists(token_path):
                    os.remove(token_path)
                # Start fresh authentication
                flow = InstalledAppFlow.from_client_secrets_file(
                    client_secrets_file, SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    return creds
