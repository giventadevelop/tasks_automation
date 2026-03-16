import os
import re
import sys
import random
import string


def rename_whatsapp_images(directory):
    # Ensure the directory exists
    if not os.path.isdir(directory):
        print(f"Error: The directory '{directory}' does not exist")
        return False

    # Count files processed
    files_renamed = 0

    # Dictionary to track used random names to ensure uniqueness
    used_names = set()

    # Process all jpeg files in the directory
    for filename in os.listdir(directory):
        if filename.lower().endswith(('.jpeg', '.jpg', '.png')):
            # Strip any parenthetical numbering like "(2)" or "(5)"
            base_name = re.sub(r'\s*\(\d+\)\s*', '', filename)

            # Generate base part of new name (first part of old filename with no spaces)
            file_prefix = base_name.split('.')[0].replace(' ', '_')

            # Generate random string (8 characters)
            random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

            # Get file extension
            _, extension = os.path.splitext(filename)

            # Create unique name
            new_name = f"{file_prefix}_{random_str}{extension}"

            # Make sure it's unique
            while new_name in used_names:
                random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
                new_name = f"{file_prefix}_{random_str}{extension}"

            used_names.add(new_name)

            # Rename the file
            try:
                old_path = os.path.join(directory, filename)
                new_path = os.path.join(directory, new_name)
                os.rename(old_path, new_path)
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
        folder_path = input("Enter the folder path containing images: ")

    # Remove quotes if they were included in the path
    folder_path = folder_path.strip('"\'')

    # Run the renaming function
    rename_whatsapp_images(folder_path)