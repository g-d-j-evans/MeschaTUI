import pytest
from unittest.mock import AsyncMock, MagicMock
from meshchat_ui.radio.connector import RadioConnector
from meshcore import EventType

@pytest.mark.asyncio
async def test_add_contact_key_bytes_conversion():
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

    # Test Data: key is hex string
    hex_key = "a" * 64
    contact_data = {
        "adv_name": "Test Key Bytes",
        "public_key": hex_key,
        "out_path": ""
    }
    
    await connector.add_contact(contact_data.copy())
    
    args, _ = mock_meshcore.commands.add_contact.call_args
    passed_data = args[0]
    
    # Check key is string (reverted byte conversion)
    assert isinstance(passed_data["key"], str)
    assert passed_data["key"] == hex_key
    
    # Check out_path is string (hex)
    assert isinstance(passed_data["out_path"], str)

