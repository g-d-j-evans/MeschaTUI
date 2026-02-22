import pytest
from unittest.mock import MagicMock
from meshchat_ui.radio.handler import RadioHandler
from meshcore import EventType
from rich.text import Text

@pytest.mark.asyncio
async def test_message_callback_formatting():
    # Mock App
    mock_app = MagicMock()
    mock_app.channels = {"#general": 0}
    mock_app.contacts = [{"name": "Alice", "public_key": "alice_key"}]
    mock_app.add_message = MagicMock()
    
    # Mock MeshCore
    mock_meshcore = MagicMock()
    
    # Create Handler
    handler = RadioHandler(mock_meshcore, mock_app)
    
    # Create a mock event for CHANNEL_MSG_RECV from known contact
    mock_event = MagicMock()
    mock_event.type = EventType.CHANNEL_MSG_RECV
    mock_event.payload = {
        "text": "Hello world",
        "sender": "alice_key",
        "channel_idx": 0,
        "sender_timestamp": 1740054000,
        "path_len": 2
    }
    
    # Call the callback
    handler.message_callback(mock_event)
    
    # Verify app.add_message was called
    mock_app.add_message.assert_called_once()
    args, _ = mock_app.add_message.call_args
    rendered_text = args[0]
    
    assert isinstance(rendered_text, Text)
    # Check if time, #general and (2) are in the same highlight part
    assert "20/02 12:20 #general (2)" in rendered_text.plain
    # Check if "#general," is NOT there anymore
    assert "#general," not in rendered_text.plain
    # Check if "Alice:" is there
    assert "Alice:" in rendered_text.plain
    # Check if tick is there (Alice is known)
    assert "✔" in rendered_text.plain
    # Check if message is there
    assert "Hello world" in rendered_text.plain

@pytest.mark.asyncio
async def test_message_callback_dm():
    # Mock App
    mock_app = MagicMock()
    mock_app.channels = {}
    mock_app.contacts = [{"name": "Bob", "public_key": "bob_key"}]
    mock_app.add_message = MagicMock()
    
    # Mock MeshCore
    mock_meshcore = MagicMock()
    
    # Create Handler
    handler = RadioHandler(mock_meshcore, mock_app)
    
    # Create a mock event for CONTACT_MSG_RECV (DM)
    mock_event = MagicMock()
    mock_event.type = EventType.CONTACT_MSG_RECV
    mock_event.payload = {
        "text": "Private msg",
        "sender": "bob_key",
        "sender_timestamp": 1740054000,
        "path_len": 1
    }
    
    # Call the callback
    handler.message_callback(mock_event)
    
    # Verify
    args, _ = mock_app.add_message.call_args
    rendered_text = args[0]
    
    assert "20/02 12:20 [DM] (1)" in rendered_text.plain
    assert "Bob:" in rendered_text.plain
    assert "✔" in rendered_text.plain
    assert "Private msg" in rendered_text.plain
