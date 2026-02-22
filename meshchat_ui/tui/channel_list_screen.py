from textual.screen import ModalScreen
from textual.widgets import ListView, ListItem, Static
from textual.containers import Vertical

class ChannelListScreen(ModalScreen):
    """A modal screen to display the list of channels."""

    CSS = """
    ChannelListScreen {
        align: center middle;
    }

    #channel-list-container {
        width: 60%;
        height: 70%;
        border: round white;
        background: $surface;
    }
    """

    def __init__(self, channels: dict[str, int], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channels = channels

    def compose(self):
        """Create the content of the screen."""
        with Vertical(id="channel-list-container"):
            yield Static("Subscribed Channels (Press any key to close)", classes="header")
            yield ListView(id="channel-list-view")

    def on_mount(self):
        """Called when the widget is mounted."""
        self.call_after_refresh(self.populate_list)

    def populate_list(self):
        """Populate the list view with channels."""
        channel_list = self.query_one("#channel-list-view", ListView)
        if self.channels:
            for name, channel_id in self.channels.items():
                channel_list.append(ListItem(Static(f"{name} (ID: {channel_id})")))
        else:
            channel_list.append(ListItem(Static("No channels subscribed.")))

    def on_key(self, event) -> None:
        """Dismiss the screen on any key press."""
        self.dismiss()
