from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Input, Static, ListView, ListItem, Footer
from textual.worker import Worker, WorkerState
from textual.command import Provider, Hit, DiscoveryHit

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
from meshchat_ui.tui.radio_stats_screen import RadioStatsScreen
import re


class Message(Static):
    def __init__(self, message_content: str | Text, is_sent: bool = False, **kwargs):
        super().__init__(message_content, **kwargs)
        self.is_sent = is_sent
        self.add_class("message-sent" if is_sent else "message-received")


class MessageDisplay(VerticalScroll):
    pass


class CharacterCount(Static):
    """A widget to display the character count of an input."""
    def __init__(self, count: int = 0, max_len: int = 129, **kwargs):
        super().__init__(f"{count}/{max_len}", **kwargs)
        self.count = count
        self.max_len = max_len

    def update_count(self, count: int):
        self.count = count
        self.update(f"{self.count}/{self.max_len}")
        if self.count >= self.max_len:
            self.add_class("count-warn")
        else:
            self.remove_class("count-warn")


class CustomInput(Static):
    """A custom input widget that includes a character count."""
    def compose(self) -> ComposeResult:
        yield Input(placeholder="<channel|contact> <message> or /command", id="chat-input")
        yield CharacterCount(id="char-count")


class MeshChatCommandProvider(Provider):
    """A command provider for the MeshChat app."""

    async def discover(self) -> DiscoveryHit:
        """Yield discovery hits for the command palette."""
        commands = [
            ("/channels", self.app.action_show_channels, "Show subscribed channels"),
            ("/contacts", self.app.action_show_contacts, "Show contacts list"),
            ("/radio", self.app.action_show_radio_stats, "Show radio information and stats"),
            ("/advert", self.app.action_send_advert, "Send a flood advertisement"),
            ("/add", self.app.action_add_contact, "Add a new contact"),
            ("/remove", self.app.action_remove_contact, "Remove an existing contact"),
            ("/purge", self.app.action_purge_contacts, "Purge contacts by type"),
            ("/join", self.app.action_join_channel, "Join a public channel"),
            ("/disconnect", self.app.action_disconnect, "Disconnect from the radio"),
        ]
        for name, callback, help_text in commands:
            yield DiscoveryHit(
                name,
                callback,
                help=help_text,
            )

    async def search(self, query: str) -> Hit:
        """Search for commands."""
        matcher = self.matcher(query)

        commands = [
            ("/channels", self.app.action_show_channels, "Show subscribed channels"),
            ("/contacts", self.app.action_show_contacts, "Show contacts list"),
            ("/radio", self.app.action_show_radio_stats, "Show radio information and stats"),
            ("/advert", self.app.action_send_advert, "Send a flood advertisement"),
            ("/add", self.app.action_add_contact, "Add a new contact"),
            ("/remove", self.app.action_remove_contact, "Remove an existing contact"),
            ("/purge", self.app.action_purge_contacts, "Purge contacts by type"),
            ("/join", self.app.action_join_channel, "Join a public channel"),
            ("/disconnect", self.app.action_disconnect, "Disconnect from the radio"),
        ]

        for name, callback, help_text in commands:
            score = matcher.match(name)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(name),
                    callback,
                    help=help_text,
                )


