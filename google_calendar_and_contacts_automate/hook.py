import os
import sys

def print_file_locations():
    print("Python executable:", sys.executable)
    print("Current working directory:", os.getcwd())
    print("Contents of current directory:")
    for item in os.listdir():
        print(f"- {item}")
    
    service_account_file = 'calendar-automate-srvc-account-ref-file.json'
    properties_file = 'calendar_api_properties.properties'
    
    for file in [service_account_file, properties_file]:
        if os.path.exists(file):
            print(f"{file} found in the current directory")
            print(f"Full path: {os.path.abspath(file)}")
        else:
            print(f"{file} not found in the current directory")
            print(f"Searching in parent directories...")
            current_dir = os.getcwd()
            while True:
                parent_dir = os.path.dirname(current_dir)
                if parent_dir == current_dir:
                    print(f"Reached root directory, {file} not found")
                    break
                file_path = os.path.join(parent_dir, file)
                if os.path.exists(file_path):
                    print(f"{file} found at: {file_path}")
                    break
                current_dir = parent_dir

print_file_locations()
