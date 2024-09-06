import os

def print_cwd_contents():
    print("Current working directory:", os.getcwd())
    print("Contents of current directory:")
    for item in os.listdir():
        print(item)

print_cwd_contents()
