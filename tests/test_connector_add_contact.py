import pytest
from unittest.mock import AsyncMock, MagicMock
from meshchat_ui.radio.connector import RadioConnector
from meshcore import EventType

@pytest.mark.asyncio
async def test_add_contact_mappings():
    # Mock App
    mock_app = MagicMock()
    
    # Mock MeshCore
    mock_meshcore = AsyncMock()
    mock_meshcore.commands.add_contact = AsyncMock()
    # Return success event
    success_event = MagicMock()
    success_event.type = EventType.OK
    mock_meshcore.commands.add_contact.return_value = success_event
    
    # Create Connector and inject mock meshcore
    connector = RadioConnector(mock_app)
    # Mock get_meshcore to return our mock
    connector.get_meshcore = AsyncMock(return_value=mock_meshcore)

    # Test Data 1: public_key provided, no key
    contact_data = {
        "adv_name": "Test User",
        "public_key": "aabbcc",
        "out_path": "00" * 32 # Hex string
    }
    
    success, msg = await connector.add_contact(contact_data.copy())
    
    assert success is True
    assert msg is None
    
    # Verify what was passed to meshcore
    args, _ = mock_meshcore.commands.add_contact.call_args
    passed_data = args[0]
    
    assert passed_data["key"] == "aabbcc" # Mapped from public_key
    assert isinstance(passed_data["out_path"], str) # Kept as string
    assert passed_data["out_path"] == "00" * 32
    assert passed_data["type"] == 1 # Default

    # Test Data 2: key provided already
    contact_data_2 = {
        "adv_name": "Test User 2",
        "key": "112233",
        "public_key": "should_be_ignored_if_key_exists", 
        "out_path": b'\x01\x02' # Already bytes
    }
    
    await connector.add_contact(contact_data_2.copy())
    
    args, _ = mock_meshcore.commands.add_contact.call_args
    passed_data = args[0]
    
    assert passed_data["key"] == "112233"
    assert passed_data["out_path"] == "0102"

