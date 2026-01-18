from __future__ import annotations
from typing import TYPE_CHECKING
import asyncio
import serial
from abc import ABC, abstractmethod
from meshcore import MeshCore, EventType
from bleak.exc import BleakDBusError
from meshchat_ui.radio.handler import RadioHandler
from meshchat_ui.logger import get_logger
from meshchat_ui.config import BLE_CONNECT_TIMEOUT, BLE_MAX_RETRIES, BLE_RETRY_DELAY, BLE_MAX_CHANNEL_ATTEMPTS

if TYPE_CHECKING:
    from meshchat_ui.tui.app import MeshChatApp

class BaseRadio(ABC):
    @abstractmethod
    async def connect(self) -> tuple[bool, str | None]:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    async def get_meshcore(self) -> MeshCore | None:
        pass

class BluetoothRadio(BaseRadio):
    def __init__(self, ble_address: str, debug_mode: bool = False):
        self.ble_address = ble_address
        self.meshcore: MeshCore | None = None
        self.logger = get_logger(__name__, debug_mode=debug_mode)

    async def connect(self) -> tuple[bool, str | None]:
        self.logger.debug(f"Attempting to connect via BLE to {self.ble_address}...")
        if self.meshcore:
            self.logger.debug("Already connected, disconnecting first...")
            await self.disconnect()

        for attempt in range(BLE_MAX_RETRIES + 1):
            try:
                self.meshcore = await asyncio.wait_for(
                    MeshCore.create_ble(self.ble_address), timeout=BLE_CONNECT_TIMEOUT
                )
                self.logger.debug("BLE connection successful.")
                return True, None
            except asyncio.TimeoutError:
                self.logger.warning(f"BLE Connection attempt {attempt + 1}/{BLE_MAX_RETRIES + 1} timed out.")
                if attempt >= BLE_MAX_RETRIES:
                    return False, "Connection attempt timed out."
            except (ConnectionError, BleakDBusError, AttributeError) as e:
                self.logger.warning(f"BLE Connection attempt {attempt + 1}/{BLE_MAX_RETRIES + 1} failed: {e}")
                if attempt >= BLE_MAX_RETRIES:
                    return False, f"Failed to connect after multiple attempts: {e}"
            except Exception as e:
                self.logger.error(f"BLE Connection attempt {attempt + 1}/{BLE_MAX_RETRIES + 1} failed with unexpected error: {e}", exc_info=True)
                if attempt >= BLE_MAX_RETRIES:
                    return False, f"An unexpected error occurred: {e}"
            await asyncio.sleep(BLE_RETRY_DELAY * (2 ** attempt))
        return False, "Failed to connect to radio after multiple attempts."

    async def disconnect(self) -> None:
        if self.meshcore:
            self.logger.debug("Attempting to disconnect from BLE MeshCore...")
            await self.meshcore.disconnect()
            self.meshcore = None
            self.logger.info("Successfully disconnected from BLE MeshCore.")

    async def get_meshcore(self) -> MeshCore | None:
        return self.meshcore

class SerialRadio(BaseRadio):
    def __init__(self, serial_port: str, baud_rate: int, debug_mode: bool = False):
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.meshcore: MeshCore | None = None
        self.logger = get_logger(__name__, debug_mode=debug_mode)

    async def connect(self) -> tuple[bool, str | None]:
        self.logger.debug(f"Attempting to connect via Serial to {self.serial_port}@{self.baud_rate}...")
        try:
            self.meshcore = await MeshCore.create_serial(self.serial_port, self.baud_rate)
            self.logger.debug("Serial connection successful.")
            return True, None
        except Exception as e:
            self.logger.error(f"Failed to connect via Serial: {e}", exc_info=True)
            return False, f"Failed to connect via Serial: {e}"

    async def disconnect(self) -> None:
        if self.meshcore:
            self.logger.debug("Attempting to disconnect from Serial MeshCore...")
            await self.meshcore.disconnect()
            self.meshcore = None
            self.logger.info("Successfully disconnected from Serial MeshCore.")

    async def get_meshcore(self) -> MeshCore | None:
        return self.meshcore

