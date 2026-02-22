from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Input, Static, ListView, ListItem
from textual.worker import Worker, WorkerState

from datetime import datetime
from meshchat_ui.radio.connector import RadioConnector
from meshchat_ui.logger import get_logger
from meshchat_ui.tui.header import Header
from meshchat_ui.tui.connection_screen import ConnectionScreen
from meshchat_ui.tui.channel_overwrite_screen import ChannelOverwriteScreen
from meshchat_ui.tui.advert_selection_screen import AdvertSelectionScreen
from meshchat_ui.tui.contact_add_screen import ContactAddScreen
from meshchat_ui.tui.channel_list_screen import ChannelListScreen
from meshchat_ui.tui.contact_list_screen import ContactListScreen
from meshchat_ui.tui.contact_info_screen import ContactInfoScreen
import re


class Message(Static):
    def __init__(self, message_content: str | Text, is_sent: bool = False, **kwargs):
        super().__init__(message_content, **kwargs)
        self.is_sent = is_sent
        self.add_class("message-sent" if is_sent else "message-received")


class MessageDisplay(VerticalScroll):
    pass


class MeshChatApp(App):
    """A Textual app to chat over a mesh radio."""

    CSS = """
    Screen {
        layout: vertical;
    }

    Header {
        height: 3;
        dock: top;
        background: $panel;
        border-bottom: heavy white;
    }

    Header #radio-name {
        content-align: left middle;
        width: 50%;
        padding: 0 1;
    }

    Header #channel-count, Header #contact-count {
        content-align: right middle;
        width: 25%;
        padding: 0 1;
    }

    Header #channel-count:hover, Header #contact-count:hover {
        background: $boost;
    }

    MessageDisplay {
        height: 1fr;
    }

    #chat-input {
        dock: bottom;
    }

    .message-received {
        color: white;
        margin: 1 2;
        padding: 0 1;
    }

    .message-sent {
        margin: 1 2;
        padding: 0 1;
    }
    """

    def __init__(self, debug_mode: bool = False):
        super().__init__()
        self.debug_mode = debug_mode
        self.logger = get_logger(__name__, debug_mode=self.debug_mode)
        self.radio_connector = RadioConnector(self, debug_mode=self.debug_mode)
        self.connection_worker: Worker | None = None
        self.get_lists_worker: Worker | None = None
        self.disconnect_worker: Worker | None = None
        self.get_info_worker: Worker | None = None
        self.channels: dict[str, int] = {}
        self.contacts: list[dict] = []
        self.recent_adverts: list[dict] = []
        self.radio_info: dict = {}

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield MessageDisplay()
        yield Input(placeholder="Type a command or message...", id="chat-input")

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        def connection_callback(connection_details: dict | None):
            if connection_details:
                self.action_start_connection(connection_details)
        
        self.push_screen(ConnectionScreen(), connection_callback)

    def on_click(self, event) -> None:
        """Handle click events."""
        if event.widget.id == "channel-count":
            self.action_show_channels()
        elif event.widget.id == "contact-count":
            self.action_show_contacts()

    def action_show_channels(self):
        """Show the channel list screen."""
        self.push_screen(ChannelListScreen(self.channels))

    def action_show_contacts(self):
        """Show the contact list screen."""
        def show_contact_info(contact_data):
            if contact_data:
                self.push_screen(ContactInfoScreen(contact_data))
        
        self.push_screen(ContactListScreen(self.contacts), show_contact_info)

    def action_start_connection(self, connection_details: dict):
        """Start the connection process based on details from the connection screen."""
        conn_type = connection_details.get("type")
        if conn_type == "ble":
            ble_address = connection_details.get("address")
            self.notify(f"Connecting to radio via BLE at {ble_address}...")
            self.radio_connector.set_bluetooth_radio(ble_address)
        elif conn_type == "serial":
            serial_port = connection_details.get("port")
            baud_rate = connection_details.get("baud_rate")
            self.notify(f"Connecting to radio via Serial at {serial_port} with baud rate {baud_rate}...")
            self.radio_connector.set_serial_radio(serial_port, baud_rate)

        if self.connection_worker and self.connection_worker.is_running:
            self.notify("Connection already in progress. Please wait.")
            return
        self.connection_worker = self.run_worker(
            self.radio_connector.connect_radio(), exclusive=True
        )

    def add_message(self, message: str | Text, is_sent: bool = False):
        message_display = self.query_one(MessageDisplay)
        message_display.mount(Message(message, is_sent=is_sent))
        message_display.scroll_end(animate=False)
    
    def add_recent_advert(self, advert: dict):
        if self.debug_mode:
            self.logger.debug(f"Adding recent advert: {advert}")

        # Check for duplicates based on public_key or sender
        key = advert.get("public_key") or advert.get("sender")
        if not key:
            if self.debug_mode:
                self.logger.debug("Advert ignored due to missing public_key/sender")
            return
        
        # Normalize: Ensure public_key is set if sender is available
        if "sender" in advert and "public_key" not in advert:
             advert["public_key"] = advert["sender"]
        
        # Remove existing if any (to move to top/update)
        self.recent_adverts = [a for a in self.recent_adverts if (a.get("public_key") or a.get("sender")) != key]
        self.recent_adverts.insert(0, advert)
        # Keep last 50
        if len(self.recent_adverts) > 50:
            self.recent_adverts.pop()


    async def process_join_command(self, channel_name: str) -> None:
        self.notify(f"Attempting to join public channel {channel_name}...")
        # join_public_channel returns (success, message, extra_data)
        join_success, result, extra_data = await self.radio_connector.join_public_channel(channel_name)
        
        if join_success:
            self.notify(f"Successfully joined channel {channel_name}.")
            # Refresh channels list after joining a new one
            self.get_lists_worker = self.run_worker(
                self.radio_connector.get_contacts_and_channels, name="get_lists"
            )
        elif result == "OVERWRITE_REQUIRED":
            # Use the extra_data (used_channels) returned from join_public_channel
            overwrite_choice = await self.push_screen_wait(ChannelOverwriteScreen(extra_data))
            
            if overwrite_choice is not None:
                self.notify(f"Overwriting channel {overwrite_choice} with {channel_name}...")
                overwrite_success, overwrite_message = await self.radio_connector.overwrite_public_channel(channel_name, overwrite_choice)
                if overwrite_success:
                    self.notify(f"Successfully joined channel {channel_name}.")
                    self.get_lists_worker = self.run_worker(
                        self.radio_connector.get_contacts_and_channels, name="get_lists"
                    )
                else:
                    self.notify(f"Failed to overwrite channel: {overwrite_message}")
                    self.logger.error(f"Failed to overwrite channel: {overwrite_message}")
            else:
                self.notify("Channel join cancelled.")
        else:
            self.notify(f"Failed to join channel {channel_name}: {result}")
            self.logger.error(f"Failed to join channel {channel_name}: {result}")

    async def _add_contact_helper(self, contact_data: dict):
        success, msg = await self.radio_connector.add_contact(contact_data)
        if success:
            self.notify(f"Contact '{contact_data.get('adv_name')}' added.")
            self.run_worker(self.radio_connector.get_contacts_and_channels, name="get_lists")
        else:
            self.notify(f"Failed to add contact: {msg}")

    async def _remove_contact_helper(self, public_key: str, name: str, refresh_list: bool = True):
        success, msg = await self.radio_connector.remove_contact(public_key)
        if success:
            self.notify(f"Contact '{name}' removed.")
            if refresh_list:
                self.run_worker(self.radio_connector.get_contacts_and_channels, name="get_lists")
        else:
            self.notify(f"Failed to remove contact '{name}': {msg}")

    async def _purge_contacts_worker(self, contacts_to_remove: list, type_str: str):
        """Worker to remove multiple contacts and refresh once at the end."""
        self.notify(f"Purging {len(contacts_to_remove)} contacts of type {type_str}...")
        for i, contact in enumerate(contacts_to_remove):
            # Refresh list only on the last contact
            is_last = (i == len(contacts_to_remove) - 1)
            await self.radio_connector.remove_contact(contact['public_key'])
            if (i + 1) % 5 == 0:
                self.notify(f"Purged {i+1}/{len(contacts_to_remove)}...")
        
        self.notify(f"Purge of {type_str} complete.")
        self.run_worker(self.radio_connector.get_contacts_and_channels, name="get_lists")

    async def _send_advert_helper(self):
        success, msg = await self.radio_connector.send_advert()
        if success:
            self.notify("Flood advert sent.")
        else:
            self.notify(f"Failed to send advert: {msg}")

    async def _send_message_worker(self, message_text: str, destination: str, destination_id: str | int, type_str: str):
        """Worker to handle sending messages and updating the UI upon delivery confirmation."""
        self.logger.debug(f"Starting _send_message_worker for {type_str} to {destination}")
        self.notify(f"Sending {type_str} to {destination}...")
        
        if type_str == "DM":
            # For DM, destination_id is public key string. send_message uses retry logic.
            # We can pass extra params to try harder
            success, error, _ = await self.radio_connector.send_message(message_text, str(destination_id))
        else:
            # For Channel, destination_id is channel integer index.
            success, error, _ = await self.radio_connector.send_channel_message(message_text, int(destination_id))
            
        if success:
            self.logger.debug(f"Message delivery confirmed for {destination}. Adding to UI.")
            
            text = Text()
            time_str = datetime.now().strftime("%d/%m %H:%M")
            # 1. Channel or Contact Part (with Time inside highlight, all black text)
            text.append(f" {time_str} {destination} ", style="black on cyan")
            text.append("\u25b6", style="cyan")
            text.append(" ")
            
            # 2. Message Text (Bold White)
            text.append(message_text, style="bold white")
            
            self.add_message(text, is_sent=True)
            self.notify("Message delivered")
        else:
            self.logger.warning(f"Message delivery failed for {destination}: {error}")
            self.notify(f"Failed to send: {error}")
            self.logger.error(f"Failed to send to {destination}: {error}")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle submitted input."""
        parts = event.value.strip().split()
        if not parts:
            return

        command = parts[0].lower()
        message_text = " ".join(parts[1:])

        if command == "disconnect":
            self.notify("Disconnecting from radio...")
            self.disconnect_worker = self.run_worker(self.radio_connector.disconnect)
        elif command == "advert":
            self.notify("Sending flood advert...")
            self.run_worker(self._send_advert_helper())
        elif command == "channels":
            self.action_show_channels()
        elif command == "contacts":
            self.action_show_contacts()
        
        elif command == "<add>":
            def handle_save_contact(contact_data):
                if contact_data:
                    self.run_worker(self._add_contact_helper(contact_data))

            def handle_add_choice(choice):
                if choice == "MANUAL":
                    self.push_screen(ContactAddScreen(), handle_save_contact)
                elif isinstance(choice, dict):
                    self.push_screen(ContactAddScreen(choice), handle_save_contact)
            
            self.push_screen(AdvertSelectionScreen(self.recent_adverts), handle_add_choice)

        elif command == "<remove>":
            name_to_remove = message_text
            contact = next((c for c in self.contacts if c['name'] == name_to_remove), None)
            if contact:
                self.run_worker(self._remove_contact_helper(contact['public_key'], name_to_remove))
            else:
                self.notify(f"Contact '{name_to_remove}' not found.")

        elif command == "<purge>":
            type_str = message_text.lower()
            type_map = {"client": 1, "repeater": 2, "room": 3}
            target_type = type_map.get(type_str)
            if target_type:
                to_remove = [c for c in self.contacts if c.get('type') == target_type]
                self.run_worker(self._purge_contacts_worker(to_remove, type_str))
            else:
                self.notify("Invalid type. Use: client, repeater, room")

        elif command == "join":
            channel_name = message_text
            if not channel_name.startswith("#"):
                self.notify("Error: Public channel names must start with '#'.")
                return
            if not self.radio_connector.radio:
                self.notify("Error: Not connected to a radio.")
                return

            self.run_worker(self.process_join_command(channel_name))
        
        # Check if destination is a channel
        elif command in self.channels:
            channel_id = self.channels[command]
            self.run_worker(self._send_message_worker(message_text, command, channel_id, "to"))
        
        # Check if destination is a client
        else:
            recipient = next((c for c in self.contacts if c['name'] == command and c['type'] == 1), None)
            if recipient:
                destination_id = recipient['public_key']
                self.run_worker(self._send_message_worker(message_text, command, destination_id, "DM"))
            else:
                self.notify(f"Unknown command or destination: {command}")

        event.input.value = ""

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Called when a worker's state changes."""
        if event.worker is self.connection_worker:
            if event.state == WorkerState.SUCCESS:
                connected, error_message = event.worker.result
                if connected:
                    self.notify("Successfully connected to radio.")
                    self.notify("Fetching radio info...")
                    self.get_info_worker = self.run_worker(
                        self.radio_connector.get_radio_info, name="get_info"
                    )
                else:
                    self.notify(f"Failed to connect to radio: {error_message}")
                    self.logger.error(f"Failed to connect to radio: {error_message}")
            elif event.state == WorkerState.ERROR:
                self.notify(f"Connection worker failed: {event.worker.result}")
                self.logger.error(f"Connection worker failed: {event.worker.result}")

        elif event.worker.name == "get_info":
            if event.state == WorkerState.SUCCESS:
                self.radio_info = event.worker.result
                if self.radio_info:
                    self.notify("Successfully fetched radio info.")
                    self.query_one(Header).update_header(radio_name=self.radio_info.get("name", "Unknown Radio"))
                else:
                    self.notify("Failed to fetch radio info.")
                    self.logger.error("Failed to fetch radio info.")
                self.notify("Fetching contacts and channels...")
                self.get_lists_worker = self.run_worker(
                    self.radio_connector.get_contacts_and_channels, name="get_lists"
                )
            elif event.state == WorkerState.ERROR:
                self.notify("Failed to fetch radio info.")
                self.logger.error("Failed to fetch radio info.")

        elif event.worker.name == "get_lists":
            if event.state == WorkerState.SUCCESS:
                data = event.worker.result
                self.contacts = data["contacts"]
                self.channels = {
                    channel["name"]: channel["id"] for channel in data["channels"]
                }
                
                # Update header counts
                self.query_one(Header).update_header(
                    channel_count=len(self.channels), 
                    contact_count=len(self.contacts),
                    total_channels=self.radio_info.get("max_channels", 0)
                )

                self.notify("Subscribing to new messages...")
                self.run_worker(self.radio_connector.subscribe, name="subscribe")
            elif event.state == WorkerState.ERROR:
                self.notify("Failed to fetch contacts and channels.")
                self.logger.error("Failed to fetch contacts and channels.")

        elif event.worker.name == "subscribe":
            if event.state == WorkerState.SUCCESS:
                self.notify("Subscribed to new messages.")
            elif event.state == WorkerState.ERROR:
                self.notify("Failed to subscribe to new messages.")
                self.logger.error("Failed to subscribe to new messages.")
