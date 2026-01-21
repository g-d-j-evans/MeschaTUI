import pytest
from unittest.mock import MagicMock
from meshchat_ui.radio.handler import RadioHandler
from meshcore import EventType

@pytest.mark.asyncio
async def test_new_contact_callback():
    # Mock App
    mock_app = MagicMock()
    mock_app.add_recent_advert = MagicMock()
    
    # Mock MeshCore
    mock_meshcore = MagicMock()
    
    # Create Handler
    handler = RadioHandler(mock_meshcore, mock_app)
    
    # Create a mock event for NEW_CONTACT
    mock_event = MagicMock()
    mock_event.type = EventType.NEW_CONTACT
    mock_event.payload = {
        "public_key": "1234567890abcdef",
        "adv_name": "New Friend",
        "type": 1
    }
    
    # Call the callback directly
    handler.new_contact_callback(mock_event)
    
    # Assert that app.add_recent_advert was called with the payload
    mock_app.add_recent_advert.assert_called_once_with(mock_event.payload)

