import os

def print_cwd_contents():
    print("Current working directory:", os.getcwd())
    print("Contents of current directory:")
    for item in os.listdir():
        print(item)
    
    property_files_dir = os.path.join(os.getcwd(), 'property_files')
    if os.path.exists(property_files_dir):
        print("\nContents of property_files directory:")
        for item in os.listdir(property_files_dir):
            print(item)
    else:
        print("\nproperty_files directory not found")

print_cwd_contents()
