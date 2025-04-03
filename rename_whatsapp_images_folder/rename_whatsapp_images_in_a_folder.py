import os
import re
import sys


def rename_whatsapp_images(directory):
    # Ensure the directory exists
    if not os.path.isdir(directory):
        print(f"Error: The directory '{directory}' does not exist")
        return False

    # Regular expression to extract the date and time from WhatsApp filenames
    pattern = r'WhatsApp Image (\d{4}-\d{2}-\d{2}) at (\d+\.\d+\.\d+) ([AP]M)'

    # Count files processed
    files_renamed = 0

    # Process all jpeg files in the directory
    for filename in os.listdir(directory):
        if filename.lower().endswith(('.jpeg', '.jpg')):
            # Try to match the WhatsApp pattern
            match = re.match(pattern, filename)
            if match:
                # Extract date and time components
                date, time, am_pm = match.groups()
                # Replace dots with colons in time
                time = time.replace('.', '-')
                # Create a new filename without spaces
                new_name = f"WhatsApp_{date}_{time}_{am_pm}.jpeg"

                # Rename the file
                try:
                    os.rename(os.path.join(directory, filename),
                              os.path.join(directory, new_name))
                    print(f"Renamed: {filename} → {new_name}")
                    files_renamed += 1
                except Exception as e:
                    print(f"Error renaming {filename}: {e}")
            else:
                # For files that don't match the pattern, just replace spaces with underscores
                new_name = filename.replace(' ', '_')
                if new_name != filename:
                    try:
                        os.rename(os.path.join(directory, filename),
                                  os.path.join(directory, new_name))
                        print(f"Renamed: {filename} → {new_name}")
                        files_renamed += 1
                    except Exception as e:
                        print(f"Error renaming {filename}: {e}")

    print(f"\nTotal files renamed: {files_renamed}")
    return True


if __name__ == "__main__":
    # Use command line argument if provided, otherwise ask for input
    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
    else:
        folder_path = input("Enter the folder path containing WhatsApp images: ")

    # Remove quotes if they were included in the path
    folder_path = folder_path.strip('"\'')

    # Run the renaming function
    rename_whatsapp_images(folder_path)