from __future__ import annotations
from typing import TYPE_CHECKING
from meshcore import MeshCore, EventType
import re

if TYPE_CHECKING:
    from meshchat_ui.tui.app import MeshChatApp

class RadioHandler:
    """Handles incoming messages and other radio events."""

    def __init__(self, meshcore: MeshCore, app: MeshChatApp):
        self.meshcore = meshcore
        self.app = app
        self.subscriptions = []

    def message_callback(self, event):
        try:
            message_text = event.payload.get("text", "No message text")
            message_text = re.sub(r'@\[(.*?)\]', r'@\1', message_text)
            sender = event.payload.get("pubkey_prefix", "Unknown Sender")
            channel_id = event.payload.get("channel_idx")
            timestamp = event.payload.get("sender_timestamp")

            from datetime import datetime

            if timestamp:
                local_time = datetime.fromtimestamp(timestamp).strftime("%d;%m %H:%M")
            else:
                local_time = "No timestamp"

            channels_by_id = {v: k for k, v in self.app.channels.items()}
            channel_name = channels_by_id.get(channel_id, f"Channel {channel_id}")

            self.app.add_message(
                f"{local_time} [{channel_name}] {sender}: {message_text}"
            )
        except Exception:
            # Silently ignore errors in message processing
            pass

    def contacts_callback(self, event):
        """Callback for handling contacts events."""
        try:
            self.app.update_contacts(event.payload)
        except Exception:
            # Silently ignore errors in contacts processing
            pass

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
