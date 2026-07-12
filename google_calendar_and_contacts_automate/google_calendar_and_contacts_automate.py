import os
import sys
import base64
import mimetypes
import requests
import json
import calendar
from datetime import datetime, timedelta, timezone
import logging
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from jproperties import Properties
import httpx

from calendar_app_paths import (
    PROPERTY_SUBDIR,
    property_files_locations_hint,
    resolved_property_files_dir,
    resolved_tasks_automation_root,
    task_batch_path,
    task_batch_workdir,
)
from prompt_library import show_prompt_library

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

# Config: exe-side property_files first, then bundled MEIPASS (see calendar_app_paths).
property_dir = resolved_property_files_dir()
properties_dir = PROPERTY_SUBDIR

# Read the properties file
properties = Properties()
properties_path = os.path.join(property_dir, 'calendar_api_properties.properties')

try:
    logging.info(f"Attempting to read properties file from: {properties_path}")
    with open(properties_path, 'rb') as config_file:
        properties.load(config_file)
    logging.info("Successfully loaded properties file")
    _tasks_root_prop = properties.get('TASKS_AUTOMATION_ROOT')
    if _tasks_root_prop and getattr(_tasks_root_prop, 'data', None) and str(_tasks_root_prop.data).strip():
        os.environ.setdefault('TASKS_AUTOMATION_ROOT', str(_tasks_root_prop.data).strip())
except FileNotFoundError:
    error_msg = f"Error: Properties file not found at {properties_path}"
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        error_msg += (
            f"\n\nChecked:\n{property_files_locations_hint()}"
            f"\n\nCreate folder {PROPERTY_SUBDIR} in:\n  {exe_dir}\n"
            "and put calendar_api_properties.properties (and your JSON secrets) there, "
            "then run again."
        )
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
service_account_file = os.path.join(
    property_dir,
    properties.get('SERVICE_ACCOUNT_FILE').data
    if properties.get('SERVICE_ACCOUNT_FILE')
    else 'calendar-automate-srvc-account-ref-file.json',
)

logging.info(f"Service account file path: {service_account_file}")

# Get OAuth2 credentials
credentials = get_oauth_credentials()

# Build the services
calendar_service = build('calendar', 'v3', credentials=credentials)
drive_service = build('drive', 'v3', credentials=credentials)
people_service = build('people', 'v1', credentials=credentials)

# Calendar ID for list/insert/delete (primary user calendar)
CALENDAR_ID = 'giventauser@gmail.com'


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
            calendarId=CALENDAR_ID,
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


def get_upcoming_events_for_deletion(max_results=30):
    """Fetch upcoming events for the delete dialog. Returns list of dicts with id, summary, start_str, recurringEventId."""
    try:
        events_result = calendar_service.events().list(
            calendarId=CALENDAR_ID,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime',
            timeMin=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        ).execute(num_retries=3)
        events = events_result.get('items', [])
        out = []
        for event in events:
            start = event.get('start', {})
            start_str = start.get('dateTime', start.get('date', ''))
            if start_str and 'T' in start_str:
                try:
                    dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                    start_str = dt.strftime('%Y-%m-%d %H:%M')
                except Exception:
                    pass
            out.append({
                'id': event['id'],
                'summary': event.get('summary', '(No title)'),
                'start_str': start_str or '(No date)',
                'recurringEventId': event.get('recurringEventId'),
            })
        return out
    except Exception as e:
        logging.error(f"Error fetching events for deletion: {e}")
        raise


# Reminder events created by this app use this pattern in the summary
REMINDER_SUMMARY_MARKER = " - Reminder: "


def _event_name_for_reminder_match(selected_event_summary):
    """
    Extract the event name used to find related reminders.
    Main event format:  "EventName - 2026 March 17 (Tuesday)"
    Reminder format:    "2026 March 17 (Tuesday) - Reminder: EventName"
    We match reminders by EventName so we find them when deleting either the main event or a reminder.
    """
    if not selected_event_summary:
        return ""
    s = selected_event_summary.strip()
    if REMINDER_SUMMARY_MARKER in s:
        return s.split(REMINDER_SUMMARY_MARKER, 1)[-1].strip()
    if " - " in s:
        return s.split(" - ", 1)[0].strip()
    return s


def _list_reminder_event_ids_for_main_event(selected_event_summary):
    """Find calendar event IDs for our app-created reminders (week/day/day-of) for this event."""
    event_name = _event_name_for_reminder_match(selected_event_summary)
    if not event_name:
        return []
    ids = set()  # use set to avoid deleting the same event twice (e.g. if selected item is a reminder)
    try:
        now_utc = datetime.now(timezone.utc)
        time_min = (now_utc - timedelta(days=30)).isoformat().replace('+00:00', 'Z')
        time_max = (now_utc + timedelta(days=400)).isoformat().replace('+00:00', 'Z')
        page_token = None
        while True:
            result = calendar_service.events().list(
                calendarId=CALENDAR_ID,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime',
                pageToken=page_token,
                maxResults=250,
            ).execute(num_retries=3)
            for event in result.get('items', []):
                summary = event.get('summary', '')
                # Match our reminder events: they contain " - Reminder: " and the event name (e.g. "test1")
                if REMINDER_SUMMARY_MARKER in summary and event_name in summary:
                    ids.add(event['id'])
            page_token = result.get('nextPageToken')
            if not page_token:
                break
    except Exception as e:
        logging.warning(f"Could not list reminder events for '{event_name}': {e}")
    return list(ids)


