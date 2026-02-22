from textual.screen import ModalScreen
from textual.widgets import Static
from textual.containers import Vertical, Grid

class RadioStatsScreen(ModalScreen):
    """A modal screen to display radio statistics."""

    def __init__(self, summary: dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.summary = summary

    def compose(self):
        """Create the content of the screen."""
        with Vertical(id="radio-stats-container", classes="modal-container"):
            yield Static("Radio Information (Press any key to close)", classes="modal-header")
            
            with Grid(id="radio-stats-grid"):
                # 1. Device Info
                yield Static("Device Info", classes="category-header")
                device_info = self.summary.get("device_info")
                if device_info:
                    for key, value in device_info.items():
                        yield Static(f"{key.replace('_', ' ').title()}:", classes="stat-label")
                        yield Static(str(value), classes="stat-value")
                else:
                    yield Static("No device info available.", classes="stat-value")
                    yield Static("", classes="stat-value") # filler
                    yield Static("", classes="stat-value") # filler

                # 2. Self Info (Node Config)
                yield Static("Node Configuration", classes="category-header")
                self_info = self.summary.get("self_info")
                if self_info:
                    for key, value in self_info.items():
                        # Skip large binary blobs or redundant data if any
                        if key in ["public_key"]: # Display key but maybe truncate if too long?
                             yield Static(f"{key.title()}:", classes="stat-label")
                             yield Static(f"{str(value)[:16]}...", classes="stat-value")
                             continue
                        yield Static(f"{key.replace('_', ' ').title()}:", classes="stat-label")
                        yield Static(str(value), classes="stat-value")
                else:
                    yield Static("No self info available.", classes="stat-value")
                    yield Static("", classes="stat-value") # filler
                    yield Static("", classes="stat-value") # filler

                # 3. Radio Stats
                yield Static("Radio Statistics", classes="category-header")
                radio_stats = self.summary.get("radio_stats")
                if radio_stats:
                    for key, value in radio_stats.items():
                        yield Static(f"{key.replace('_', ' ').title()}:", classes="stat-label")
                        yield Static(str(value), classes="stat-value")
                else:
                    yield Static("No statistics available.", classes="stat-value")
                    yield Static("", classes="stat-value") # filler
                    yield Static("", classes="stat-value") # filler

    def on_key(self, event):
        """Dismiss on any key press."""
        self.dismiss()
