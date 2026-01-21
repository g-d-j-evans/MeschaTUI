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
        with Vertical(id="dialog"):
            yield Label("Select a contact to add:", id="title")
            yield ListView(id="advert-list")
            with Horizontal(id="buttons"):
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

    CSS = """
    AdvertSelectionScreen {
        align: center middle;
    }

    #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1fr 3;
        padding: 0 1;
        width: 60;
        height: 20;
        border: thick $background 80%;
        background: $surface;
    }

    #title {
        column-span: 2;
        height: 1;
        width: 100%;
        content-align: center middle;
    }

    #advert-list {
        column-span: 2;
        height: 1fr;
        width: 100%;
        border: solid $accent;
    }

    #buttons {
        column-span: 2;
        width: 100%;
        height: 3;
        align: center middle;
    }
    """