def delete_calendar_event(event_id, send_updates='all', event_summary=None):
    """Delete a calendar event. If event_summary is provided, first deletes app-created reminder events for it."""
    def do_delete(eid):
        try:
            calendar_service.events().delete(
                calendarId=CALENDAR_ID,
                eventId=eid,
                sendUpdates=send_updates,
            ).execute(num_retries=3)
            return True
        except HttpError as e:
            if e.resp.status == 410:
                logging.info(f"Event {eid} already deleted (410), skipping")
                return True
            raise
        except Exception as e:
            logging.warning(f"Could not delete event {eid}: {e}")
            return False

    if event_summary:
        reminder_ids = _list_reminder_event_ids_for_main_event(event_summary)
        for rid in reminder_ids:
            if do_delete(rid):
                logging.info(f"Deleted reminder event: {rid}")
    # Delete the selected event (main or reminder); 410 = already gone, treat as success
    try:
        if do_delete(event_id):
            logging.info(f"Deleted calendar event: {event_id}")
    except HttpError as e:
        if e.resp.status == 410:
            logging.info(f"Event {event_id} already deleted (410)")
        else:
            raise


def ensure_credentials_file():
    if not os.path.exists('credentials.json'):
        print("credentials.json not found. Please make sure you have the correct client configuration file.")
        raise FileNotFoundError("credentials.json is missing")
    else:
        print("credentials.json found.")


# Anthropic API key will be read from .env file at runtime


def show_delete_calendar_dialog():
    """Dialog to pick an upcoming event and delete it (and its reminders). Recurring: delete one or full series."""
    root = tk.Tk()
    root.withdraw()
    dialog = tk.Toplevel(root)
    dialog.title("Delete Calendar Entry")
    dialog.configure(bg='#ecf0f1')

    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    dialog_width = min(500, int(screen_width * 2/5))
    dialog_height = min(450, int(screen_height * 1/2))

    tk.Label(dialog, text="Select an event to delete (reminders are removed with the event):",
             bg='#ecf0f1', font=('Helvetica', 10)).pack(pady=(10, 2))
    tk.Label(dialog, text="Click an event in the list, then click \"Delete this event\" or \"Delete entire series\".",
             bg='#ecf0f1', font=('Helvetica', 9), fg='#7f8c8d').pack(pady=(0, 5))

    list_frame = tk.Frame(dialog, bg='#ecf0f1')
    list_frame.pack(fill='both', expand=True, padx=10, pady=5)
    scrollbar = tk.Scrollbar(list_frame)
    scrollbar.pack(side='right', fill='y')
    listbox = tk.Listbox(list_frame, height=12, font=('Consolas', 10),
                        yscrollcommand=scrollbar.set, selectmode='single')
    listbox.pack(side='left', fill='both', expand=True)
    scrollbar.config(command=listbox.yview)

    events_list = []
    try:
        events_list = get_upcoming_events_for_deletion(max_results=50)
    except Exception as e:
        messagebox.showerror("Error", f"Could not load events:\n{str(e)}", parent=dialog)
        dialog.destroy()
        root.destroy()
        return

    if not events_list:
        tk.Label(dialog, text="No upcoming events found.", bg='#ecf0f1', fg='#7f8c8d').pack(pady=10)
    else:
        for ev in events_list:
            listbox.insert(tk.END, f"  {ev['start_str']}  |  {ev['summary']}")

    # Keep last selected index (selection can be lost when a button takes focus)
    last_selected_index = [None]

    def on_list_select(event):
        sel = listbox.curselection()
        if sel:
            last_selected_index[0] = int(sel[0])

    listbox.bind('<<ListboxSelect>>', on_list_select)

    def get_selected_event():
        sel = listbox.curselection()
        idx = int(sel[0]) if sel else last_selected_index[0]
        if idx is not None and 0 <= idx < len(events_list):
            return events_list[idx]
        return None

    def do_delete(this_occurrence_only=True):
        ev = get_selected_event()
        if not ev:
            messagebox.showwarning("Select event", "Please select an event from the list.", parent=dialog)
            return
        event_id = ev['id'] if this_occurrence_only else ev.get('recurringEventId') or ev['id']
        if not this_occurrence_only and not ev.get('recurringEventId'):
            messagebox.showinfo("Not recurring", "This event is not part of a series.", parent=dialog)
            return
        msg = "Delete this occurrence only?" if (this_occurrence_only and ev.get('recurringEventId')) else (
            "Delete the entire series (all occurrences)?" if ev.get('recurringEventId') else "Delete this event?"
        )
        # Use custom confirm dialog so it appears on top and is clearly visible
        dialog.grab_release()
        confirm_result = [None]  # use list so inner function can set it

        confirm_win = tk.Toplevel(root)
        confirm_win.title("Confirm delete")
        confirm_win.configure(bg='#ecf0f1')
        f = tk.Frame(confirm_win, bg='#ecf0f1', padx=24, pady=20)
        f.pack(fill='both', expand=True)
        tk.Label(f, text=msg, wraplength=340, padx=8, pady=12, bg='#ecf0f1',
                 font=('Helvetica', 11)).pack()
        btn_frame = tk.Frame(f, bg='#ecf0f1')
        btn_frame.pack(pady=(12, 0))

        def on_yes():
            confirm_result[0] = True
            confirm_win.destroy()

        def on_no():
            confirm_result[0] = False
            confirm_win.destroy()

        tk.Button(btn_frame, text="Yes, delete", command=on_yes, width=12,
                  bg='#e74c3c', fg='white').pack(side='left', padx=8)
        tk.Button(btn_frame, text="Cancel", command=on_no, width=12).pack(side='left', padx=8)
        confirm_win.geometry("400x160")
        # Center on screen and force on top so it is never hidden
        confirm_win.update_idletasks()
        w, h = 400, 160
        x = (screen_width - w) // 2
        y = (screen_height - h) // 2
        confirm_win.geometry(f'{w}x{h}+{x}+{y}')
        confirm_win.attributes('-topmost', True)
        confirm_win.lift()
        confirm_win.focus_force()
        confirm_win.update_idletasks()
        confirm_win.grab_set()
        confirm_win.wait_window()
        dialog.grab_set()

        if not confirm_result[0]:
            return
        try:
            delete_calendar_event(event_id, event_summary=ev.get('summary'))
            # Release grab and close delete dialog before showing success (avoid "grab failed")
            dialog.grab_release()
            dialog.destroy()
            try:
                root.destroy()
            except Exception:
                pass
            show_success_dialog("Deleted", "Calendar entry and its reminders were deleted.")
        except Exception as e:
            logging.error(f"Delete calendar event failed: {e}")
            messagebox.showerror("Error", f"Failed to delete event:\n{str(e)}", parent=dialog)

    btn_frame = tk.Frame(dialog, bg='#ecf0f1')
    btn_frame.pack(fill='x', padx=10, pady=10)

    def go_home():
        dialog.destroy()
        try:
            root.destroy()
        except Exception:
            pass

    tk.Button(btn_frame, text="Delete this event", bg='#e74c3c', fg='white',
              command=lambda: do_delete(this_occurrence_only=True), width=18).pack(side='left', padx=4)
    tk.Button(btn_frame, text="Delete entire series", bg='#c0392b', fg='white',
              command=lambda: do_delete(this_occurrence_only=False), width=18).pack(side='left', padx=4)
    tk.Button(btn_frame, text="Back to home", bg='#3498db', fg='white',
              command=go_home, width=14).pack(side='right', padx=4)
    tk.Button(btn_frame, text="Cancel", command=go_home, width=10).pack(side='right', padx=4)

    x = (screen_width - dialog_width) // 2
    y = (screen_height - dialog_height) // 2
    dialog.geometry(f'{dialog_width}x{dialog_height}+{x}+{y}')
    dialog.lift()
    dialog.focus_force()
    dialog.grab_set()
    dialog.wait_window()
    try:
        root.destroy()
    except Exception:
        pass


