import pytest
from unittest.mock import AsyncMock, MagicMock
from meshchat_ui.radio.connector import RadioConnector
from meshcore import EventType

@pytest.mark.asyncio
async def test_send_advert_success():
    # Mock App
    mock_app = MagicMock()
    
    # Mock MeshCore
    mock_meshcore = AsyncMock()
    mock_meshcore.commands.send_advert = AsyncMock()
    # Return success event
    success_event = MagicMock()
    success_event.type = EventType.OK
    mock_meshcore.commands.send_advert.return_value = success_event
    
    # Create Connector
    connector = RadioConnector(mock_app)
    connector.get_meshcore = AsyncMock(return_value=mock_meshcore)

    success, msg = await connector.send_advert()
    
    assert success is True
    assert msg is None
    
    # Verify call args
    mock_meshcore.commands.send_advert.assert_called_once_with(flood=True)

@pytest.mark.asyncio
async def test_send_advert_failure_event():
    # Mock App
    mock_app = MagicMock()
    
    # Mock MeshCore
    mock_meshcore = AsyncMock()
    mock_meshcore.commands.send_advert = AsyncMock()
    # Return error event
    error_event = MagicMock()
    error_event.type = EventType.ERROR
    error_event.payload = "Some error"
    mock_meshcore.commands.send_advert.return_value = error_event
    
    # Create Connector
    connector = RadioConnector(mock_app)
    connector.get_meshcore = AsyncMock(return_value=mock_meshcore)

    success, msg = await connector.send_advert()
    
    assert success is False
    assert "Failed to send advert" in msg

@pytest.mark.asyncio
async def test_send_advert_exception():
    # Mock App
    mock_app = MagicMock()
    
    # Mock MeshCore
    mock_meshcore = AsyncMock()
    mock_meshcore.commands.send_advert = AsyncMock(side_effect=Exception("Boom"))
    
    # Create Connector
    connector = RadioConnector(mock_app)
    connector.get_meshcore = AsyncMock(return_value=mock_meshcore)

    success, msg = await connector.send_advert()
    
    assert success is False
    assert "Boom" in msg
