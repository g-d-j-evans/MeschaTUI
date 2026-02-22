from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, ListView, ListItem, Button, Static
from textual.containers import Vertical, Horizontal

class AdvertSelectionScreen(ModalScreen):
    """Screen to select a contact from recent adverts."""

    def __init__(self, adverts: list[dict]):
        super().__init__()
        self.adverts = adverts

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog", classes="dialog-container"):
            yield Label("Select a contact to add:", classes="modal-header")
            yield ListView(id="advert-list")
            with Horizontal(id="buttons", classes="button-group"):
                yield Button("Manual Add", variant="primary", id="manual")
                yield Button("Cancel", variant="error", id="cancel")

    def on_mount(self) -> None:
        advert_list = self.query_one("#advert-list", ListView)
        for advert in self.adverts:
            name = advert.get("adv_name", "Unknown")
            key = advert.get("public_key", advert.get("sender", "Unknown Key"))
            # Format: Name (Key)
            display_text = f"{name} ({key[:8]}...)"
            item = ListItem(Static(display_text))
            item.payload = advert # Store the advert data in the item
            advert_list.append(item)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Called when an item is selected."""
        self.dismiss(event.item.payload)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "manual":
            self.dismiss("MANUAL")
        elif event.button.id == "cancel":
            self.dismiss(None)