def show_initial_dialog():
    root = tk.Tk()
    root.withdraw()
    dialog = tk.Toplevel(root)
    dialog.title("")  # Empty title as we'll use custom title bar

    # Calculate screen dimensions and desired dialog size
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    dialog_width = int(screen_width * 3/8)
    dialog_height = int(screen_height * 0.72)  # room for task buttons + prompt library

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

    def on_whatsapp_poll():
        result['choice'] = 'whatsapp_poll'
        dialog.destroy()

    def on_whatsapp_low_turnout():
        result['choice'] = 'whatsapp_low_turnout'
        dialog.destroy()

    def on_youtube_transcribe():
        result['choice'] = 'youtube_transcribe'
        dialog.destroy()

    def on_prune_transcripts():
        result['choice'] = 'prune_transcripts'
        dialog.destroy()

    def on_delete_calendar():
        result['choice'] = 'delete_calendar'
        dialog.destroy()

    def on_prompt_library():
        result['choice'] = 'prompt_library'
        dialog.destroy()

    def on_exit():
        result['choice'] = None
        dialog.destroy()

    # Create and style buttons
    calendar_btn = tk.Button(content_frame, text="Calendar Entry",
                           bg='#3498db', fg='white',
                           activebackground='#2980b9',
                           command=on_calendar, **button_style)
    calendar_btn.pack(pady=10)

    delete_calendar_btn = tk.Button(content_frame, text="Delete Calendar Entry",
                                   bg='#9b59b6', fg='white',
                                   activebackground='#8e44ad',
                                   command=on_delete_calendar, **button_style)
    delete_calendar_btn.pack(pady=10)

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

    whatsapp_poll_btn = tk.Button(content_frame, text="WhatsApp Poll (manual)",
                                  bg='#128C7E', fg='white',
                                  activebackground='#075E54',
                                  command=on_whatsapp_poll, **button_style)
    whatsapp_poll_btn.pack(pady=8)

    whatsapp_turnout_btn = tk.Button(
        content_frame,
        text="Volleyball Low Turnout (Friday)",
        bg='#0B6E4F',
        fg='white',
        activebackground='#084C35',
        command=on_whatsapp_low_turnout,
        **button_style,
    )
    whatsapp_turnout_btn.pack(pady=8)

    youtube_btn = tk.Button(content_frame, text="YouTube Transcribe",
                           bg='#e67e22', fg='white',
                           activebackground='#d35400',
                           command=on_youtube_transcribe, **button_style)
    youtube_btn.pack(pady=10)

    prune_btn = tk.Button(content_frame, text="Cleanup Transcripts",
                         bg='#16a085', fg='white',
                         activebackground='#1abc9c',
                         command=on_prune_transcripts, **button_style)
    prune_btn.pack(pady=10)

    prompt_lib_btn = tk.Button(
        content_frame,
        text="Prompt Library",
        bg='#1abc9c',
        fg='white',
        activebackground='#16a085',
        command=on_prompt_library,
        **button_style,
    )
    prompt_lib_btn.pack(pady=10)

    exit_btn = tk.Button(content_frame, text="Exit",
                         bg='#95a5a6', fg='white',
                         activebackground='#7f8c8d',
                         command=on_exit, **button_style)
    exit_btn.pack(pady=10)

    # Center dialog
    x = (screen_width - dialog_width) // 2
    y = (screen_height - dialog_height) // 2
    dialog.geometry(f'{dialog_width}x{dialog_height}+{x}+{y}')

    # Make dialog modal
    dialog.grab_set()
    dialog.wait_window()
    root.destroy()

    return result['choice']


