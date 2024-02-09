import os
import json


def trim_message(msg):
    replacements = [
        ("@everyone", ""),
        ("everyone", ""),
    ]

    for old, new in replacements:
        msg = msg.replace(old, new)

    return msg.strip()


def load_strings_from_json(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)


def load_state_file(file_path):
    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, 'r') as file:
            return json.loads(file.read())

    except FileNotFoundError:
        print(f"state file does not exist.")
        exit(1)


def save_state_file(state, file_path):
    with open(file_path, 'w') as file:
        file.write(json.dumps(state))

    print(f"Saved state")

