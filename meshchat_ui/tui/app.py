from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Input, Static, ListView, ListItem
from textual.worker import Worker, WorkerState

from meshchat_ui.radio.connector import RadioConnector
from meshchat_ui.tui.sidebar import Sidebar
from meshchat_ui.tui.connection_screen import ConnectionScreen

class Message(Static):
    def __init__(self, message_content: str, is_sent: bool = False, **kwargs):
        super().__init__(Text(message_content), **kwargs)
        self.is_sent = is_sent
        self.add_class("message-sent" if is_sent else "message-received")


class MessageDisplay(VerticalScroll):
    pass


class MeshChatApp(App):
    """A Textual app to chat over a mesh radio."""

    CSS = """
    Screen {
        layout: horizontal;
    }

    Sidebar {
        width: 15%;
        height: 100%;
    }

    Sidebar .header {
        background: white;
        color: black;
        text-align: center;
    }

    Sidebar ListView {
        border: round white;
        margin: 1;
    }

    #main-content {
        width: 85%;
        height: 100%;
    }

    Input {
        border: round white;
    }

    .message-received {
        color: white;
        margin: 1 2;
        padding: 0 1;
    }

    .message-sent {
        color: grey;
        margin: 1 2;
        padding: 0 1;
    }
    """

    def __init__(self):
        super().__init__()
        self.radio_connector = RadioConnector(self)
        self.connection_worker: Worker | None = None
        self.get_lists_worker: Worker | None = None
        self.disconnect_worker: Worker | None = None
        self.get_info_worker: Worker | None = None
        self.channels: dict[str, int] = {}

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Sidebar()
        with Vertical(id="main-content"):
            yield MessageDisplay()
            yield Input(placeholder="Type a message...")

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        def connection_callback(connection_details: dict | None):
            if connection_details:
                self.action_start_connection(connection_details)
        
        self.push_screen(ConnectionScreen(), connection_callback)

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

    def add_message(self, message: str, is_sent: bool = False):
        message_display = self.query_one(MessageDisplay)
        message_display.mount(Message(message, is_sent=is_sent))
        message_display.scroll_end(animate=False)

    def update_contacts(self, contacts):
        contact_list = self.query_one("#contacts", ListView)
        contact_list.clear()
        for contact in contacts:
            contact_type = contact.get("type")
            contact_name = contact.get("name", "Unknown")
            if contact_type == 1:  # Client
                display_name = f" {contact_name}"
            elif contact_type == 2:  # Repeater
                display_name = f" {contact_name}"
            elif contact_type == 3: # Room Server
                display_name = f" {contact_name}"
            else:
                display_name = contact_name
            contact_list.append(ListItem(Static(display_name)))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle submitted input."""
        parts = event.value.strip().split()

        if not parts:
            return

        command = parts[0]
        args = parts[1:]

        if command == "disconnect":
            self.notify("Disconnecting from radio...")
            self.disconnect_worker = self.run_worker(self.radio_connector.disconnect)
        elif command == "advert":
            self.notify("Sending flood advert...")
            self.run_worker(self.radio_connector.send_advert)
        elif command == "to":
            if len(args) >= 2:
                channel_name = args[0]
                message_text = " ".join(args[1:])
                if channel_name in self.channels:
                    channel_id = self.channels[channel_name]
                    self.add_message(
                        f"Sending to {channel_name}: {message_text}", is_sent=True
                    )
                    self.run_worker(
                        self.radio_connector.send_channel_message(
                            message_text, channel_id
                        )
                    )
                else:
                    self.notify(f"Channel '{channel_name}' not found.")
            else:
                self.notify("Usage: to <channel name> <message>")
        else:
            self.notify(f"Unknown command: {command}")

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
            elif event.state == WorkerState.ERROR:
                self.notify(f"Connection worker failed: {event.worker.result}")

        elif event.worker.name == "get_info":
            if event.state == WorkerState.SUCCESS:
                info = event.worker.result
                if info:
                    self.notify("Successfully fetched radio info.")
                else:
                    self.notify("Failed to fetch radio info.")
                self.notify("Fetching contacts and channels...")
                self.get_lists_worker = self.run_worker(
                    self.radio_connector.get_contacts_and_channels, name="get_lists"
                )
            elif event.state == WorkerState.ERROR:
                self.notify("Failed to fetch radio info.")

        elif event.worker.name == "get_lists":
            if event.state == WorkerState.SUCCESS:
                data = event.worker.result
                self.notify(
                    f"Found {len(data['contacts'])} contacts and {len(data['channels'])} channels."
                )
                self.channels = {
                    channel["name"]: channel["id"] for channel in data["channels"]
                }

                channel_list = self.query_one("#channels", ListView)
                channel_list.clear()
                for channel in data["channels"]:
                    channel_list.append(ListItem(Static(channel["name"])))

                self.update_contacts(data['contacts'])

                self.notify("Subscribing to new messages...")
                self.run_worker(self.radio_connector.subscribe, name="subscribe")
            elif event.state == WorkerState.ERROR:
                self.notify("Failed to fetch contacts and channels.")

        elif event.worker.name == "subscribe":
            if event.state == WorkerState.SUCCESS:
                self.notify("Subscribed to new messages.")
            elif event.state == WorkerState.ERROR:
                self.notify("Failed to subscribe to new messages.")