def launch_task_batch_in_console(bat_path, work_dir, extra_env=None):
    """Start a .bat in a new console (Windows). extra_env values may be empty strings."""
    import subprocess
    env = os.environ.copy()
    if extra_env:
        for key, value in extra_env.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
    if sys.platform != 'win32':
        raise OSError('Console batch launch is supported on Windows only')
    subprocess.Popen(
        ['cmd.exe', '/c', 'start', '', 'cmd.exe', '/k', bat_path],
        cwd=work_dir,
        env=env,
    )


def get_whatsapp_poll_options():
    """Dashboard prompts for manual WhatsApp poll. Returns (contact, send_real) or None."""
    root = tk.Tk()
    root.withdraw()
    dialog = tk.Toplevel(root)
    dialog.title("WhatsApp Poll")
    dialog.configure(bg='#ecf0f1')
    dialog.resizable(False, False)

    frame = tk.Frame(dialog, bg='#ecf0f1', padx=20, pady=16)
    frame.pack(fill='both', expand=True)

    tk.Label(
        frame,
        text="WhatsApp poll — manual run",
        bg='#ecf0f1',
        font=('Helvetica', 12, 'bold'),
    ).pack(anchor='w', pady=(0, 8))

    tk.Label(
        frame,
        text="Contact / chat name to search:",
        bg='#ecf0f1',
        font=('Helvetica', 10),
    ).pack(anchor='w')
    contact_entry = tk.Entry(frame, width=42, font=('Helvetica', 11))
    contact_entry.insert(0, 'Volleyball Friday')
    contact_entry.pack(anchor='w', pady=(4, 12))

    tk.Label(
        frame,
        text="Send mode:",
        bg='#ecf0f1',
        font=('Helvetica', 10),
    ).pack(anchor='w')
    send_mode = tk.StringVar(value='send')
    modes = tk.Frame(frame, bg='#ecf0f1')
    modes.pack(anchor='w', pady=(4, 12))
    tk.Radiobutton(
        modes, text='Send for real', variable=send_mode, value='send',
        bg='#ecf0f1', font=('Helvetica', 10),
    ).pack(anchor='w')
    tk.Radiobutton(
        modes, text='Dry-run (fill poll, do not click Send)', variable=send_mode, value='dry',
        bg='#ecf0f1', font=('Helvetica', 10),
    ).pack(anchor='w')

    result = {'value': None}

    def on_run():
        contact = contact_entry.get().strip() or 'Volleyball Friday'
        send_real = send_mode.get() == 'send'
        result['value'] = (contact, send_real)
        dialog.destroy()

    def on_cancel():
        dialog.destroy()

    btn_row = tk.Frame(frame, bg='#ecf0f1')
    btn_row.pack(pady=(8, 0))
    tk.Button(
        btn_row, text='Run', width=10, bg='#128C7E', fg='white',
        command=on_run,
    ).pack(side='left', padx=4)
    tk.Button(btn_row, text='Cancel', width=10, command=on_cancel).pack(side='left', padx=4)

    dialog.protocol('WM_DELETE_WINDOW', on_cancel)
    dialog.update_idletasks()
    w, h = dialog.winfo_width(), dialog.winfo_height()
    sw, sh = dialog.winfo_screenwidth(), dialog.winfo_screenheight()
    dialog.geometry(f'+{(sw - w) // 2}+{(sh - h) // 2}')
    dialog.grab_set()
    dialog.wait_window()
    root.destroy()
    return result['value']


def get_whatsapp_turnout_options():
    """Dashboard prompts for low-turnout flow. Returns (mode, contact, send_real) or None.

    mode: 'check' (read poll, cancel if Yes < 6) or 'send' (always send cancel message)
    """
    root = tk.Tk()
    root.withdraw()
    dialog = tk.Toplevel(root)
    dialog.title("Volleyball Low Turnout")
    dialog.configure(bg='#ecf0f1')
    dialog.resizable(False, False)

    frame = tk.Frame(dialog, bg='#ecf0f1', padx=20, pady=16)
    frame.pack(fill='both', expand=True)

    tk.Label(
        frame,
        text="Volleyball low turnout",
        bg='#ecf0f1',
        font=('Helvetica', 12, 'bold'),
    ).pack(anchor='w', pady=(0, 8))

    tk.Label(
        frame,
        text="Action:",
        bg='#ecf0f1',
        font=('Helvetica', 10),
    ).pack(anchor='w')
    action_mode = tk.StringVar(value='check')
    modes = tk.Frame(frame, bg='#ecf0f1')
    modes.pack(anchor='w', pady=(4, 12))
    tk.Radiobutton(
        modes,
        text='Check latest poll — send cancel if fewer than 6 Yes votes',
        variable=action_mode,
        value='check',
        bg='#ecf0f1',
        font=('Helvetica', 10),
        wraplength=420,
        justify='left',
    ).pack(anchor='w')
    tk.Radiobutton(
        modes,
        text='Send cancel message now (skip poll read)',
        variable=action_mode,
        value='send',
        bg='#ecf0f1',
        font=('Helvetica', 10),
        wraplength=420,
        justify='left',
    ).pack(anchor='w')

    tk.Label(
        frame,
        text="Contact / group name:",
        bg='#ecf0f1',
        font=('Helvetica', 10),
    ).pack(anchor='w')
    contact_entry = tk.Entry(frame, width=42, font=('Helvetica', 11))
    contact_entry.insert(0, 'Volleyball Friday')
    contact_entry.pack(anchor='w', pady=(4, 12))

    tk.Label(
        frame,
        text="Send mode:",
        bg='#ecf0f1',
        font=('Helvetica', 10),
    ).pack(anchor='w')
    send_mode = tk.StringVar(value='send')
    send_row = tk.Frame(frame, bg='#ecf0f1')
    send_row.pack(anchor='w', pady=(4, 12))
    tk.Radiobutton(
        send_row, text='Send for real', variable=send_mode, value='send',
        bg='#ecf0f1', font=('Helvetica', 10),
    ).pack(anchor='w')
    tk.Radiobutton(
        send_row, text='Dry-run (do not click Send)', variable=send_mode, value='dry',
        bg='#ecf0f1', font=('Helvetica', 10),
    ).pack(anchor='w')

    result = {'value': None}

    def on_run():
        contact = contact_entry.get().strip() or 'Volleyball Friday'
        send_real = send_mode.get() == 'send'
        result['value'] = (action_mode.get(), contact, send_real)
        dialog.destroy()

    def on_cancel():
        dialog.destroy()

    btn_row = tk.Frame(frame, bg='#ecf0f1')
    btn_row.pack(pady=(8, 0))
    tk.Button(
        btn_row, text='Run', width=10, bg='#0B6E4F', fg='white',
        command=on_run,
    ).pack(side='left', padx=4)
    tk.Button(btn_row, text='Cancel', width=10, command=on_cancel).pack(side='left', padx=4)

    dialog.protocol('WM_DELETE_WINDOW', on_cancel)
    dialog.update_idletasks()
    w, h = dialog.winfo_width(), dialog.winfo_height()
    sw, sh = dialog.winfo_screenwidth(), dialog.winfo_screenheight()
    dialog.geometry(f'+{(sw - w) // 2}+{(sh - h) // 2}')
    dialog.grab_set()
    dialog.wait_window()
    root.destroy()
    return result['value']


