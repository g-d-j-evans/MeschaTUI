from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Header, Footer, Button, ListView, ListItem, Static
from textual.message import Message

class ChannelOverwriteScreen(ModalScreen):
    """
    A modal screen to prompt the user to select a channel to overwrite
    or cancel the join operation.
    """

    CSS = """
    ChannelOverwriteScreen {
        align: center middle;
    }

    .channel-overwrite-dialog {
        width: 60%;
        height: 60%;
        border: round white;
        background: $surface;
        padding: 1 2;
    }

    .dialog-prompt {
        margin-bottom: 1;
        text-align: center;
    }

    #channel-list {
        border: round white;
        height: 1fr;
        margin-bottom: 1;
    }

    Button {
        width: 100%;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, channels: list[dict], name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name=name, id=id, classes=classes)
        self.channels = channels
        self.selected_channel_id: int | None = None

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="channel-overwrite-dialog"):
            yield Static("No empty channel slots available. Select a channel to overwrite:", classes="dialog-prompt")
            channel_list_items = []
            for channel in self.channels:
                channel_list_items.append(
                    ListItem(Static(f"{channel['name']} (ID: {channel['id']})"), id=f"channel-{channel['id']}")
                )
            yield ListView(*channel_list_items, id="channel-list")
            yield Button("Overwrite Selected", variant="primary", id="overwrite-button")
            yield Button("Cancel", variant="default", id="cancel-button")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Called when a channel is selected from the list."""
        # Extract channel ID from the ListItem's ID
        item_id = event.item.id
        if item_id and item_id.startswith("channel-"):
            self.selected_channel_id = int(item_id.split("-")[1])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "overwrite-button":
            if self.selected_channel_id is not None:
                self.dismiss(self.selected_channel_id)
            else:
                self.app.notify("Please select a channel to overwrite.", title="No Channel Selected")
        elif event.button.id == "cancel-button":
            self.dismiss(None) # Dismiss with None to indicate cancellation

    def action_cancel(self) -> None:
        """Cancel the overwrite operation."""
        self.dismiss(None)
