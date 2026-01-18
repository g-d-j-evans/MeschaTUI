from __future__ import annotations
from typing import TYPE_CHECKING
from meshcore import MeshCore, EventType
from meshchat_ui.logger import get_logger
import re
import json
import os

if TYPE_CHECKING:
    from meshchat_ui.tui.app import MeshChatApp

class RadioHandler:
    """Handles incoming messages and other radio events."""

    def __init__(self, meshcore: MeshCore, app: MeshChatApp, debug_mode: bool = False):
        self.meshcore = meshcore
        self.app = app
        self.subscriptions = []
        self.debug_mode = debug_mode
        self.json_log_path = os.path.join(os.getcwd(), "radio_messages.json") # Log file in current working directory
        self.logger = get_logger(__name__, debug_mode=self.debug_mode)

    def _log_json_message(self, event_payload):
        """Logs the event payload to a JSON file."""
        if not self.debug_mode:
            return
        
        # Ensure the payload is serializable
        serializable_payload = {}
        for key, value in event_payload.items():
            try:
                json.dumps(value) # Try to serialize to catch non-serializable types
                serializable_payload[key] = value
            except TypeError:
                serializable_payload[key] = str(value) # Convert non-serializable to string

        try:
            with open(self.json_log_path, "a") as f:
                json.dump(serializable_payload, f)
                f.write("\n") # Add a newline for each entry
            self.logger.debug(f"Logged radio message to {self.json_log_path}")
        except IOError as e:
            self.logger.error(f"Error writing to JSON log file {self.json_log_path}: {e}")

    def message_callback(self, event):
        try:
            self._log_json_message(event.payload) # Log the raw payload
            
            self.logger.debug(f"Message event payload: {event.payload}")
            message_text = event.payload.get("text", "")
            # Preserve original message text for potential sender name extraction
            original_message_text = message_text
            message_text = re.sub(r'@\[(.*?)\]', r'@\1', message_text)
            
            sender_pubkey_prefix = event.payload.get("pubkey_prefix")
            full_sender_pubkey = event.payload.get("sender")
            sender_name_from_payload = event.payload.get("sender_name")
            channel_id = event.payload.get("channel_idx")
            timestamp = event.payload.get("sender_timestamp")

            from datetime import datetime
            local_time = datetime.fromtimestamp(timestamp).strftime("%d;%m %H:%M") if timestamp else "No timestamp"

            self.logger.debug(f"full_sender_pubkey: {full_sender_pubkey}")
            self.logger.debug(f"sender_name_from_payload: {sender_name_from_payload}")
            self.logger.debug(f"sender_pubkey_prefix: {sender_pubkey_prefix}")
            self.logger.debug(f"App contacts: {self.app.contacts}")

            # 1. Try to find the sender in our contacts list
            determined_sender_name = None
            is_known_contact = False

            if full_sender_pubkey:
                for contact in self.app.contacts:
                    if contact["public_key"] == full_sender_pubkey:
                        determined_sender_name = contact["name"]
                        is_known_contact = True
                        break
            
            # If not found by full public key, try by pubkey_prefix (if available)
            if not is_known_contact and sender_pubkey_prefix:
                 for contact in self.app.contacts:
                    if contact["public_key"].startswith(sender_pubkey_prefix):
                        determined_sender_name = contact["name"]
                        is_known_contact = True # Set flag here
                        break

            self.logger.debug(f"Determined sender name (from contact list): {determined_sender_name}, Is known contact: {is_known_contact}")

            # 2. If still no name from contacts, try to extract from message text for channel messages
            #    This is only for Channel messages where sender_pubkey_prefix/full_sender_pubkey is None
            if determined_sender_name is None and event.type == EventType.CHANNEL_MSG_RECV:
                match = re.match(r'^([^:]+):', original_message_text)
                if match:
                    extracted_name_from_text = match.group(1).strip()
                    # Check if the extracted name is in contacts by name (less reliable but possible)
                    for contact in self.app.contacts:
                        if contact["name"] == extracted_name_from_text:
                            determined_sender_name = contact["name"]
                            is_known_contact = True # Set flag here
                            # Remove the name part from message_text to avoid redundancy in output
                            message_text = original_message_text[len(match.group(0)):].strip()
                            break
                    # If it's not a known contact, but we extracted a name, use it for display
                    if determined_sender_name is None:
                         determined_sender_name = extracted_name_from_text
                         message_text = original_message_text[len(match.group(0)):].strip()

            self.logger.debug(f"Determined sender name (after text extraction): {determined_sender_name}")

            # 3. Fallback to sender_name_from_payload if still no name (might contain full name)
            if determined_sender_name is None and sender_name_from_payload:
                determined_sender_name = sender_name_from_payload
            
            # 4. Fallback to pubkey_prefix if still nothing
            if determined_sender_name is None and sender_pubkey_prefix:
                determined_sender_name = sender_pubkey_prefix

            # 5. Final default
            if determined_sender_name is None:
                determined_sender_name = "Unknown"

            self.logger.debug(f"Final determined sender name: {determined_sender_name}")

            # Construct the output string based on message type and sender info
            output_string = ""

            if event.type == EventType.CONTACT_MSG_RECV: # Direct Message
                channel_display_part = "[DM]"
                output_string = f"{local_time} {channel_display_part} {determined_sender_name}: {message_text}"

            else: # Channel Message (EventType.CHANNEL_MSG_RECV)
                channels_by_id = {v: k for k, v in self.app.channels.items()}
                channel_name = channels_by_id.get(channel_id, f"Channel {channel_id}")
                channel_display_part = f"[{channel_name}]"

                if is_known_contact: # Sender is a known contact
                    output_string = f"{local_time} {channel_display_part} {determined_sender_name}: {message_text}"
                else: # Sender is not a known contact
                    output_string = f"{local_time} {channel_display_part} Unknown Sender: {determined_sender_name}: {message_text}"

            self.app.add_message(output_string)

        except Exception as e:
            self.logger.error("Error in message_callback", exc_info=True)

    def contacts_callback(self, event):
        """Callback for handling contacts events."""
        try:
            self.app.update_contacts(event.payload)
        except Exception as e:
            self.logger.error("Error in contacts_callback", exc_info=True)

    async def start_listening(self):
        """Subscribes to message events and starts auto message fetching."""
        private_subscription = self.meshcore.subscribe(
            EventType.CONTACT_MSG_RECV, self.message_callback
        )
        channel_subscription = self.meshcore.subscribe(
            EventType.CHANNEL_MSG_RECV, self.message_callback
        )
        contacts_subscription = self.meshcore.subscribe(
            EventType.CONTACTS, self.contacts_callback
        )
        
        self.subscriptions.extend(
            [private_subscription, channel_subscription, contacts_subscription]
        )

        await self.meshcore.start_auto_message_fetching()

    async def stop_listening(self):
        """Unsubscribes from all events and stops auto message fetching."""
        for subscription in self.subscriptions:
            self.meshcore.unsubscribe(subscription)
        self.subscriptions = []
        await self.meshcore.stop_auto_message_fetching()