def confirm_laundry_launch():
    """Dashboard confirmation before starting laundry flow."""
    root = tk.Tk()
    root.withdraw()
    ok = messagebox.askyesno(
        'Laundry',
        'Start the TryCents laundry order flow in Microsoft Edge?\n\n'
        'The automation stops at Order Summary — review the order and click Submit yourself.',
    )
    root.destroy()
    return ok


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

def _get_message_text(message):
    """Extract raw text from Anthropic API message content (handles different response shapes)."""
    if not message.content:
        return ""
    text_parts = []
    for block in message.content:
        if hasattr(block, "text"):
            text_parts.append(block.text)
        elif isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(block.get("text", ""))
    return "".join(text_parts).strip()


def _parse_json_from_response(raw_text):
    """Parse JSON from model response, handling markdown code blocks and extra text."""
    if not raw_text:
        raise ValueError("Empty response from model")
    text = raw_text.strip()
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Extract JSON object (first { to matching })
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object in response: {text[:200]!r}")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                json_str = text[start : i + 1]
                # Remove common markdown/code block wrapping
                if json_str.startswith("```"):
                    lines = json_str.split("\n")
                    json_str = "\n".join(l for l in lines if not l.strip().startswith("```"))
                return json.loads(json_str)
    raise ValueError(f"Unbalanced braces in response: {text[:200]!r}")


def _get_anthropic_api_key():
    """Get Anthropic API key from environment variable ANTHROPIC_API_KEY."""
    key = os.environ.get('ANTHROPIC_API_KEY', '').strip()
    if not key:
        raise ValueError(
            "ANTHROPIC_API_KEY is not set. Set the ANTHROPIC_API_KEY environment variable."
        )
    return key


def extract_contact_details(contact_text):
    try:
        api_key = _get_anthropic_api_key()
        client = anthropic.Anthropic(api_key=api_key)

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
                model="claude-sonnet-4-6",
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

        result = _get_message_text(message)
        contact_details = _parse_json_from_response(result)

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


_CALENDAR_IMAGE_FILETYPES = [
    ("Image files", "*.png *.jpg *.jpeg *.jfif *.jpe *.gif *.bmp *.webp"),
    ("JPEG / JFIF", "*.jpg *.jpeg *.jfif *.jpe"),
    ("PNG", "*.png"),
    ("All files", "*.*"),
]


def _image_media_type(image_path):
    """MIME type for Claude vision / calendar attachments (JFIF → image/jpeg)."""
    ext = os.path.splitext(image_path)[1].lower()
    by_ext = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".jfif": "image/jpeg",
        ".jpe": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    if ext in by_ext:
        return by_ext[ext]
    guessed, _ = mimetypes.guess_type(image_path)
    return guessed or "image/jpeg"


def _pick_calendar_image_file(title="Select image file"):
    return filedialog.askopenfilename(title=title, filetypes=_CALENDAR_IMAGE_FILETYPES)


