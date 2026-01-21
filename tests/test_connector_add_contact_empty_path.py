import pytest
from unittest.mock import AsyncMock, MagicMock
from meshchat_ui.radio.connector import RadioConnector
from meshcore import EventType

@pytest.mark.asyncio
async def test_add_contact_empty_path():
    # Mock App
    mock_app = MagicMock()
    
    # Mock MeshCore
    mock_meshcore = AsyncMock()
    mock_meshcore.commands.add_contact = AsyncMock()
    success_event = MagicMock()
    success_event.type = EventType.OK
    mock_meshcore.commands.add_contact.return_value = success_event
    
    # Create Connector
    connector = RadioConnector(mock_app)
    connector.get_meshcore = AsyncMock(return_value=mock_meshcore)

    # Test Data: out_path is empty string
    contact_data = {
        "adv_name": "Test User Empty Path",
        "public_key": "aabbcc",
        "out_path": ""
    }
    
    await connector.add_contact(contact_data.copy())
    
    # Verify call args
    args, _ = mock_meshcore.commands.add_contact.call_args
    passed_data = args[0]
    
    # Expect hex string, not bytes
    assert isinstance(passed_data["out_path"], str)
    assert passed_data["out_path"] == "00" * 32
    assert passed_data["key"] == "aabbcc"

