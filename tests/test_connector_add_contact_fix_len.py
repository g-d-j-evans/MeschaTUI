import pytest
from unittest.mock import AsyncMock, MagicMock
from meshchat_ui.radio.connector import RadioConnector
from meshcore import EventType

@pytest.mark.asyncio
async def test_add_contact_fixes_len():
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

    # Test Data 1: Empty string out_path, out_path_len -1
    contact_data = {
        "adv_name": "Test Len Fix",
        "public_key": "aabbcc",
        "out_path": "",
        "out_path_len": -1
    }
    
    await connector.add_contact(contact_data.copy())
    
    args, _ = mock_meshcore.commands.add_contact.call_args
    passed_data = args[0]
    
    assert passed_data["out_path"] == "00" * 32
    assert passed_data["out_path_len"] == -1 # Should be preserved

    # Test Data 2: Hex string zeros, out_path_len -1
    contact_data_2 = {
        "adv_name": "Test Len Fix 2",
        "public_key": "aabbcc",
        "out_path": "00" * 32,
        "out_path_len": -1
    }
    
    await connector.add_contact(contact_data_2.copy())
    
    args, _ = mock_meshcore.commands.add_contact.call_args
    passed_data = args[0]
    
    assert passed_data["out_path"] == "00" * 32
    assert passed_data["out_path_len"] == -1 # Should be preserved

