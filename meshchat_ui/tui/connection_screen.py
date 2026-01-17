from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical
from textual.widgets import Button, Input, Label, Checkbox, Static, Tabs, Tab, ListView, ListItem

from meshchat_ui.config import save_serial_connection, load_serial_connection
from bleak import BleakScanner
import asyncio


class ConnectionScreen(ModalScreen[dict]):
    """A modal screen for managing radio connections."""

    CSS = """
    ConnectionScreen {
        align: center middle;
    }

    #connection-dialog {
        width: 80w;
        height: auto;
        padding: 2;
        border: round white;
        background: $surface;
    }

    .hidden {
        display: none;
    }
    
    Input {
        margin-bottom: 1;
        border: round white;
    }

    ListView {
        border: round white;
        margin: 1;
        height: 8;
    }

    Checkbox {
        margin-top: 1;
        margin-bottom: 1;
    }

    Tabs {
        background: $surface;
    }

    Tab {
        background: $surface;
        color: $text;
    }

    Tab.active {
        background: $primary;
        color: $text;
    }

    Button {
        height: 1;
        padding: 0 1;
        background: red;
        color: white;
        border: none;
        margin-top: 1;
    }

    Button:hover {
        background: $primary;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="connection-dialog"):
            yield Tabs(
                Tab("Serial", id="serial-tab"),
                Tab("Bluetooth", id="bt-tab"),
                id="tabs",
            )
            with Vertical(id="serial-view"):
                yield Label("Serial Connection")
                yield Input(placeholder="Device Name (e.g., My Radio)", id="device-name-input")
                yield Input(placeholder="Port (e.g., /dev/ttyUSB0)", id="port-input")
                yield Input(value="115200", id="baud-rate-input")
                yield Checkbox("Remember this device", id="remember-checkbox")
                yield Button("Connect", id="serial-connect-button")

            with Vertical(id="bt-view", classes="hidden"):
                yield Label("Bluetooth Low Energy (BLE) Connection")
                yield ListView(id="bt-device-list")
                yield Button("Scan for devices", id="bt-scan-button")
                yield Button("Connect", id="bt-connect-button")

            yield Static(id="connection-status")

    def on_mount(self) -> None:
        """Load any saved connection details."""
        saved_connection = load_serial_connection()
        if saved_connection:
            self.query_one("#device-name-input", Input).value = saved_connection.get("device_name", "")
            self.query_one("#port-input", Input).value = saved_connection.get("port", "")
            self.query_one("#baud-rate-input", Input).value = saved_connection.get("baud_rate", "115200")
            self.query_one("#remember-checkbox", Checkbox).value = True

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        """Handle tab activation."""
        if event.tab.id == "serial-tab":
            self.query_one("#serial-view").remove_class("hidden")
            self.query_one("#bt-view").add_class("hidden")
        elif event.tab.id == "bt-tab":
            self.query_one("#serial-view").add_class("hidden")
            self.query_one("#bt-view").remove_class("hidden")
            
    async def scan_ble_devices(self):
        """Scan for BLE devices and populate the list."""
        ble_list = self.query_one("#bt-device-list", ListView)
        ble_list.clear()
        self.query_one("#connection-status", Static).update("Scanning for BLE devices...")
        try:
            devices = await BleakScanner.discover()
            for device in devices:
                ble_list.append(ListItem(Label(f"{device.name} ({device.address})"), name=device.address))
            self.query_one("#connection-status", Static).update("Scan complete.")
        except Exception as e:
            self.query_one("#connection-status", Static).update(f"BLE Scan Error: {e}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle the connect button press."""
        if event.button.id == "serial-connect-button":
            device_name = self.query_one("#device-name-input", Input).value
            port = self.query_one("#port-input", Input).value
            baud_rate = self.query_one("#baud-rate-input", Input).value
            
            if not port or not baud_rate:
                self.query_one("#connection-status", Static).update("Port and Baud Rate are required.")
                return

            if port.startswith("dev/tty") and not port.startswith("/"):
                port = "/" + port

            if self.query_one("#remember-checkbox", Checkbox).value:
                save_serial_connection(device_name, port, baud_rate)

            self.dismiss({
                "type": "serial",
                "port": port,
                "baud_rate": int(baud_rate)
            })

        elif event.button.id == "bt-scan-button":
            self.run_worker(self.scan_ble_devices, name="ble_scanner")

        elif event.button.id == "bt-connect-button":
            bt_list = self.query_one("#bt-device-list", ListView)
            if bt_list.highlighted_child:
                address = bt_list.highlighted_child.name
                self.dismiss({"type": "ble", "address": address})
