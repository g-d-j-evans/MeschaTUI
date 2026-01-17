import json
import os

# BLE Connection Configuration
BLE_CONNECT_TIMEOUT = 10.0  # seconds
BLE_MAX_RETRIES = 3
BLE_RETRY_DELAY = 5  # seconds
BLE_MAX_CHANNEL_ATTEMPTS = 8 # Max number of channels to attempt to fetch

# --- Persistence ---
CONFIG_PATH = os.path.expanduser("~/.meshchat_serial.json")

def save_serial_connection(device_name: str, port: str, baud_rate: str):
    """Saves the last successful serial connection details."""
    details = {
        "device_name": device_name,
        "port": port,
        "baud_rate": baud_rate,
    }
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(details, f)
    except IOError:
        # Silently fail if we can't write the config file
        pass

def load_serial_connection() -> dict | None:
    """Loads the last serial connection details if they exist."""
    if not os.path.exists(CONFIG_PATH):
        return None
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return None
