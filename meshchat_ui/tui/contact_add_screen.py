from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, Input, Button
from textual.containers import Vertical, Horizontal

class ContactAddScreen(ModalScreen):
    """Screen to add or edit a contact."""

    def __init__(self, contact_data: dict | None = None):
        super().__init__()
        self.contact_data = contact_data or {}

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog", classes="dialog-container"):
            yield Label("Add Contact", classes="modal-header")
            yield Label("Name:")
            yield Input(value=self.contact_data.get("adv_name", ""), id="name-input", placeholder="Enter contact name")
            yield Label("Public Key:")
            yield Input(value=self.contact_data.get("public_key", self.contact_data.get("sender", "")), id="key-input", placeholder="Enter public key (hex)")
            with Horizontal(id="buttons", classes="button-group"):
                yield Button("Save", variant="success", id="save")
                yield Button("Cancel", variant="error", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            name = self.query_one("#name-input", Input).value
            key = self.query_one("#key-input", Input).value
            
            if not name or not key:
                self.app.notify("Name and Key are required.")
                return
            
            # Update contact data with new values
            self.contact_data["adv_name"] = name
            self.contact_data["public_key"] = key
            # Ensure type is set
            self.contact_data.setdefault("type", 1) # Client

            self.dismiss(self.contact_data)
        elif event.button.id == "cancel":
            self.dismiss(None)

