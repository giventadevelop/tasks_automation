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
3. Place your service account JSON key file in the project directory
4. Update the `SERVICE_ACCOUNT_FILE` variable in `calendar_api.py` with your service account file name
5. Set your Anthropic API key in the `ANTHROPIC_API_KEY` variable

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
