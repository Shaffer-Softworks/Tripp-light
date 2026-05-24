"""Telnet client for SRCOOL devices with persistent session management."""
import logging
import re
import telnetlib
import threading
import time
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)

PROMPT_LOGIN = b"ogin:"     # matches "Login:" / "login:"
PROMPT_PASSWORD = b"assword:"  # matches "Password:"
PROMPT_READY = b">>"        # main-menu prompt
TELNET_TIMEOUT = 10
RETRY_COUNT = 3
RETRY_DELAY = 1


class SRCOOLClient:
    """Telnet client with one persistent session (serialized via lock)."""

    def __init__(self, host: str, port: int, username: str, password: str):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._tn: Optional[telnetlib.Telnet] = None
        self._lock = threading.RLock()

    def connect(self) -> None:
        """(Re)establish the Telnet session and log in."""
        with self._lock:
            self._connect_unlocked()

    def disconnect(self) -> None:
        """Close the Telnet session."""
        with self._lock:
            self._disconnect_unlocked()

    def verify_connection(self) -> None:
        """Log in and disconnect; for config-flow validation only."""
        with self._lock:
            try:
                self._connect_unlocked()
            finally:
                self._disconnect_unlocked()

    def get_status(
        self, *, include_diagnostics: bool = False
    ) -> Dict[str, Any]:
        """Fetch device info, status, and set-point; diagnostics optional."""
        with self._lock:
            return self._get_status_unlocked(
                include_diagnostics=include_diagnostics,
            )

    def get_diagnostics(self) -> Dict[str, Optional[str]]:
        """Fetch the About/Diagnostics screen (menu 5)."""
        with self._lock:
            return self._get_diagnostics_unlocked()

    def set_target_temp(self, temp_f: float) -> None:
        """Set the target temperature in Fahrenheit."""
        with self._lock:
            self._set_target_temp_unlocked(temp_f)

    def set_fan(self, speed: str) -> None:
        """Set the fan speed to low, medium, high, or auto."""
        with self._lock:
            self._set_fan_unlocked(speed)

    def shutdown(self) -> None:
        """Shut down the cooling unit (telnet has no power-on command)."""
        with self._lock:
            self._shutdown_unlocked()

    def set_dehumidifying(self, enabled: bool) -> None:
        """Enable or disable dehumidifying mode."""
        with self._lock:
            self._set_dehumidifying_unlocked(enabled)

    def _connect_unlocked(self) -> None:
        """(Re)establish session; caller must hold _lock."""
        last_exc: Optional[Exception] = None
        tn: Optional[telnetlib.Telnet] = None

        for attempt in range(1, RETRY_COUNT + 1):
            try:
                _LOGGER.debug(
                    "Connecting to %s:%d (attempt %d)",
                    self._host, self._port, attempt,
                )
                tn = telnetlib.Telnet(
                    self._host, self._port, timeout=TELNET_TIMEOUT)

                tn.read_until(PROMPT_LOGIN, TELNET_TIMEOUT)
                tn.write(self._username.encode("ascii") + b"\r\n")

                tn.read_until(PROMPT_PASSWORD, TELNET_TIMEOUT)
                tn.write(self._password.encode("ascii") + b"\r\n")

                tn.read_until(PROMPT_READY, TELNET_TIMEOUT)
                _LOGGER.debug("Login successful on attempt %d", attempt)

                self._tn = tn
                return

            except Exception as exc:
                last_exc = exc
                _LOGGER.warning("Login attempt %d failed: %s", attempt, exc)
                if tn is not None:
                    try:
                        tn.close()
                    except Exception:
                        pass
                    tn = None
                if attempt < RETRY_COUNT:
                    time.sleep(RETRY_DELAY)

        _LOGGER.error("All %d login attempts failed", RETRY_COUNT)
        raise ConnectionError(
            f"Could not connect/login to SRCOOL: {last_exc}") from last_exc

    def _disconnect_unlocked(self) -> None:
        """Close session; caller must hold _lock."""
        if not self._tn:
            return

        status_raw: Optional[bytes] = None
        try:
            self._tn.write(b"M\r\n")
            self._tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            self._tn.write(b"Q\r\n")
            status_raw = self._tn.read_until(
                PROMPT_READY, timeout=TELNET_TIMEOUT)
        except Exception:
            pass
        try:
            self._tn.close()
        except Exception:
            pass
        self._tn = None
        if status_raw is not None:
            _LOGGER.debug("Quit screen:\n%s", status_raw)
        _LOGGER.debug("Telnet session closed.")

    def _ensure_connection_unlocked(self) -> telnetlib.Telnet:
        """Return a live session; caller must hold _lock."""
        if not self._tn:
            self._connect_unlocked()
        return self._tn  # type: ignore[return-value]

    def _go_main_menu(self, tn: telnetlib.Telnet) -> None:
        tn.write(b"M\r\n")
        tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

    def _read_devices_screen(
        self, tn: telnetlib.Telnet, submenu: bytes
    ) -> str:
        """Navigate M → Devices → submenu and return the screen text."""
        self._go_main_menu(tn)
        tn.write(b"1\r\n")
        tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)
        tn.write(submenu)
        return tn.read_until(
            PROMPT_READY, TELNET_TIMEOUT
        ).decode("ascii", "ignore")

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

    def _get_status_unlocked(
        self, *, include_diagnostics: bool
    ) -> Dict[str, Any]:
        tn = self._ensure_connection_unlocked()

        try:
            status_raw = self._read_devices_screen(tn, b"1\r\n")
            id_raw = self._read_devices_screen(tn, b"2\r\n")
            prefs_raw = self._read_devices_screen(tn, b"5\r\n")
        except Exception as err:
            _LOGGER.warning("get_status step A failed, reconnecting: %s", err)
            self._disconnect_unlocked()
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

        fan_value = None
        for line in status_raw.splitlines():
            if line.lstrip().lower().startswith("fan speed"):
                after = line.split(":", 1)[1].strip()
                fan_value = after.split("  ")[0].strip().lower()
                break
        if not fan_value:
            _LOGGER.warning("Could not parse Fan Speed in status screen")
            fan_value = "unknown"
        status["fan"] = fan_value

        dehumid = extract("Dehumidifying Status", prefs_raw) or "unknown"
        status["dehumidifying_status"] = dehumid.lower()
        status["units"] = extract("Units", prefs_raw)

        try:
            self._go_main_menu(tn)

            tn.write(b"1\r\n")  # Devices
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"3\r\n")  # Controls
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"2\r\n")  # Set Set Point
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"1\r\n")  # Temperature (F)
            setpoint_raw = tn.read_until(
                PROMPT_READY, timeout=TELNET_TIMEOUT).decode(errors="ignore")
            _LOGGER.debug("Set-Point Screen:\n%s", setpoint_raw)
        except Exception as err:
            _LOGGER.warning("get_status step B failed, reconnecting: %s", err)
            self._disconnect_unlocked()
            raise

        m = re.search(r"Value\s*:\s*([0-9]+(?:\.[0-9]+)?)", setpoint_raw)
        if m:
            status["target_temp"] = float(m.group(1))
        else:
            _LOGGER.warning("Could not parse target_temp from screen")

        merged = {**device_info, **status}

        if include_diagnostics:
            try:
                merged.update(self._get_diagnostics_unlocked())
            except Exception as err:
                _LOGGER.warning("Error fetching diagnostics: %s", err)

        _LOGGER.debug("Final merged status: %s", merged)
        return merged

    def _get_diagnostics_unlocked(self) -> Dict[str, Optional[str]]:
        tn = self._ensure_connection_unlocked()
        try:
            self._go_main_menu(tn)

            tn.write(b"5\r\n")
            raw = tn.read_until(PROMPT_READY, TELNET_TIMEOUT).decode(
                "ascii", "ignore")
        except Exception as err:
            _LOGGER.warning("get_diagnostics failed, reconnecting: %s", err)
            self._disconnect_unlocked()
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

    def _set_target_temp_unlocked(self, temp_f: float) -> None:
        tn = self._ensure_connection_unlocked()
        try:
            self._go_main_menu(tn)

            tn.write(b"1\r\n")
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"3\r\n")
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"2\r\n")
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"1\r\n")
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(str(int(temp_f)).encode("ascii") + b"\r\n")
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)
            _LOGGER.debug("Target temperature set to %s°F", int(temp_f))
        except Exception:
            self._disconnect_unlocked()
            raise

    def _set_fan_unlocked(self, speed: str) -> None:
        code_map = {"low": "1", "medium": "2", "high": "3", "auto": "0"}
        code = code_map.get(speed.lower())
        if not code:
            _LOGGER.error("Invalid fan speed: %s", speed)
            return

        tn = self._ensure_connection_unlocked()
        try:
            self._go_main_menu(tn)

            tn.write(b"1\r\n")
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"3\r\n")
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"4\r\n")
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(code.encode("ascii") + b"\r\n")
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)
            _LOGGER.debug("Fan speed set to %s", speed)
        except Exception:
            self._disconnect_unlocked()
            raise

    def _shutdown_unlocked(self) -> None:
        tn = self._ensure_connection_unlocked()
        try:
            self._go_main_menu(tn)

            tn.write(b"1\r\n")  # Devices
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"3\r\n")  # Controls
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"3\r\n")  # Shut down device
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)
            tn.write(b"Y\r\n")
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)
            tn.write(b"E\r\n")
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)
            _LOGGER.debug("Device shut down")
        except Exception:
            self._disconnect_unlocked()
            raise

    def _set_dehumidifying_unlocked(self, enabled: bool) -> None:
        code = b"2\r\n" if enabled else b"1\r\n"
        tn = self._ensure_connection_unlocked()
        try:
            self._go_main_menu(tn)
            tn.write(b"1\r\n")
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)
            tn.write(b"5\r\n")
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)
            tn.write(b"1\r\n")
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)
            tn.write(code)
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)
            _LOGGER.debug(
                "Dehumidifying set to %s",
                "on" if enabled else "off",
            )
        except Exception:
            self._disconnect_unlocked()
            raise
