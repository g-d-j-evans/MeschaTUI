from textual.screen import ModalScreen
from textual.widgets import Static
from textual.containers import Vertical, Grid

class ContactInfoScreen(ModalScreen):
    """A modal screen to display detailed information about a contact."""

    def __init__(self, contact: dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.contact = contact

    def compose(self):
        """Create the content of the screen."""
        with Vertical(id="contact-info-container", classes="modal-container"):
            yield Static(f"Details for {self.contact.get('name', 'Unknown')} (Press any key to close)", classes="modal-header")
            
            with Grid(id="contact-info-grid"):
                yield Static("Name:")
                yield Static(self.contact.get("name", "N/A"))

                yield Static("Public Key:")
                yield Static(self.contact.get("public_key", "N/A"))
                
                yield Static("Type:")
                contact_type = self.contact.get("type")
                if contact_type == 1:
                    type_str = "Client"
                elif contact_type == 2:
                    type_str = "Repeater"
                elif contact_type == 3:
                    type_str = "Room Server"
                else:
                    type_str = "Unknown"
                yield Static(type_str)

                yield Static("Last Seen:")
                # Assuming 'last_advert' is a timestamp
                from datetime import datetime
                last_seen_ts = self.contact.get("last_advert")
                if last_seen_ts:
                    last_seen_str = datetime.fromtimestamp(last_seen_ts).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    last_seen_str = "Never"
                yield Static(last_seen_str)

                yield Static("Path:")
                path = self.contact.get("out_path", "N/A")
                path_len = self.contact.get("out_path_len", 0)
                yield Static(f"{path} (len: {path_len})")

    def on_key(self, event):
        """Dismiss on any key press."""
        self.dismiss()
