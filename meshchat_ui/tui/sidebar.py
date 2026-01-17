from textual.widgets import Static, ListView, ListItem
from textual.containers import Vertical

class Sidebar(Static):
    """A sidebar with Channels and Contacts lists."""

    def compose(self):
        """Create the content of the sidebar."""
        with Vertical():
            yield Static("Channels", classes="header")
            yield ListView(id="channels")
            yield Static("Contacts", classes="header")
            yield ListView(id="contacts")
