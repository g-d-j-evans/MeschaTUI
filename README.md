# MeshChaTUI

This is a personal project, so use with caution. Playing with a Meshcore radio, i didnt want to have to use my phoneone all the time. Also the phone application only allows you to monitor messages from one channel or contact. I wanted a unified messaging view. The Meshcore_PY library does all the work in connecting to the companion radio. All this project does is put a Textual UI around it.

Dont expect everything to work. I dont have a lot of devices to test against. My setup is a linux machine and a Heltec V3 lora radio. The terminal i use is Alacritty

bluetooth connection is possible, but i have found it flakey, i would suggest connecting over USB serial. You will need to ensure that you have the correct permissions to access the device from the terminal.

This is very much a MVP.. just to see what is possible.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd MeshChaTUI
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Font Requirements

For the proper display of icons in the TUI, a Nerd Font is required. Please ensure you have a Nerd Font installed and configured in your terminal emulator.

## Usage

1.  **Run the application:**
    ```bash
    python run.py [--debug]
    ```
    *   To enable debug mode, run with the `--debug` flag: `python run.py --debug`.
        In debug mode, detailed debug logs will be written to `app_error.log`, and all
        subscribed radio messages will be logged in JSON format to a file named
        `radio_messages.json` in the project root directory.

2.  **Connect to your radio:**
     * enter the name, serial port (normally /dev/ttyUSB0) and the correct baud rate for your device.
        ```

3.  **Send a message:**
    Once connected, you can send messages by typing in the message bar. prefix the message with the name of the contact or channel.
    send a message to a channel
     * < channel > < message >
    to send to a contact
     * < contact > < message >
    ```

4. Join a public hashtag channel
   Type command join, followed by channel name (including #).
     * join #test 
   Joining Private channels not yet implemented.

5. Disconnect client device
     * disconnect

6. Send a flood advert
     * advert

