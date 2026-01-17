import sys
import os
from meshchat_ui.tui.app import MeshChatApp

os.environ["TEXTUAL_LOG"] = ""

if __name__ == "__main__":
    app = MeshChatApp()
    app.run()
