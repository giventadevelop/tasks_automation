import json
import os
import sys
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

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
    
    # Get the properties file path
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
        
    # Read the properties file
    from jproperties import Properties
    properties = Properties()
    properties_path = os.path.join(base_path, 'property_files', 'calendar_api_properties.properties')
    
    with open(properties_path, 'rb') as config_file:
        properties.load(config_file)
    
    # Get credentials from properties file
    email = properties.get('GOOGLE_EMAIL').data
    password = properties.get('GOOGLE_APP_PASSWORD').data
    
    # Use existing client secrets file
    client_secrets_file = os.path.join(base_path, 'property_files', 'client_secrets.json')
    if not os.path.exists(client_secrets_file):
        raise FileNotFoundError(
            f"Client secrets file not found at {client_secrets_file}. "
            "Please download it from Google Cloud Console and place it in the property_files directory."
        )
    
    token_path = os.path.join(base_path, 'property_files', 'token.pickle')
    
    # Check if we have valid credentials in the token file
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    return creds
