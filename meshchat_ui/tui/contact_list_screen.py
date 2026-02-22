from textual.screen import ModalScreen
from textual.widgets import ListView, ListItem, Static
from textual.containers import Vertical

class ContactListScreen(ModalScreen):
    """A modal screen to display the list of contacts."""

    def __init__(self, contacts: list[dict], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.contacts = contacts

    def compose(self):
        """Create the content of the screen."""
        with Vertical(id="contact-list-container", classes="modal-container"):
            yield Static("Contacts (Select to view, ESC to close)", classes="modal-header")
            yield ListView(id="contact-list-view")

    def on_mount(self):
        """Called when the widget is mounted."""
        self.call_after_refresh(self.populate_list)

    def populate_list(self):
        """Populate the list view with contacts."""
        contact_list = self.query_one("#contact-list-view", ListView)
        if self.contacts:
            for contact in self.contacts:
                contact_name = contact.get('name', 'Unknown')
                contact_type = contact.get('type')
                if contact_type == 1:
                    display_name = f" {contact_name}"
                elif contact_type == 2:
                    display_name = f" {contact_name}"
                elif contact_type == 3:
                    display_name = f" {contact_name}"
                else:
                    display_name = contact_name
                
                item = ListItem(Static(display_name))
                item.contact_data = contact
                contact_list.append(item)
        else:
            contact_list.append(ListItem(Static("No contacts found.")))

    def on_key(self, event) -> None:
        """Dismiss on ESC."""
        if event.key == "escape":
            self.dismiss()

    def on_list_view_selected(self, event: ListView.Selected):
        """Handle contact selection."""
        self.dismiss(event.item.contact_data)
