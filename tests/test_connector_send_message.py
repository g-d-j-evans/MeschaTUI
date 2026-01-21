import pytest
from unittest.mock import AsyncMock, MagicMock
from meshchat_ui.radio.connector import RadioConnector

@pytest.mark.asyncio
async def test_send_message_converts_key():
    # Mock App
    mock_app = MagicMock()
    
    # Mock MeshCore
    mock_meshcore = AsyncMock()
    # Mock send_msg instead of send_msg_with_retry
    mock_meshcore.commands.send_msg = AsyncMock()
    
    # Create Connector
    connector = RadioConnector(mock_app)
    connector.get_meshcore = AsyncMock(return_value=mock_meshcore)

    # Test with hex string key
    hex_key = "a" * 64
    message = "Hello"
    
    success, err = await connector.send_message(message, hex_key)
    
    assert success is True
    assert err is None
    
    # Verify call args for send_msg
    args, _ = mock_meshcore.commands.send_msg.call_args
    destination, msg = args
    
    # Expect string now
    assert isinstance(destination, str)
    assert destination == hex_key
    assert msg == message

    # Test with non-hex string (e.g. invalid length or chars)
    alias = "some_alias"
    await connector.send_message(message, alias)
    
    args, _ = mock_meshcore.commands.send_msg.call_args
    destination, msg = args
    
    assert isinstance(destination, str)
    assert destination == alias
