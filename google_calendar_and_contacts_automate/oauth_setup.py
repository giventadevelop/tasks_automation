import os
import sys
from google.oauth2 import service_account

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/contacts'
]

def get_oauth_credentials():
    """Gets credentials from service account file."""
    import json
    from google.oauth2 import service_account
    
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
    
    # Get service account file path
    service_account_file = os.path.join(base_path, 'property_files', 
                                      properties.get('SERVICE_ACCOUNT_FILE',
                                      'calendar-automate-srvc-account-ref-file.json'))
    
    # Load credentials from service account file
    creds = service_account.Credentials.from_service_account_file(
        service_account_file,
        scopes=SCOPES
    )
    
    return creds
