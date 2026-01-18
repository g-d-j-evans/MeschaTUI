import sys
import argparse
import os
from meshchat_ui.tui.app import MeshChatApp
from meshchat_ui.logger import get_logger

os.environ["TEXTUAL_LOG"] = ""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the MeshChat TUI application.")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode.")
    args = parser.parse_args()

    logger = get_logger(__name__)
    try:
        app = MeshChatApp(debug_mode=args.debug)
        app.run()
    except Exception as e:
        logger.critical("Application failed to run", exc_info=True)
