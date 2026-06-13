"""Telnet client for SRCOOL devices with persistent session management."""
from __future__ import annotations

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

import telnetlib3
from telnetlib3.stream_reader import TelnetReader
from telnetlib3.stream_writer import TelnetWriter

_LOGGER = logging.getLogger(__name__)

PROMPT_LOGIN = b"ogin:"     # matches "Login:" / "login:"
PROMPT_PASSWORD = b"assword:"  # matches "Password:"
PROMPT_READY = b">>"        # main-menu prompt
TELNET_TIMEOUT = 10
RETRY_COUNT = 3
RETRY_DELAY = 1
STATUS_SCREEN_MARKER = "Device Status Menu"

FAN_SPEED_ALIASES = {
    'med': 'medium',
}


class SRCOOLClient:
    """Async telnet client with one persistent session."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        *,
        host_lock: asyncio.Lock | None = None,
    ):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._reader: TelnetReader | None = None
        self._writer: TelnetWriter | None = None
        self._host_lock = host_lock or asyncio.Lock()
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def _session_lock(
        self, *, host_lock_held: bool = False
    ) -> AsyncIterator[None]:
        if host_lock_held:
            await self._lock.acquire()
            try:
                yield
            finally:
                self._lock.release()
        else:
            async with self._host_lock:
                async with self._lock:
                    yield

    async def connect(self, *, host_lock_held: bool = False) -> None:
        """(Re)establish the Telnet session and log in."""
        async with self._session_lock(host_lock_held=host_lock_held):
            await self._connect_unlocked()

    async def disconnect(self, *, host_lock_held: bool = False) -> None:
        """Close the Telnet session."""
        async with self._session_lock(host_lock_held=host_lock_held):
            await self._disconnect_unlocked()

    async def verify_connection(self, *, host_lock_held: bool = False) -> None:
        """Log in and disconnect; for config-flow validation only."""
        async with self._session_lock(host_lock_held=host_lock_held):
            try:
                await self._connect_unlocked()
            finally:
                await self._disconnect_unlocked()

    async def check_connection(self, *, host_lock_held: bool = False) -> None:
        """Confirm the live session responds (M → >>). Used by config flow."""
        async with self._session_lock(host_lock_held=host_lock_held):
            if not self._writer:
                await self._connect_unlocked()
            await self._go_main_menu_unlocked()

    async def get_status(
        self, *, include_diagnostics: bool = False
    ) -> Dict[str, Any]:
        """Fetch device info, status, and set-point; diagnostics optional."""
        async with self._session_lock():
            return await self._get_status_unlocked(
                include_diagnostics=include_diagnostics,
            )

    async def get_diagnostics(self) -> Dict[str, Optional[str]]:
        """Fetch the About/Diagnostics screen (menu 5)."""
        async with self._session_lock():
            return await self._get_diagnostics_unlocked()

    async def set_target_temp(self, temp_f: float) -> None:
        """Set the target temperature in Fahrenheit."""
        async with self._session_lock():
            await self._set_target_temp_unlocked(temp_f)

    async def set_fan(self, speed: str) -> None:
        """Set the fan speed to low, medium, high, or auto."""
        async with self._session_lock():
            await self._set_fan_unlocked(speed)

    async def shutdown(self) -> None:
        """Shut down the cooling unit (telnet has no power-on command)."""
        async with self._session_lock():
            await self._shutdown_unlocked()

    async def set_dehumidifying(self, enabled: bool) -> None:
        """Enable or disable dehumidifying mode."""
        async with self._session_lock():
            await self._set_dehumidifying_unlocked(enabled)

    async def _write_unlocked(self, data: bytes) -> None:
        assert self._writer is not None
        self._writer.write(data)
        await self._writer.drain()

    async def _read_until_unlocked(
        self, sep: bytes, *, timeout: float = TELNET_TIMEOUT
    ) -> str:
        assert self._reader is not None
        raw = await asyncio.wait_for(
            self._reader.readuntil(sep), timeout=timeout
        )
        return raw.decode("ascii", "ignore")

    async def _close_writer_unlocked(self) -> None:
        if not self._writer:
            return
        try:
            self._writer.close()
            await self._writer.wait_closed()
        except Exception:
            pass
        self._reader = None
        self._writer = None

    async def _connect_unlocked(self) -> None:
        """(Re)establish session; caller must hold _lock."""
        last_exc: Optional[Exception] = None

        for attempt in range(1, RETRY_COUNT + 1):
            reader: TelnetReader | None = None
            writer: TelnetWriter | None = None
            try:
                _LOGGER.debug(
                    "Connecting to %s:%d (attempt %d)",
                    self._host, self._port, attempt,
                )
                reader, writer = await telnetlib3.open_connection(
                    self._host,
                    self._port,
                    connect_timeout=TELNET_TIMEOUT,
                    encoding=False,
                )
                self._reader = reader
                self._writer = writer

                await self._read_until_unlocked(PROMPT_LOGIN)
                await self._write_unlocked(self._username.encode("ascii") + b"\r\n")

                await self._read_until_unlocked(PROMPT_PASSWORD)
                await self._write_unlocked(self._password.encode("ascii") + b"\r\n")

                await self._read_until_unlocked(PROMPT_READY)
                _LOGGER.debug("Login successful on attempt %d", attempt)
                return

            except Exception as exc:
                last_exc = exc
                _LOGGER.warning("Login attempt %d failed: %s", attempt, exc)
                self._reader = reader
                self._writer = writer
                await self._close_writer_unlocked()
                if attempt < RETRY_COUNT:
                    await asyncio.sleep(RETRY_DELAY)

        _LOGGER.error("All %d login attempts failed", RETRY_COUNT)
        raise ConnectionError(
            f"Could not connect/login to SRCOOL: {last_exc}") from last_exc

    async def _disconnect_unlocked(self) -> None:
        """Close session; caller must hold _lock."""
        if not self._writer:
            return

        status_raw: Optional[str] = None
        try:
            await self._write_unlocked(b"M\r\n")
            await self._read_until_unlocked(PROMPT_READY)

            await self._write_unlocked(b"Q\r\n")
            status_raw = await self._read_until_unlocked(PROMPT_READY)
        except Exception:
            pass
        await self._close_writer_unlocked()
        if status_raw is not None:
            _LOGGER.debug("Quit screen:\n%s", status_raw)
        _LOGGER.debug("Telnet session closed.")

    async def _ensure_connection_unlocked(self) -> None:
        """Ensure a live session; caller must hold _lock."""
        if not self._writer:
            await self._connect_unlocked()

    async def _go_main_menu_unlocked(self) -> None:
        await self._write_unlocked(b"M\r\n")
        await self._read_until_unlocked(PROMPT_READY)

    async def _commit_control_value_unlocked(self, value: str) -> None:
        """Apply a Control Data edit (value entry, Execute, confirm)."""
        await self._write_unlocked(value.encode("ascii") + b"\r\n")
        await self._read_until_unlocked(PROMPT_READY)
        await self._write_unlocked(b"E\r\n")
        await self._read_until_unlocked(PROMPT_READY)
        await self._write_unlocked(b"Y\r\n")
        await self._read_until_unlocked(PROMPT_READY)

    async def _read_devices_screen(self, submenu: bytes) -> str:
        """Navigate M → Devices → submenu and return the screen text."""
        await self._go_main_menu_unlocked()
        await self._write_unlocked(b"1\r\n")
        await self._read_until_unlocked(PROMPT_READY)
        await self._write_unlocked(submenu)
        return await self._read_until_unlocked(PROMPT_READY)

    @staticmethod
    def _extract_field(
        label: str,
        raw: str,
        cast=lambda v: v,
        default=None,
    ):
        """Parse a labeled column from a telnet status screen."""
        for line in raw.splitlines():
            if label in line:
                idx = line.lower().find(label.lower())
                colon = line.find(":", idx)
                if colon == -1:
                    continue
                after = line[colon + 1:].strip()
                parts = re.split(r"\s{2,}", after)
                val = parts[0].strip()
                try:
                    return cast(val)
                except Exception:
                    return default
        return default

    @staticmethod
    def _normalize_fan_speed(value: Optional[str]) -> Optional[str]:
        """Map device fan labels to integration fan modes."""
        if not value:
            return None
        normalized = value.lower()
        return FAN_SPEED_ALIASES.get(normalized, normalized)

    @staticmethod
    def _parse_fan_speed(status_raw: str) -> Optional[str]:
        """Return fan speed from status screen (not Auto Fan Speed)."""
        for line in status_raw.splitlines():
            stripped = line.lstrip()
            if stripped.lower().startswith("auto fan"):
                continue
            match = re.match(r"Fan Speed\s*:\s*(\S+)", stripped, re.I)
            if match:
                return SRCOOLClient._normalize_fan_speed(match.group(1))
        return None

    @staticmethod
    def _parse_target_temp(prefs_raw: str) -> Optional[float]:
        """Read committed setpoint from Preferences screen."""
        return SRCOOLClient._extract_field(
            "Set Point Temperature",
            prefs_raw,
            lambda v: float(v.split()[0]),
            None,
        )

    async def _fetch_status_screens_unlocked(
        self,
    ) -> tuple[str, str, str]:
        """Read status, identification, and preferences screens."""
        status_raw = await self._read_devices_screen(b"1\r\n")
        if STATUS_SCREEN_MARKER not in status_raw:
            raise ValueError(
                "Unexpected status screen (session out of sync)"
            )
        id_raw = await self._read_devices_screen(b"2\r\n")
        prefs_raw = await self._read_devices_screen(b"5\r\n")
        return status_raw, id_raw, prefs_raw

    async def _get_status_unlocked(
        self, *, include_diagnostics: bool
    ) -> Dict[str, Any]:
        last_err: Optional[Exception] = None

        for attempt in range(1, 3):
            await self._ensure_connection_unlocked()
            try:
                merged = await self._get_status_once_unlocked(
                    include_diagnostics=include_diagnostics
                )
                return merged
            except Exception as err:
                last_err = err
                _LOGGER.warning(
                    "get_status attempt %d failed, reconnecting: %s",
                    attempt, err,
                )
                await self._disconnect_unlocked()

        raise ConnectionError(
            f"Could not read SRCOOL status: {last_err}"
        ) from last_err

    async def _get_status_once_unlocked(
        self,
        *,
        include_diagnostics: bool,
    ) -> Dict[str, Any]:
        try:
            status_raw, id_raw, prefs_raw = (
                await self._fetch_status_screens_unlocked()
            )
        except Exception as err:
            _LOGGER.warning("get_status step A failed: %s", err)
            raise

        _LOGGER.debug("Status screen:\n%s", status_raw)
        _LOGGER.debug("Identification screen:\n%s", id_raw)
        _LOGGER.debug("Preferences screen:\n%s", prefs_raw)

        extract = self._extract_field

        device_info = {
            "device_name":    extract("Device Name",    id_raw),
            "location":       extract("Location",       id_raw),
            "region":         extract("Region",         id_raw),
            "vendor":         extract("Vendor",         id_raw),
            "product":        extract("Product",        id_raw),
            "protocol":       extract("Protocol",       id_raw),
            "date_installed": extract("Date Installed", id_raw),
            "state":          extract("State",          id_raw),
            "type":           extract("Type",           id_raw),
            "port_mode":      extract("Port Mode",      id_raw),
            "port_name":      extract("Port Name",      id_raw),
            "serial_number":  extract("Serial Number",  id_raw),
            "asset_tag":      extract("Asset Tag",      id_raw),
        }

        status = {
            "water_status": extract("Water Status", status_raw),
            "quiet_mode":   extract("Quiet Mode",   status_raw),
            "mode": (
                extract("Operating Mode", status_raw) or "off"
            ).lower(),
            "current_temp": extract(
                "Return Air Temperature",
                status_raw,
                lambda v: float(v.split()[0]),
                0.0,
            ),
            "auto_fan": (
                extract("Auto Fan Speed", status_raw) or "off"
            ).lower(),
        }

        if status["auto_fan"] == "on":
            status["fan"] = "auto"
        else:
            fan_value = self._parse_fan_speed(status_raw)
            if not fan_value:
                _LOGGER.warning(
                    "Could not parse Fan Speed in status screen"
                )
                fan_value = "unknown"
            status["fan"] = fan_value

        dehumid = extract("Dehumidifying Status", prefs_raw) or "unknown"
        status["dehumidifying_status"] = dehumid.lower()
        status["units"] = extract("Units", prefs_raw)

        target_temp = self._parse_target_temp(prefs_raw)
        if target_temp is not None:
            status["target_temp"] = target_temp
        else:
            _LOGGER.warning(
                "Could not parse Set Point Temperature from preferences"
            )

        merged = {**device_info, **status}

        if include_diagnostics:
            try:
                merged.update(await self._get_diagnostics_unlocked())
            except Exception as err:
                _LOGGER.warning("Error fetching diagnostics: %s", err)

        _LOGGER.debug("Final merged status: %s", merged)
        return merged

    async def _get_diagnostics_unlocked(self) -> Dict[str, Optional[str]]:
        await self._ensure_connection_unlocked()
        try:
            await self._go_main_menu_unlocked()
            await self._write_unlocked(b"5\r\n")
            raw = await self._read_until_unlocked(PROMPT_READY)
        except Exception as err:
            _LOGGER.warning("get_diagnostics failed, reconnecting: %s", err)
            await self._disconnect_unlocked()
            raise

        _LOGGER.debug("Diagnostics screen:\n%s", raw)

        def extract(label: str, text: str) -> Optional[str]:
            for line in text.splitlines():
                if label in line:
                    return line.split(":", 1)[1].strip()
            return None

        return {
            "os":                  extract("OS", raw),
            "agent_type":          extract("Agent Type", raw),
            "mac_address":         extract("MAC Address", raw),
            "card_serial_number":  extract("Card Serial Number", raw),
            "driver_version":      extract("Driver Version", raw),
            "engine_version":      extract("Engine Version", raw),
            "driver_file_status":  extract("Driver File Status", raw),
        }

    async def _set_target_temp_unlocked(self, temp_f: float) -> None:
        await self._ensure_connection_unlocked()
        try:
            await self._go_main_menu_unlocked()

            await self._write_unlocked(b"1\r\n")
            await self._read_until_unlocked(PROMPT_READY)

            await self._write_unlocked(b"3\r\n")
            await self._read_until_unlocked(PROMPT_READY)

            await self._write_unlocked(b"2\r\n")
            await self._read_until_unlocked(PROMPT_READY)

            await self._write_unlocked(b"1\r\n")
            await self._read_until_unlocked(PROMPT_READY)

            await self._commit_control_value_unlocked(str(int(temp_f)))
            await self._go_main_menu_unlocked()
            _LOGGER.debug("Target temperature set to %s°F", int(temp_f))
        except Exception:
            await self._disconnect_unlocked()
            raise

    async def _set_fan_unlocked(self, speed: str) -> None:
        code_map = {"low": "1", "medium": "2", "high": "3", "auto": "0"}
        code = code_map.get(speed.lower())
        if not code:
            _LOGGER.error("Invalid fan speed: %s", speed)
            return

        await self._ensure_connection_unlocked()
        try:
            await self._go_main_menu_unlocked()

            await self._write_unlocked(b"1\r\n")
            await self._read_until_unlocked(PROMPT_READY)

            await self._write_unlocked(b"3\r\n")
            await self._read_until_unlocked(PROMPT_READY)

            await self._write_unlocked(b"4\r\n")
            await self._read_until_unlocked(PROMPT_READY)

            await self._write_unlocked(b"1\r\n")
            await self._read_until_unlocked(PROMPT_READY)

            await self._commit_control_value_unlocked(code)
            await self._go_main_menu_unlocked()
            _LOGGER.debug("Fan speed set to %s", speed)
        except Exception:
            await self._disconnect_unlocked()
            raise

    async def _shutdown_unlocked(self) -> None:
        await self._ensure_connection_unlocked()
        try:
            await self._go_main_menu_unlocked()

            await self._write_unlocked(b"1\r\n")  # Devices
            await self._read_until_unlocked(PROMPT_READY)

            await self._write_unlocked(b"3\r\n")  # Controls
            await self._read_until_unlocked(PROMPT_READY)

            await self._write_unlocked(b"3\r\n")  # Shut down device
            await self._read_until_unlocked(PROMPT_READY)
            await self._write_unlocked(b"Y\r\n")
            await self._read_until_unlocked(PROMPT_READY)
            await self._go_main_menu_unlocked()
            _LOGGER.debug("Device shut down")
        except Exception:
            await self._disconnect_unlocked()
            raise

    async def _set_dehumidifying_unlocked(self, enabled: bool) -> None:
        code = b"2\r\n" if enabled else b"1\r\n"
        await self._ensure_connection_unlocked()
        try:
            await self._go_main_menu_unlocked()
            await self._write_unlocked(b"1\r\n")
            await self._read_until_unlocked(PROMPT_READY)
            await self._write_unlocked(b"5\r\n")
            await self._read_until_unlocked(PROMPT_READY)
            await self._write_unlocked(b"1\r\n")
            await self._read_until_unlocked(PROMPT_READY)
            await self._write_unlocked(code)
            await self._read_until_unlocked(PROMPT_READY)
            await self._go_main_menu_unlocked()
            _LOGGER.debug(
                "Dehumidifying set to %s",
                "on" if enabled else "off",
            )
        except Exception:
            await self._disconnect_unlocked()
            raise
