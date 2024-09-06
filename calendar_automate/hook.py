import os

def print_file_locations():
    print("Current working directory:", os.getcwd())
    
    service_account_file = 'calendar-automate-srvc-account-ref-file.json'
    properties_file = 'calendar_api_properties.properties'
    
    for file in [service_account_file, properties_file]:
        if os.path.exists(file):
            print(f"{file} found in the current directory")
        else:
            print(f"{file} not found in the current directory")

print_file_locations()
