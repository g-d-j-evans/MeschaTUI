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
        self._is_listening = False
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
            from rich.text import Text
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
            path_len = event.payload.get("path_len", 0)

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

            # Construct the Rich Text output based on message type and sender info
            text = Text()

            # 1. Date and Time Part (DD/MM HH:MM)
            from datetime import datetime
            if timestamp:
                local_time = datetime.fromtimestamp(timestamp).strftime("%d/%m %H:%M")
            else:
                local_time = "??/?? ??:??"

            # 2. Channel / DM Part
            if event.type == EventType.CONTACT_MSG_RECV:
                channel_name = "[DM]"
            else:
                channels_by_id = {v: k for k, v in self.app.channels.items()}
                channel_name = channels_by_id.get(channel_id, f"#{channel_id}")
                if not (channel_name.startswith("#") or channel_name.startswith("[")):
                    channel_name = f"#{channel_name}"
            
            text.append(f" {local_time} {channel_name} ({path_len}) ", style="black on green")
            text.append("\u25b6", style="green")
            text.append(" ")
            
            # 3. Indicator Part (✔/✘)
            indicator = "✔" if is_known_contact else "✘"
            text.append(indicator, style="white")
            text.append(" ")
            
            # 4. Sender Name Part (Name:)
            text.append(f"{determined_sender_name}:", style="white")
            text.append(" ")
            
            # 5. Message Text (Bold White)
            text.append(message_text, style="bold white")

            self.app.add_message(text)

        except Exception as e:
            self.logger.error("Error in message_callback", exc_info=True)

    def contacts_callback(self, event):
        """Callback for handling contacts events."""
        try:
            self.app.update_contacts(event.payload)
        except Exception as e:
            self.logger.error("Error in contacts_callback", exc_info=True)

    def advert_callback(self, event):
        """Callback for handling advertisement events."""
        try:
            self._log_json_message(event.payload)
            self.logger.debug(f"Advertisement event payload: {event.payload}")
            # Payload structure should be checked, but we assume it contains contact info.
            # We will pass the payload directly to the app to store.
            if hasattr(self.app, 'add_recent_advert'):
                self.app.add_recent_advert(event.payload)
        except Exception as e:
            self.logger.error("Error in advert_callback", exc_info=True)

    def new_contact_callback(self, event):
        """Callback for handling new contact events."""
        try:
            self._log_json_message(event.payload)
            self.logger.debug(f"New Contact event payload: {event.payload}")
            if hasattr(self.app, 'add_recent_advert'):
                self.app.add_recent_advert(event.payload)
        except Exception as e:
            self.logger.error("Error in new_contact_callback", exc_info=True)

    def _generic_event_callback(self, event):
        """Generic callback for logging all other events in debug mode."""
        try:
            self._log_json_message({"type": str(event.type), "payload": event.payload})
            self.logger.debug(f"Generic event received: {event.type} - Payload: {event.payload}")
        except Exception as e:
            self.logger.error(f"Error in generic_event_callback for {event.type}", exc_info=True)

    async def start_listening(self):
        """Subscribes to message events and starts auto message fetching."""
        if self._is_listening:
            return

        self._is_listening = True
        private_subscription = self.meshcore.subscribe(
            EventType.CONTACT_MSG_RECV, self.message_callback
        )
        channel_subscription = self.meshcore.subscribe(
            EventType.CHANNEL_MSG_RECV, self.message_callback
        )
        contacts_subscription = self.meshcore.subscribe(
            EventType.CONTACTS, self.contacts_callback
        )
        advert_subscription = self.meshcore.subscribe(
            EventType.ADVERTISEMENT, self.advert_callback
        )
        new_contact_subscription = self.meshcore.subscribe(
            EventType.NEW_CONTACT, self.new_contact_callback
        )
        
        self.subscriptions.extend(
            [private_subscription, channel_subscription, contacts_subscription, advert_subscription, new_contact_subscription]
        )

        if self.debug_mode:
            handled_types = [
                EventType.CONTACT_MSG_RECV,
                EventType.CHANNEL_MSG_RECV,
                EventType.CONTACTS,
                EventType.ADVERTISEMENT,
                EventType.NEW_CONTACT
            ]
            
            for name in dir(EventType):
                if name.startswith("_"):
                    continue
                event_type = getattr(EventType, name)
                # Ensure it's a valid value to subscribe to (integers/enums)
                if event_type in handled_types:
                    continue
                
                try:
                    sub = self.meshcore.subscribe(event_type, self._generic_event_callback)
                    self.subscriptions.append(sub)
                    self.logger.debug(f"Subscribed to extra event: {name}")
                except Exception as e:
                    self.logger.warning(f"Could not subscribe to event {name}: {e}")

        await self.meshcore.start_auto_message_fetching()

    async def stop_listening(self):
        """Unsubscribes from all events and stops auto message fetching."""
        if not self._is_listening:
            return
        
        self._is_listening = False
        for subscription in self.subscriptions:
            self.meshcore.unsubscribe(subscription)
        self.subscriptions = []
        await self.meshcore.stop_auto_message_fetching()