def get_event_input():
    """Ask how to supply event details: typed text vs image to parse with AI."""
    root = tk.Tk()
    root.withdraw()
    dialog = tk.Toplevel(root)
    dialog.title("New Calendar Entry")
    dialog.configure(bg="#ecf0f1")
    dialog.resizable(False, False)

    frame = tk.Frame(dialog, bg="#ecf0f1", padx=20, pady=16)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame,
        text="How do you want to add this event?",
        bg="#ecf0f1",
        font=("Helvetica", 12, "bold"),
    ).pack(anchor="w", pady=(0, 8))

    tk.Label(
        frame,
        text=(
            "Choose one:\n"
            "• Text — type or paste details (flyer text, message, notes)\n"
            "• Image — upload a photo or screenshot (e.g. WhatsApp .jfif) "
            "and AI will read it"
        ),
        bg="#ecf0f1",
        font=("Helvetica", 10),
        justify="left",
        wraplength=420,
    ).pack(anchor="w", pady=(0, 12))

    input_mode = tk.StringVar(value="text")

    modes = tk.Frame(frame, bg="#ecf0f1")
    modes.pack(anchor="w", pady=(0, 8))
    tk.Radiobutton(
        modes,
        text="Type or paste text only",
        variable=input_mode,
        value="text",
        bg="#ecf0f1",
        font=("Helvetica", 10),
        anchor="w",
    ).pack(anchor="w")
    tk.Radiobutton(
        modes,
        text="Upload an image to parse (photo / screenshot / WhatsApp image)",
        variable=input_mode,
        value="image",
        bg="#ecf0f1",
        font=("Helvetica", 10),
        anchor="w",
    ).pack(anchor="w")

    result = {"value": None}

    def on_continue():
        result["value"] = input_mode.get()
        dialog.destroy()

    def on_cancel():
        dialog.destroy()

    btn_row = tk.Frame(frame, bg="#ecf0f1")
    btn_row.pack(pady=(12, 0))
    tk.Button(
        btn_row, text="Continue", width=12, bg="#3498db", fg="white", command=on_continue,
    ).pack(side="left", padx=4)
    tk.Button(btn_row, text="Cancel", width=10, command=on_cancel).pack(side="left", padx=4)

    dialog.protocol("WM_DELETE_WINDOW", on_cancel)
    dialog.update_idletasks()
    w, h = dialog.winfo_width(), dialog.winfo_height()
    sw, sh = dialog.winfo_screenwidth(), dialog.winfo_screenheight()
    dialog.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")
    dialog.grab_set()
    dialog.wait_window()
    root.destroy()

    mode = result["value"]
    if not mode:
        print("Calendar entry cancelled.")
        sys.exit(0)

    if mode == "image":
        root = tk.Tk()
        root.withdraw()
        image_path = _pick_calendar_image_file(
            title="Select image to parse (JPEG, JFIF, PNG, …)",
        )
        root.destroy()
        if not image_path:
            print("No file selected. Exiting.")
            sys.exit(1)
        print(f"Selected file: {image_path}")
        return "image", None, image_path

    # Text path
    root = tk.Tk()
    root.withdraw()
    text_dialog = tk.Toplevel(root)
    text_dialog.title("Event details — type or paste")
    tk.Label(
        text_dialog,
        text="Enter or paste event details (name, date, time, venue, contacts):",
        font=("Helvetica", 10),
    ).pack(padx=10, pady=(10, 4), anchor="w")
    text_area = tk.Text(text_dialog, width=60, height=20)
    text_area.pack(padx=10, pady=4)

    event_text = ""

    def on_ok():
        nonlocal event_text
        event_text = text_area.get("1.0", tk.END).strip()
        text_dialog.destroy()

    ok_button = tk.Button(text_dialog, text="OK", command=on_ok)
    ok_button.pack(pady=10)
    text_dialog.geometry("500x650")
    text_dialog.grab_set()
    text_dialog.wait_window()
    root.destroy()

    if not event_text:
        print("No event details entered. Exiting.")
        sys.exit(1)

    attach = messagebox.askyesno(
        "Attach image to calendar?",
        "Also attach an image file to this Google Calendar event?\n\n"
        "Choose Yes only if you want the file stored with the event "
        "(optional). This is separate from parsing text above.",
    )
    image_path = None
    if attach:
        root = tk.Tk()
        root.withdraw()
        image_path = _pick_calendar_image_file(
            title="Select image to attach to calendar event",
        )
        root.destroy()

    return "text", event_text, image_path


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def extract_event_details(input_type, event_text, image_path):
    global event_details
    try:
        # Read API key from environment variable only
        api_key = os.environ.get('ANTHROPIC_API_KEY', '').strip()
        if not api_key:
            error_msg = (
                "ANTHROPIC_API_KEY is not set. Set the ANTHROPIC_API_KEY environment variable."
            )
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
            media_type = _image_media_type(image_path)
            message = client.messages.create(
                model="claude-sonnet-4-6",
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
                                    "media_type": media_type,
                                    "data": base64_image
                                }
                            }
                        ]
                    }
                ]
            )
        else:  # input_type == "text"
            message = client.messages.create(
                model="claude-sonnet-4-6",
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

        result = _get_message_text(message)
        try:
            event_details = _parse_json_from_response(result)
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

        except (ValueError, json.JSONDecodeError) as e:
            logging.error(f"Failed to parse model response: {e}")
            event_details = {
                'eventName': 'Unnamed Event',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'startTime': '09:30 AM',
                'endTime': '10:30 AM',
                'venue': '@home_default',
                'contacts': [{'name': 'Default Contact', 'phone': 'N/A'}],
                'otherDetails': 'No additional details provided'
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

        # event_details already confirmed in extract_event_details; no second dialog

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

    # Button frame: OK and Back to home
    success_btn_frame = tk.Frame(content_frame, bg='#ecf0f1')
    success_btn_frame.pack(pady=(0, 20))

    def close_success():
        dialog.destroy()
        root.destroy()

    ok_button = tk.Button(success_btn_frame, text="OK",
                         bg='#3498db', fg='white',
                         activebackground='#2980b9',
                         font=('Helvetica', 12, 'bold'),
                         width=12, height=1,
                         relief='raised',
                         borderwidth=3,
                         command=close_success)
    ok_button.pack(side='left', padx=8)

    back_home_btn = tk.Button(success_btn_frame, text="Back to home",
                              bg='#2ecc71', fg='white',
                              activebackground='#27ae60',
                              font=('Helvetica', 12, 'bold'),
                              width=14, height=1,
                              relief='raised',
                              borderwidth=3,
                              command=close_success)
    back_home_btn.pack(side='left', padx=8)

    # Center dialog
    x = (screen_width - dialog_width) // 2
    y = (screen_height - dialog_height) // 2
    dialog.geometry(f'{dialog_width}x{dialog_height}+{x}+{y}')

    # Make dialog modal
    dialog.grab_set()
    dialog.wait_window()
    try:
        root.destroy()
    except Exception:
        pass


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

    # Create a frame for the buttons
    button_frame = tk.Frame(content_frame, bg='#ecf0f1')
    button_frame.pack(pady=(0, 20))

    def close_contact_url():
        dialog.destroy()
        root.destroy()

    # Styled OK and Back to home buttons
    ok_button = tk.Button(button_frame, text="OK",
                         bg='#3498db', fg='white',
                         activebackground='#2980b9',
                         font=('Helvetica', 16, 'bold'),
                         width=25, height=2,
                         relief='raised',
                         borderwidth=4,
                         cursor='hand2',
                         command=close_contact_url)
    ok_button.pack(pady=10, ipady=10)

    back_home_btn = tk.Button(button_frame, text="Back to home",
                              bg='#2ecc71', fg='white',
                              activebackground='#27ae60',
                              font=('Helvetica', 14, 'bold'),
                              width=20, height=2,
                              relief='raised',
                              borderwidth=4,
                              cursor='hand2',
                              command=close_contact_url)
    back_home_btn.pack(pady=6)

    # Add hover effect for OK
    def on_enter(e):
        ok_button['background'] = '#2980b9'
    def on_leave(e):
        ok_button['background'] = '#3498db'
    ok_button.bind("<Enter>", on_enter)
    ok_button.bind("<Leave>", on_leave)

    # Center dialog
    x = (screen_width - dialog_width) // 2
    y = (screen_height - dialog_height) // 2
    dialog.geometry(f'{dialog_width}x{dialog_height}+{x}+{y}')

    # Make dialog modal
    dialog.grab_set()
    dialog.wait_window()
    try:
        root.destroy()
    except Exception:
        pass


def main():
    try:
        global event_details
        while True:
            choice = show_initial_dialog()
            if choice is None:
                break

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

                # Show success message (OK or Back to home returns to initial dialog)
                show_success_dialog("Success", "Calendar entry added successfully!")

            elif choice == 'delete_calendar':
                show_delete_calendar_dialog()

            elif choice == 'prompt_library':
                show_prompt_library()

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
                tasks_root = resolved_tasks_automation_root()
                laundry_path = os.path.join(tasks_root, 'Laundry_TryCents')
                bat_path = task_batch_path('laundry', 'run_laundry.bat')
                bat_workdir = task_batch_workdir('laundry')
                if not os.path.isfile(bat_path):
                    messagebox.showerror(
                        "Error",
                        "Laundry launcher not found:\n"
                        f"{bat_path}\n\n"
                        "Set environment variable TASKS_AUTOMATION_ROOT to your tasks_automation "
                        "folder (the one that contains scripts_batch_files), or place that checkout at "
                        "tasks_automation next to this .exe, then try again.",
                    )
                    continue
                if not confirm_laundry_launch():
                    continue
                try:
                    if sys.platform == 'win32':
                        launch_task_batch_in_console(bat_path, bat_workdir)
                    else:
                        laundry_main = os.path.join(laundry_path, 'laundry_automation.py')
                        if os.path.isfile(laundry_main):
                            import subprocess
                            subprocess.Popen([sys.executable, laundry_main], cwd=laundry_path)
                        else:
                            messagebox.showerror("Error", f"No Windows .bat and no {laundry_main}")
                            continue
                    logging.info("Launched Laundry via run_laundry.bat")
                    messagebox.showinfo(
                        "Laundry Automation",
                        "Laundry started in a new console (run_laundry.bat).\n\n"
                        "Watch Edge for the TryCents flow. Verify TASKS_AUTOMATION_ROOT if nothing appears.",
                    )
                except Exception as e:
                    logging.error(f"Failed to start laundry automation: {e}")
                    messagebox.showerror("Error", f"Could not start laundry automation:\n{str(e)}")

            elif choice == 'whatsapp_poll':
                tasks_root = resolved_tasks_automation_root()
                poll_path = os.path.join(tasks_root, 'WhatsApp_Web_Poll')
                bat_path = task_batch_path('whatsapp_poll', 'run_whatsapp_poll.bat')
                bat_workdir = task_batch_workdir('whatsapp_poll')
                if not os.path.isfile(bat_path):
                    messagebox.showerror(
                        "Error",
                        "WhatsApp poll launcher not found:\n"
                        f"{bat_path}\n\n"
                        "Set environment variable TASKS_AUTOMATION_ROOT to your tasks_automation "
                        "folder (the one that contains scripts_batch_files), or place that checkout at "
                        "tasks_automation next to this app, then try again.",
                    )
                    continue
                poll_opts = get_whatsapp_poll_options()
                if not poll_opts:
                    continue
                contact, send_real = poll_opts
                try:
                    if sys.platform == 'win32':
                        launch_task_batch_in_console(
                            bat_path,
                            bat_workdir,
                            extra_env={
                                'SKIP_PROMPTS': '1',
                                'CONTACT': contact,
                                'SEND': '1' if send_real else '',
                            },
                        )
                    else:
                        poll_main = os.path.join(poll_path, 'whatsapp_poll.py')
                        if os.path.isfile(poll_main):
                            import subprocess
                            env = os.environ.copy()
                            env['CONTACT'] = contact
                            env['SEND'] = '1' if send_real else ''
                            subprocess.Popen([sys.executable, poll_main], cwd=poll_path, env=env)
                        else:
                            messagebox.showerror("Error", f"No Windows .bat and no {poll_main}")
                            continue
                    mode = 'real send' if send_real else 'dry-run'
                    logging.info("Launched WhatsApp poll contact=%r mode=%s", contact, mode)
                    messagebox.showinfo(
                        "WhatsApp Poll",
                        f"WhatsApp poll started in a new console.\n\n"
                        f"Contact: {contact}\nMode: {mode}\n\n"
                        "Ensure Edge is logged in at web.whatsapp.com (C:\\edge-cdp profile).",
                    )
                except Exception as e:
                    logging.error(f"Failed to start WhatsApp poll: {e}")
                    messagebox.showerror("Error", f"Could not start WhatsApp poll:\n{str(e)}")

            elif choice == 'whatsapp_low_turnout':
                tasks_root = resolved_tasks_automation_root()
                poll_path = os.path.join(tasks_root, 'WhatsApp_Web_Poll')
                turnout_opts = get_whatsapp_turnout_options()
                if not turnout_opts:
                    continue
                mode, contact, send_real = turnout_opts
                bat_name = (
                    'run_whatsapp_turnout_check.bat'
                    if mode == 'check'
                    else 'run_whatsapp_low_turnout_cancel.bat'
                )
                bat_path = task_batch_path('whatsapp_poll', bat_name)
                bat_workdir = task_batch_workdir('whatsapp_poll')
                if not os.path.isfile(bat_path):
                    messagebox.showerror(
                        "Error",
                        f"WhatsApp turnout launcher not found:\n{bat_path}",
                    )
                    continue
                try:
                    if sys.platform == 'win32':
                        launch_task_batch_in_console(
                            bat_path,
                            bat_workdir,
                            extra_env={
                                'SKIP_PROMPTS': '1',
                                'CONTACT': contact,
                                'SEND': '1' if send_real else '',
                                'MIN_PLAYERS': '6',
                            },
                        )
                    else:
                        poll_main = os.path.join(poll_path, 'whatsapp_poll.py')
                        if os.path.isfile(poll_main):
                            import subprocess
                            env = os.environ.copy()
                            env['CONTACT'] = contact
                            env['SEND'] = '1' if send_real else ''
                            env['MIN_PLAYERS'] = '6'
                            env['ACTION'] = (
                                'check_turnout' if mode == 'check'
                                else 'send_low_turnout_cancel'
                            )
                            subprocess.Popen(
                                [sys.executable, poll_main], cwd=poll_path, env=env,
                            )
                        else:
                            messagebox.showerror("Error", f"No Windows .bat and no {poll_main}")
                            continue
                    action_label = (
                        'check poll (cancel if < 6 Yes)'
                        if mode == 'check'
                        else 'send cancel message'
                    )
                    mode_label = 'real send' if send_real else 'dry-run'
                    logging.info(
                        "Launched WhatsApp turnout contact=%r action=%s mode=%s",
                        contact, action_label, mode_label,
                    )
                    messagebox.showinfo(
                        "Volleyball Low Turnout",
                        f"Started in a new console.\n\n"
                        f"Contact: {contact}\n"
                        f"Action: {action_label}\n"
                        f"Mode: {mode_label}\n\n"
                        "Ensure Edge is logged in at web.whatsapp.com (C:\\edge-cdp profile).",
                    )
                except Exception as e:
                    logging.error(f"Failed to start WhatsApp turnout: {e}")
                    messagebox.showerror(
                        "Error", f"Could not start WhatsApp turnout flow:\n{str(e)}",
                    )

            elif choice in ('youtube_transcribe', 'prune_transcripts'):
                import subprocess
                tasks_root = resolved_tasks_automation_root()
                yt_path = os.path.join(tasks_root, 'YouTube_Transcribe')
                bat_name = 'run_transcribe.bat' if choice == 'youtube_transcribe' else 'prune_transcripts.bat'
                bat_path = task_batch_path('youtube', bat_name)
                bat_workdir = task_batch_workdir('youtube')
                if not os.path.isfile(bat_path):
                    messagebox.showerror(
                        "Error",
                        f"YouTube_Transcribe launcher not found at:\n{bat_path}\n\n"
                        "Set TASKS_AUTOMATION_ROOT to your tasks_automation checkout (folder that "
                        "contains scripts_batch_files), or keep the default path that contains "
                        "scripts_batch_files\\laundry\\run_laundry.bat.",
                    )
                    continue
                try:
                    if sys.platform == 'win32':
                        subprocess.Popen(
                            ['cmd.exe', '/c', 'start', '', 'cmd.exe', '/k', bat_path],
                            cwd=bat_workdir,
                        )
                    else:
                        # WSL/Linux fallback — just run the python script directly.
                        py_script = os.path.join(yt_path, 'transcribe_youtube.py')
                        if choice == 'prune_transcripts':
                            subprocess.Popen([sys.executable, py_script, '--prune-days', '20'], cwd=yt_path)
                        else:
                            subprocess.Popen([sys.executable, py_script], cwd=yt_path)
                    logging.info(f"Launched {bat_name}")
                    label = "YouTube Transcribe" if choice == 'youtube_transcribe' else "Cleanup Transcripts"
                    extra = ("Paste a YouTube URL when prompted, choose a Whisper model, "
                             "then wait for the transcript. Outputs go to YouTube_Transcribe/transcripts/."
                             if choice == 'youtube_transcribe'
                             else "Old transcripts (default >20 days) will be deleted.")
                    messagebox.showinfo(
                        label,
                        f"{label} started in a new console window.\n\n{extra}"
                    )
                except Exception as e:
                    logging.error(f"Failed to start {bat_name}: {e}")
                    messagebox.showerror("Error", f"Could not start {bat_name}:\n{str(e)}")

    except Exception as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error", f"An unexpected error occurred:\n\n{str(e)}")
        logging.error(f"Main function error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
