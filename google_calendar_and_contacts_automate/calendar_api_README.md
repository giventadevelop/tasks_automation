# Calendar API Script

This script uses the Google Calendar API and Google Drive API to create calendar events and reminders based on information extracted from an image using the Anthropic API.

## Features

- Extract event details from an image using Anthropic's Claude AI
- Create calendar events with the extracted information
- Upload the image to a specific Google Drive folder
- Create reminder events for 1 week before, 1 day before, and at 9:00 AM on the day of the event

## Prerequisites

- Python 3.6+
- Google Cloud project with Calendar API and Drive API enabled
- Service account JSON key file
- Anthropic API key

## Installation

1. Clone the repository
2. Install the required packages:
   ```
   pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client anthropic
   ```
3. **Single config folder**: All config files live in the repo root folder `property_files/` (e.g. `tasks_automation/property_files/`). Do not use a duplicate `property_files` inside this subfolder.
4. Place your service account JSON and other config files in `property_files/` at the repo root.
5. Set your Anthropic API key:
   - In `property_files/calendar_api_properties.properties` as `ANTHROPIC_API_KEY=your-key`, or
   - As environment variable `ANTHROPIC_API_KEY` (takes precedence)

## Authentication (avoiding the browser)

Google Calendar/Drive/People APIs do **not** support login with email + password from a config file. You have two options:

### Option A: OAuth with stored token (default – browser once)

- First run: the app opens your browser once for you to sign in with your Google account and grant access.
- After that, a **refresh token** is stored and used for all future runs, so **no browser is shown again**.
- When running as a script, the token is saved in `property_files/token.pickle`. When running as a built .exe, the token is saved in `%APPDATA%\tasks_automation\token.pickle` so it persists.

### Option B: Service account impersonation (no browser at all, Google Workspace only)

- For **Google Workspace** (organization) accounts only. Does not work for consumer @gmail.com.
- In `calendar_api_properties.properties` add:
  - `USE_SERVICE_ACCOUNT_IMPERSONATION=true`
  - `GOOGLE_EMAIL=your-workspace-user@yourdomain.com`
  - Ensure `SERVICE_ACCOUNT_FILE` points to your service account JSON (or use the default filename).
- A Google Workspace admin must grant **domain-wide delegation** to the service account’s client ID for the required scopes (Calendar, Drive, Contacts). Then the app uses the service account to act as that user with no browser.

## Usage

Run the script using:

```
python calendar_api.py
```

You will be prompted to enter the path to an image file containing event information. The script will then:

1. Extract event details from the image
2. Create a calendar event with the extracted information
3. Upload the image to a "GAIN_SHARED_API" folder in Google Drive
4. Create reminder events for the main event

## Note

Ensure that the service account has the necessary permissions to access and modify the target Google Calendar and Google Drive.
