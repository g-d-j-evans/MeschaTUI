from textual.widgets import Static
from textual.containers import Horizontal

class Header(Static):
    """A header with radio information, channel, and contact counts."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.radio_name = "Not Connected"
        self.channel_count = 0
        self.total_channels = 0 
        self.contact_count = 0

    def compose(self):
        """Create the content of the header."""
        with Horizontal():
            yield Static(id="radio-name")
            yield Static(id="channel-count")
            yield Static(id="contact-count")

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        self.update_header()

    def update_header(self, radio_name=None, channel_count=None, total_channels=None, contact_count=None):
        """Update the header content."""
        if radio_name is not None:
            self.radio_name = radio_name
        if channel_count is not None:
            self.channel_count = channel_count
        if total_channels is not None:
            self.total_channels = total_channels
        if contact_count is not None:
            self.contact_count = contact_count

        self.query_one("#radio-name").update(f"Radio: {self.radio_name}")
        self.query_one("#channel-count").update(f"Channels: {self.channel_count}/{self.total_channels}")
        self.query_one("#contact-count").update(f"Contacts: {self.contact_count}")