class MeshChatApp(App):
    """A Textual app to chat over a mesh radio."""

    CSS_PATH = "style.css"
    COMMANDS = App.COMMANDS | {MeshChatCommandProvider}
    BINDINGS = [
        ("ctrl+p", "command_palette", "Commands"),
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+l", "show_channels", "Channels"),
        ("ctrl+k", "show_contacts", "Contacts"),
        ("ctrl+r", "show_radio_stats", "Radio"),
    ]

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
        self.subscribed: bool = False

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield MessageDisplay()
        yield CustomInput(id="input-container")
        yield Footer()

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        def connection_callback(connection_details: dict | None):
            if connection_details:
                self.action_start_connection(connection_details)
        
        self.push_screen(ConnectionScreen(), connection_callback)

    def _get_message_length(self, input_value: str) -> int:
        """Calculate the length of the message part of the input."""
        parts = input_value.strip().split()
        if len(parts) > 1 and not parts[0].startswith("/"):
            message_text = " ".join(parts[1:])
            return len(message_text)
        return 0

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes to update character count."""
        if event.input.id == "chat-input":
            count = self._get_message_length(event.value)
            self.query_one("#char-count", CharacterCount).update_count(count)

    def on_click(self, event) -> None:
        """Handle click events."""
        if event.widget.id == "channel-count":
            self.action_show_channels()
        elif event.widget.id == "contact-count":
            self.action_show_contacts()
        elif event.widget.id == "radio-name":
            self.action_show_radio_stats()

    def action_show_channels(self):
        """Show the channel list screen."""
        self.push_screen(ChannelListScreen(self.channels))

    def action_show_contacts(self):
        """Show the contact list screen."""
        def show_contact_info(contact_data):
            if contact_data:
                self.push_screen(ContactInfoScreen(contact_data))
        
        self.push_screen(ContactListScreen(self.contacts), show_contact_info)

    def action_show_radio_stats(self):
        """Fetch and show the radio statistics screen."""
        self.notify("Fetching radio statistics...")
        self.run_worker(self._get_radio_summary(), name="get_radio_summary")

    def action_disconnect(self):
        """Disconnect from the radio."""
        self.notify("Disconnecting from radio...")
        self.disconnect_worker = self.run_worker(self.radio_connector.disconnect)

    def action_send_advert(self):
        """Send a flood advertisement."""
        self.notify("Sending flood advert...")
        self.run_worker(self._send_advert_helper())

    def action_add_contact(self):
        """Open the add contact screen."""
        def handle_save_contact(contact_data):
            if contact_data:
                self.run_worker(self._add_contact_helper(contact_data))

        def handle_add_choice(choice):
            if choice == "MANUAL":
                self.push_screen(ContactAddScreen(), handle_save_contact)
            elif isinstance(choice, dict):
                self.push_screen(ContactAddScreen(choice), handle_save_contact)
        
        self.push_screen(AdvertSelectionScreen(self.recent_adverts), handle_add_choice)

    def action_remove_contact(self, name: str | None = None):
        """Remove a contact by name."""
        if name:
            contact = next((c for c in self.contacts if c['name'] == name), None)
            if contact:
                self.run_worker(self._remove_contact_helper(contact['public_key'], name))
            else:
                self.notify(f"Contact '{name}' not found.")
        else:
            self.notify("Usage: <remove> <name>")

    def action_purge_contacts(self, type_str: str | None = None):
        """Purge contacts of a specific type (client, repeater, room)."""
        if type_str:
            type_map = {"client": 1, "repeater": 2, "room": 3}
            target_type = type_map.get(type_str.lower())
            if target_type:
                to_remove = [c for c in self.contacts if c.get('type') == target_type]
                self.run_worker(self._purge_contacts_worker(to_remove, type_str))
            else:
                self.notify("Invalid type. Use: client, repeater, room")
        else:
            self.notify("Usage: <purge> <type>")

    def action_join_channel(self, channel_name: str | None = None):
        """Join a public channel starting with #."""
        if channel_name:
            if not channel_name.startswith("#"):
                self.notify("Error: Public channel names must start with '#'.")
            elif not self.radio_connector.radio:
                self.notify("Error: Not connected to a radio.")
            else:
                self.run_worker(self.process_join_command(channel_name))
        else:
            self.notify("Usage: join <#channel>")

    async def _get_radio_summary(self) -> dict:
        """Fetch multiple pieces of radio information concurrently."""
        import asyncio
        results = await asyncio.gather(
            self.radio_connector.get_radio_info(),
            self.radio_connector.get_device_info(),
            self.radio_connector.get_radio_stats()
        )
        return {
            "self_info": results[0],
            "device_info": results[1],
            "radio_stats": results[2]
        }

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

    def _split_message(self, message: str, limit: int = 129) -> list[str]:
        """Split a message into segments of at most 'limit' characters."""
        if len(message) <= limit:
            return [message]
        
        segments = []
        while message:
            if len(message) <= limit:
                segments.append(message)
                break
            
            # Find the last space within the limit
            split_idx = message.rfind(" ", 0, limit + 1)
            if split_idx == -1:
                # No space found, split at limit
                split_idx = limit
            
            segments.append(message[:split_idx].strip())
            message = message[split_idx:].strip()
            
        return segments

    async def _send_message_worker(self, message_text: str, destination: str, destination_id: str | int, type_str: str):
        """Worker to handle sending messages and updating the UI upon delivery confirmation."""
        self.logger.debug(f"Starting _send_message_worker for {type_str} to {destination}")
        
        segments = self._split_message(message_text)
        total_segments = len(segments)
        
        for i, segment in enumerate(segments):
            progress_msg = f" ({i+1}/{total_segments})" if total_segments > 1 else ""
            self.notify(f"Sending {type_str}{progress_msg} to {destination}...")
            
            if type_str == "DM":
                success, error, _ = await self.radio_connector.send_message(segment, str(destination_id))
            else:
                success, error, _ = await self.radio_connector.send_channel_message(segment, int(destination_id))
                
            if success:
                self.logger.debug(f"Message segment {i+1} delivery confirmed for {destination}. Adding to UI.")
                
                text = Text()
                time_str = datetime.now().strftime("%d/%m %H:%M")
                segment_info = f" [{i+1}/{total_segments}]" if total_segments > 1 else ""
                
                # 1. Channel or Contact Part
                text.append(f" {time_str} {destination}{segment_info} ", style="black on cyan")
                text.append("\u25b6", style="cyan")
                text.append(" ")
                
                # 2. Message Text (Bold White)
                text.append(segment, style="bold white")
                
                self.add_message(text, is_sent=True)
            else:
                self.logger.warning(f"Message delivery failed for {destination} segment {i+1}: {error}")
                self.notify(f"Failed to send{progress_msg}: {error}")
                self.logger.error(f"Failed to send to {destination} segment {i+1}: {error}")
                break # Stop sending further segments if one fails
        
        if total_segments > 1 and success:
             self.notify(f"All {total_segments} segments delivered to {destination}")
        elif success:
             self.notify("Message delivered")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle submitted input."""
        parts = event.value.strip().split()
        if not parts:
            return

        original_first_part = parts[0].rstrip(":")
        first_part = original_first_part.lower()
        message_text = " ".join(parts[1:])

        if first_part.startswith("/"):
            command = first_part[1:] # strip the slash
            if command == "disconnect":
                self.action_disconnect()
            elif command == "advert":
                self.action_send_advert()
            elif command == "channels":
                self.action_show_channels()
            elif command == "contacts":
                self.action_show_contacts()
            elif command == "radio":
                self.action_show_radio_stats()
            elif command == "add":
                self.action_add_contact()
            elif command == "remove":
                self.action_remove_contact(message_text)
            elif command == "purge":
                self.action_purge_contacts(message_text)
            elif command == "join":
                self.action_join_channel(message_text)
            else:
                self.notify(f"Unknown command: /{command}")
        
        # Check if first_part is a channel
        elif original_first_part in self.channels:
            channel_id = self.channels[original_first_part]
            self.run_worker(self._send_message_worker(message_text, original_first_part, channel_id, "to"))

        # Check if first_part is a client
        else:
            recipient = next((c for c in self.contacts if c['name'] == original_first_part and c['type'] == 1), None)
            if recipient:
                destination_id = recipient['public_key']
                self.run_worker(self._send_message_worker(message_text, original_first_part, destination_id, "DM"))
            else:
                self.notify(f"Unknown command or destination: {original_first_part}")

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

                if not self.subscribed:
                    self.run_worker(self.radio_connector.subscribe, name="subscribe")
            elif event.state == WorkerState.ERROR:
                self.notify("Failed to fetch contacts and channels.")
                self.logger.error("Failed to fetch contacts and channels.")

        elif event.worker.name == "subscribe":
            if event.state == WorkerState.SUCCESS:
                self.subscribed = True
            elif event.state == WorkerState.ERROR:
                self.notify("Failed to subscribe to new messages.")
                self.logger.error("Failed to subscribe to new messages.")

        elif event.worker.name == "get_radio_summary":
            if event.state == WorkerState.SUCCESS:
                summary = event.worker.result
                self.push_screen(RadioStatsScreen(summary))
            elif event.state == WorkerState.ERROR:
                self.notify("Failed to fetch radio statistics.")
                self.logger.error("Failed to fetch radio statistics.")
