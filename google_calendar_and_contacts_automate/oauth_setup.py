"""
Google OAuth credentials for Calendar, Drive, and People APIs.

Two modes (no browser after first run when using OAuth):
1. Service account impersonation (no browser ever): Set USE_SERVICE_ACCOUNT_IMPERSONATION=true
   in calendar_api_properties.properties. Requires Google Workspace and domain-wide delegation
   for the service account. Uses GOOGLE_EMAIL and SERVICE_ACCOUNT_FILE from properties.
2. OAuth with stored token (browser once): First run opens the browser to sign in; after that
   the refresh token in token.pickle is used so no browser is shown. Token is stored in a
   writable location (AppData when running as exe, property_files otherwise).

Note: Google does not allow Calendar/Drive/People API access with email + password only;
OAuth or service-account delegation is required.
"""
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


def _get_base_path_and_properties():
    """Return (base_path for config files, properties_dir name, loaded Properties)."""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        properties_dir = 'property_files'
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        properties_dir = 'property_files'

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
    return base_path, properties_dir, properties


def _get_writable_token_path(base_path, properties_dir):
    """
    Return a path for token.pickle that is always writable so the token persists.
    When running as frozen exe, sys._MEIPASS is read-only, so we use AppData instead.
    """
    if getattr(sys, 'frozen', False):
        appdata = os.environ.get('APPDATA') or os.path.expanduser('~')
        token_dir = os.path.join(appdata, 'tasks_automation')
        try:
            os.makedirs(token_dir, exist_ok=True)
        except OSError:
            token_dir = os.path.expanduser('~')
        return os.path.join(token_dir, 'token.pickle')
    return os.path.join(base_path, properties_dir, 'token.pickle')


def get_oauth_credentials():
    """
    Get valid credentials: either service-account impersonation (no browser)
    or OAuth using stored token / one-time browser login.
    """
    base_path, properties_dir, properties = _get_base_path_and_properties()

    # Optional: use service account to impersonate the user (no browser, Google Workspace only)
    use_sa = (properties.get('USE_SERVICE_ACCOUNT_IMPERSONATION') and
              properties.get('USE_SERVICE_ACCOUNT_IMPERSONATION').data and
              properties.get('USE_SERVICE_ACCOUNT_IMPERSONATION').data.strip().lower() == 'true')
    if use_sa:
        email_prop = properties.get('GOOGLE_EMAIL')
        sa_file_prop = properties.get('SERVICE_ACCOUNT_FILE')
        sa_file = (sa_file_prop.data.strip() if sa_file_prop and sa_file_prop.data
                   else 'calendar-automate-srvc-account-ref-file.json')
        if email_prop and email_prop.data:
            from google.oauth2 import service_account
            sa_path = os.path.join(base_path, properties_dir, sa_file)
            if os.path.exists(sa_path):
                creds = service_account.Credentials.from_service_account_file(
                    sa_path, scopes=SCOPES
                )
                creds = creds.with_subject(email_prop.data.strip())
                return creds
            print("Warning: USE_SERVICE_ACCOUNT_IMPERSONATION is true but service account file not found; falling back to OAuth.")
        else:
            print("Warning: USE_SERVICE_ACCOUNT_IMPERSONATION is true but GOOGLE_EMAIL not set; falling back to OAuth.")

    # OAuth: use client secrets and stored token (browser only when token missing or invalid)
    client_secrets_file = os.path.join(base_path, properties_dir, 'google_desktop_oauth_client_contacts_api.json')
    if not os.path.exists(client_secrets_file):
        print(f"Error: Client secrets file not found at {client_secrets_file}")
        sys.exit(1)

    token_path = _get_writable_token_path(base_path, properties_dir)
    creds = None

    if os.path.exists(token_path):
        try:
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        except Exception as e:
            print(f"Could not load token: {e}")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Token refresh failed: {str(e)}")
                print("Re-authentication required (browser will open once).")
                creds = None
                if os.path.exists(token_path):
                    try:
                        os.remove(token_path)
                    except OSError:
                        pass

        if not creds or not creds.valid:
            print("Opening browser for one-time Google sign-in. Future runs will not prompt.")
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)

        try:
            os.makedirs(os.path.dirname(token_path), exist_ok=True)
        except OSError:
            pass
        try:
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
        except OSError as e:
            print(f"Warning: Could not save token for next run: {e}")

    return creds
