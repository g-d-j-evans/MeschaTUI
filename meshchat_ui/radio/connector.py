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
import hashlib # Added for channel key generation

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

    @staticmethod
    def _generate_channel_key(channel_name: str) -> bytes:
        """
        Generates the channel key for a public hashtag channel.
        The key is the first 16 bytes of the SHA256 digest of the channel name.
        """
        sha256_hash = hashlib.sha256(channel_name.encode('utf-8')).digest()
        return sha256_hash[:16]

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
            self.logger.debug(f"get_contacts returned: {result}")
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
                        "public_key": key,
                        "out_path": contact_entry.get("out_path"),
                        "out_path_len": contact_entry.get("out_path_len")
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

    async def join_public_channel(self, channel_name: str) -> tuple[bool, str | None, list | None]:
        """
        Attempts to join a public hashtag channel.
        Finds an empty slot or prompts the user to overwrite.
        Returns: (success, message, extra_data)
        """
        meshcore = await self.get_meshcore()
        if meshcore is None:
            return False, "Radio not connected. Cannot join channel.", None

        channel_key = self._generate_channel_key(channel_name)
        channel_id_to_use = -1
        empty_slot_found = False
        already_joined = False
        used_channels = []

        self.logger.debug(f"Attempting to join channel {channel_name} with key {channel_key.hex()}")

        # 1. Check existing channels and find an empty slot
        for idx in range(BLE_MAX_CHANNEL_ATTEMPTS):
            try:
                chan_result = await meshcore.commands.get_channel(idx)
                if chan_result and chan_result.type != EventType.ERROR:
                    channel_info = chan_result.payload
                    current_channel_name = channel_info.get("channel_name")
                    current_channel_id = channel_info.get("channel_id") # Note: assuming channel_id might be different from idx

                    self.logger.debug(f"Channel {idx}: {current_channel_name} (ID: {current_channel_id})")

                    if current_channel_name == channel_name:
                        already_joined = True
                        channel_id_to_use = idx # Use existing slot
                        break
                    elif not current_channel_name and not empty_slot_found: # Assuming empty channel has no name
                        empty_slot_found = True
                        channel_id_to_use = idx
                    else:
                        used_channels.append({"id": idx, "name": current_channel_name or f"Unnamed {idx}"})
                elif not empty_slot_found: # If error or no result, treat as potentially empty
                    empty_slot_found = True
                    channel_id_to_use = idx

            except Exception as e:
                self.logger.warning(f"Error getting channel {idx}: {e}", exc_info=True)
                if not empty_slot_found:
                    empty_slot_found = True
                    channel_id_to_use = idx
        
        # 2. Assign channel to a slot
        if already_joined:
            self.logger.info(f"Already joined channel {channel_name} at slot {channel_id_to_use}")
            return True, None, None
        elif empty_slot_found and channel_id_to_use != -1:
            self.logger.debug(f"Empty slot found at index {channel_id_to_use}. Setting channel.")
            success, msg = await self._set_channel_config(meshcore, channel_id_to_use, channel_name, channel_key)
            return success, msg, None
        else:
            # No empty slots found and channel not already joined
            # Return special signal for UI to prompt for overwrite
            self.logger.warning(f"No empty channel slots available for {channel_name}. Used channels: {used_channels}")
            return False, "OVERWRITE_REQUIRED", used_channels
    
    async def overwrite_public_channel(self, channel_name: str, overwrite_channel_id: int) -> tuple[bool, str | None]:
        """
        Overwrites an existing channel with a new public hashtag channel.
        """
        meshcore = await self.get_meshcore()
        if meshcore is None:
            return False, "Radio not connected. Cannot overwrite channel."

        channel_key = self._generate_channel_key(channel_name)
        self.logger.debug(f"Overwriting channel {overwrite_channel_id} with {channel_name} (key: {channel_key.hex()})")

        return await self._set_channel_config(meshcore, overwrite_channel_id, channel_name, channel_key)

    async def _set_channel_config(self, meshcore: MeshCore, channel_idx: int, channel_name: str, channel_key: bytes) -> tuple[bool, str | None]:
        """Helper to set channel configuration."""
        try:
            set_result = await meshcore.commands.set_channel(channel_idx, channel_name, channel_key)
            if set_result and set_result.type != EventType.ERROR:
                self.logger.info(f"Successfully set channel {channel_name} in slot {channel_idx}")
                # Refresh channels list in app after successful join/overwrite
                # This should probably be handled by the app's get_contacts_and_channels worker
                return True, None
            else:
                error_msg = set_result.payload.get("error") if set_result else "Unknown error from set_channel"
                return False, f"Failed to set channel {channel_name}: {error_msg}"
        except Exception as e:
            self.logger.error(f"Error setting channel {channel_name}: {e}", exc_info=True)
            return False, f"Exception while setting channel: {e}"

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

    async def send_advert(self) -> tuple[bool, str | None]:
        """Sends a flood advert."""
        meshcore = await self.get_meshcore()
        if meshcore is None:
            return False, "Radio not connected."
        try:
            result = await meshcore.commands.send_advert(flood=True)
            if result and result.type == EventType.OK:
                self.logger.info("Flood advert sent successfully.")
                return True, None
            else:
                return False, f"Failed to send advert: {result}"
        except Exception as e:
            self.logger.error(f"Error sending advert: {e}", exc_info=True)
            return False, str(e)

    async def send_message(self, message: str, destination_id: str) -> tuple[bool, str | None, Event | None]:
        """Sends a message to a specified destination with automatic retries."""
        meshcore = await self.get_meshcore()
        if meshcore is None:
            return False, "Radio not connected. Cannot send message.", None
        try:
            self.logger.debug(f"Sending message to {destination_id} with retry")
            # send_msg_with_retry returns the MSG_SENT result event if successful (ACK received), else None
            # Increasing attempts to improve delivery chance via repeaters
            result = await meshcore.commands.send_msg_with_retry(
                destination_id, message, max_attempts=4, max_flood_attempts=3, flood_after=2
            )
            if result:
                return True, None, result
            else:
                return False, "Message delivery failed after retries (no ACK received)", None
        except Exception as e:
            self.logger.error(f"Error sending message to {destination_id}: {e}", exc_info=True)
            return False, f"Error sending message: {e}", None

    async def send_channel_message(self, message: str, channel_id: int) -> tuple[bool, str | None, Event | None]:
        """Sends a message to a specified channel."""
        meshcore = await self.get_meshcore()
        if meshcore is None:
            return False, "Radio not connected. Cannot send channel message.", None
        try:
            self.logger.debug(f"Sending channel message to {channel_id}")
            result = await meshcore.commands.send_chan_msg(chan=channel_id, msg=message)
            if result and result.type != EventType.ERROR:
                return True, None, result
            else:
                error_msg = result.payload.get("error", "Unknown error") if result else "No response"
                return False, error_msg, result
        except Exception as e:
            self.logger.error(f"Error sending channel message to {channel_id}: {e}", exc_info=True)
            return False, f"Error sending channel message: {e}", None

    async def add_contact(self, contact_data: dict) -> tuple[bool, str | None]:
        """Adds a contact to the radio."""
        meshcore = await self.get_meshcore()
        if meshcore is None:
            return False, "Radio not connected."
        try:
            # Check if we have existing contact info to preserve path
            public_key = contact_data.get("public_key") or contact_data.get("key")
            if public_key and hasattr(self.app, "contacts"):
                existing_contact = next((c for c in self.app.contacts if c.get("public_key") == public_key), None)
                if existing_contact:
                    # If new data lacks path or has "unknown" (-1) path, try to use existing
                    new_len = contact_data.get("out_path_len", -1)
                    
                    if "out_path" not in contact_data or new_len < 0:
                         if "out_path" in existing_contact:
                             contact_data["out_path"] = existing_contact["out_path"]
                         if "out_path_len" in existing_contact:
                             contact_data["out_path_len"] = existing_contact["out_path_len"]

            # ensure defaults if missing
            contact_data.setdefault("out_path", "00" * 32)
            contact_data.setdefault("out_path_len", 0)
            contact_data.setdefault("flags", 0)
            contact_data.setdefault("last_advert", 0)
            contact_data.setdefault("adv_lat", 0.0)
            contact_data.setdefault("adv_lon", 0.0)
            contact_data.setdefault("type", 1)  # Client

            # Ensure 'key' is present, as meshcore likely expects it
            if "key" not in contact_data and "public_key" in contact_data:
                contact_data["key"] = contact_data["public_key"]

            # Handle out_path: Ensure it is a HEX STRING, not bytes.
            out_path = contact_data.get("out_path")
            
            # If out_path is empty string or None, set to default hex string
            if not out_path:
                 contact_data["out_path"] = "00" * 32
                 # Do not force out_path_len to 0. Leave it as is (often -1 for unknown).
            
            # If it was somehow bytes (legacy/error), convert back to hex string
            elif isinstance(out_path, bytes):
                contact_data["out_path"] = out_path.hex()

            # Ensure out_path_len is NOT forced to 0 even if path is zeros
            # This matches the state of other contacts in the logs (len: -1)

            self.logger.debug(f"Adding contact with data: {contact_data}")

            result = await meshcore.commands.add_contact(contact_data)
            self.logger.debug(f"add_contact response: {result}")
            
            if result and result.type == EventType.OK:
                return True, None
            else:
                error_msg = result.payload.get("error", "Unknown error") if result else "Timeout/No response"
                self.logger.error(f"Failed to add contact: {error_msg}")
                return False, f"Failed to add contact: {error_msg}"
        except Exception as e:
            self.logger.error(f"Error adding contact: {e}", exc_info=True)
            return False, str(e)

    async def remove_contact(self, public_key: str) -> tuple[bool, str | None]:
        """Removes a contact from the radio."""
        meshcore = await self.get_meshcore()
        if meshcore is None:
            return False, "Radio not connected."
        try:
            self.logger.debug(f"Removing contact: {public_key}")
            result = await meshcore.commands.remove_contact(public_key)
            self.logger.debug(f"remove_contact response: {result}")
            if result and result.type == EventType.OK:
                return True, None
            else:
                error_msg = result.payload.get("error", "Unknown error") if result else "Timeout/No response"
                self.logger.error(f"Failed to remove contact: {error_msg}")
                return False, f"Failed to remove contact: {error_msg}"
        except Exception as e:
            self.logger.error(f"Error removing contact: {e}", exc_info=True)
            return False, str(e)