class RadioConnector:
    """Handles the connection to the MeshCore radio."""

    def __init__(self, app: MeshChatApp, debug_mode: bool = False):
        self.radio: BaseRadio | None = None
        self.radio_handler: RadioHandler | None = None
        self.app = app
        self.debug_mode = debug_mode
        self.logger = get_logger(__name__, debug_mode=self.debug_mode)

    def set_bluetooth_radio(self, ble_address: str):
        self.radio = BluetoothRadio(ble_address, debug_mode=self.debug_mode)

    def set_serial_radio(self, serial_port: str, baud_rate: int):
        self.radio = SerialRadio(serial_port, baud_rate, debug_mode=self.debug_mode)

    async def connect_radio(self) -> tuple[bool, str | None]:
        if self.radio:
            success, message = await self.radio.connect()
            if success:
                self.radio_handler = RadioHandler(await self.radio.get_meshcore(), self.app, debug_mode=self.debug_mode)
            return success, message
        return False, "No radio type selected."

    async def disconnect(self) -> None:
        """Disconnects from the radio."""
        if self.radio and self.radio.meshcore:
            self.logger.debug("Attempting to disconnect from MeshCore...")
            try:
                if self.radio_handler:
                    await self.radio_handler.stop_listening()
                await self.radio.disconnect()
            except (EOFError, Exception) as e:
                self.logger.error(f"Error during disconnection: {e}", exc_info=True)
            finally:
                self.radio = None
                self.radio_handler = None

    async def get_meshcore(self) -> MeshCore | None:
        if self.radio:
            return await self.radio.get_meshcore()
        return None

    async def get_contacts_and_channels(self) -> dict[str, list[str]]:
        contacts = []
        channels = []

        meshcore = await self.get_meshcore()
        if meshcore is None:
            return {"contacts": contacts, "channels": channels}

        try:
            result = await meshcore.commands.get_contacts()
            if result and result.type != EventType.ERROR:
                payload = result.payload
                for key, contact_entry in payload.items():
                    name = (
                        contact_entry.get("adv_name")
                        or contact_entry.get("name")
                        or f"contact_{key}"
                    )
                    contact_type = contact_entry.get("type")
                    contacts.append({
                        "name": name,
                        "type": contact_type,
                        "public_key": key
                    })
        except Exception as e:
            self.logger.error("Error fetching contacts:", exc_info=True)

        for idx in range(BLE_MAX_CHANNEL_ATTEMPTS):
            try:
                chan_result = await meshcore.commands.get_channel(idx)
                if chan_result and chan_result.type != EventType.ERROR:
                    channel_info = chan_result.payload
                    channel_name = channel_info.get("channel_name")
                    if channel_name:
                        channels.append({"name": channel_name, "id": idx})
            except Exception:
                continue

        return {"contacts": contacts, "channels": channels}

    async def get_radio_info(self) -> dict | None:
        """Gets the radio info."""
        meshcore = await self.get_meshcore()
        if meshcore is None:
            return None
        try:
            return meshcore.self_info
        except Exception as e:
            self.logger.error(f"Error getting radio info: {e}", exc_info=True)
            return None

    async def subscribe(self) -> None:
        """Subscribes to new messages, channels, and adverts."""
        if self.radio_handler:
            try:
                await self.radio_handler.start_listening()
            except Exception as e:
                self.app.add_message(f"Error subscribing to messages: {e}")
                self.logger.error(f"Error subscribing: {e}", exc_info=True)

    async def send_advert(self) -> bool:
        """Sends a flood advert."""
        meshcore = await self.get_meshcore()
        if meshcore is None:
            return False
        try:
            await meshcore.commands.send_advert(flood=True)
            return True
        except Exception as e:
            self.logger.error(f"Error sending advert: {e}", exc_info=True)
            return False

    async def send_message(self, message: str, destination_id: str) -> tuple[bool, str | None]:
        """Sends a message to a specified destination."""
        meshcore = await self.get_meshcore()
        if meshcore is None:
            return False, "Radio not connected. Cannot send message."
        try:
            self.logger.debug(f"Sending message to {destination_id}")
            await meshcore.commands.send_msg(destination_id, message)
            return True, None
        except Exception as e:
            self.logger.error(f"Error sending message to {destination_id}: {e}", exc_info=True)
            return False, f"Error sending message: {e}"

    async def send_channel_message(self, message: str, channel_id: int) -> tuple[bool, str | None]:
        """Sends a message to a specified channel."""
        meshcore = await self.get_meshcore()
        if meshcore is None:
            return False, "Radio not connected. Cannot send channel message."
        try:
            self.logger.debug(f"Sending channel message to {channel_id}")
            await meshcore.commands.send_chan_msg(chan=channel_id, msg=message)
            return True, None
        except Exception as e:
            self.logger.error(f"Error sending channel message to {channel_id}: {e}", exc_info=True)
            return False, f"Error sending channel message: {e}"