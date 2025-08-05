"""Telnet client for SRCOOL devices with persistent session management."""
import telnetlib
import logging
import re
import time
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)

PROMPT_LOGIN = b"ogin:"     # matches "Login:" / "login:"
PROMPT_PASSWORD = b"assword:"  # matches "Password:"
PROMPT_READY = b">>"        # main‑menu prompt
TELNET_TIMEOUT = 10
RETRY_COUNT = 3
RETRY_DELAY = 1


class SRCOOLClient:
    """Telnet client with one persistent session."""

    def __init__(self, host: str, port: int, username: str, password: str):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._tn: Optional[telnetlib.Telnet] = None

    def connect(self) -> None:
        """(Re)establish the Telnet session and log in."""
        last_exc: Optional[Exception] = None

        for attempt in range(1, RETRY_COUNT + 1):
            try:
                _LOGGER.debug("Connecting to %s:%d (attempt %d)",
                              self._host, self._port, attempt)
                tn = telnetlib.Telnet(
                    self._host, self._port, timeout=TELNET_TIMEOUT)

                # login prompt
                tn.read_until(PROMPT_LOGIN, TELNET_TIMEOUT)
                tn.write(self._username.encode("ascii") + b"\r\n")

                # password prompt
                tn.read_until(PROMPT_PASSWORD, TELNET_TIMEOUT)
                tn.write(self._password.encode("ascii") + b"\r\n")

                # main menu
                tn.read_until(PROMPT_READY, TELNET_TIMEOUT)
                _LOGGER.debug("Login successful on attempt %d", attempt)

                self._tn = tn
                return

            except Exception as exc:
                last_exc = exc
                _LOGGER.warning("Login attempt %d failed: %s", attempt, exc)
                try:
                    tn.close()
                except Exception:
                    pass
                if attempt < RETRY_COUNT:
                    time.sleep(RETRY_DELAY)

        _LOGGER.error("All %d login attempts failed", RETRY_COUNT)
        raise ConnectionError(
            f"Could not connect/login to SRCOOL: {last_exc}") from last_exc

    def disconnect(self) -> None:
        """Close the Telnet session."""
        if self._tn:
            try:
                self._tn.write(b"M\r\n")  # Return to main menu
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
            _LOGGER.debug("Status Screen:\n%s", status_raw)
            _LOGGER.debug("Telnet session closed.")

    def _ensure_connection(self) -> telnetlib.Telnet:
        """Return a live session, connecting if needed."""
        if not self._tn:
            self.connect()
        return self._tn  # type: ignore

    def get_status(self) -> Dict[str, Any]:
        """Fetch device info, status, set‑point, and diagnostics."""
        tn = self._ensure_connection()

        try:
            tn.write(b"M\r\n")  # Return to main menu
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            # ── Device Info & Status ──────────────────────────────
            tn.write(b"1\r\n")  # Devices
            info_raw = tn.read_until(
                PROMPT_READY, TELNET_TIMEOUT).decode("ascii", "ignore")

            tn.write(b"1\r\n")  # Status submenu
            status_raw = tn.read_until(
                PROMPT_READY, TELNET_TIMEOUT).decode("ascii", "ignore")
        except Exception as err:
            _LOGGER.warning("get_status step A failed, reconnecting: %s", err)
            self.disconnect()
            raise

        _LOGGER.debug("Info screen:\n%s", info_raw)
        _LOGGER.debug("Status screen:\n%s", status_raw)

        def extract(label: str, raw: str, cast=lambda v: v, default=None):
            """
            For each line containing `label`, locate the colon after that label,
            take everything after it, then split on two+ spaces to isolate the first value.
            """
            for line in raw.splitlines():
                if label in line:
                    # find colon that follows the label text
                    idx = line.lower().find(label.lower())
                    colon = line.find(":", idx)
                    if colon == -1:
                        continue
                    after = line[colon + 1:].strip()
                    # split on two-or-more spaces to strip off any next column
                    parts = re.split(r"\s{2,}", after)
                    val = parts[0].strip()
                    try:
                        return cast(val)
                    except Exception:
                        return default
            return default

        device_info = {
            "device_name":    extract("Device Name",    info_raw),
            "vendor":         extract("Vendor",         info_raw),
            "product":        extract("Product",        info_raw),
            "protocol":       extract("Protocol",       info_raw),
            "date_installed": extract("Date Installed", info_raw),
            "state":          extract("State",          info_raw),
            "type":           extract("Type",           info_raw),
            "port_mode":      extract("Port Mode",      info_raw),
            "port_name":      extract("Port Name",      info_raw),
        }

        status = {
            "water_status": extract("Water Status", status_raw),
            "quiet_mode":   extract("Quiet Mode",   status_raw),
            "mode":         (extract("Operating Mode", status_raw) or "off").lower(),
            "current_temp": extract("Return Air Temperature", 
                                    status_raw, lambda v: float(v.split()[0]), 0.0),
            "auto_fan":     (extract("Auto Fan Speed", status_raw) or "off").lower(),
        }

        # precise Fan Speed parsing
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

        # ── Current Set‑Point ────────────────────────────────────
        try:
            tn.write(b"M\r\n")  # Return to main menu
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"1\r\n")  # Devices
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"3\r\n")  # Controls
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"2\r\n")  # Set Set Point
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"1\r\n")  # Temperature (F)
            setpoint_raw = tn.read_until(
                PROMPT_READY, timeout=TELNET_TIMEOUT).decode(errors="ignore")
            _LOGGER.debug("Set‑Point Screen:\n%s", setpoint_raw)
        except Exception as err:
            _LOGGER.warning("get_status step B failed, reconnecting: %s", err)
            self.disconnect()
            raise

        # Parse "Value : 65" from the detail screen
        m = re.search(r"Value\s*:\s*([0-9]+(?:\.[0-9]+)?)", setpoint_raw)
        if m:
            status["target_temp"] = float(m.group(1))
        else:
            _LOGGER.warning("Could not parse target_temp from screen")

        # ── Merge Diagnostics ────────────────────────────────────
        merged = {**device_info, **status}

        try:
            merged.update(self.get_diagnostics())
        except Exception as err:
            _LOGGER.error("Error fetching diagnostics: %s", err)

        _LOGGER.debug("Final merged status: %s", merged)
        return merged

    def get_diagnostics(self) -> Dict[str, Optional[str]]:
        """Fetch the About/Diagnostics screen (menu 5)."""
        tn = self._ensure_connection()
        try:
            tn.write(b"M\r\n")  # Return to main menu
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"5\r\n")
            raw = tn.read_until(PROMPT_READY, TELNET_TIMEOUT).decode(
                "ascii", "ignore")
        except Exception as err:
            _LOGGER.warning("get_diagnostics failed, reconnecting: %s", err)
            self.disconnect()
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

    def set_target_temp(self, temp_f: float) -> None:
        """Set the target temperature in Fahrenheit."""
        tn = self._ensure_connection()
        try:
            tn.write(b"M\r\n")  # Return to main menu
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"1\r\n")  # Devices
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"3\r\n")  # Controls
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"2\r\n")  # Set Set Point
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"1\r\n")  # Temperature
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(str(int(temp_f)).encode('ascii') + b"\r\n")
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            _LOGGER.debug(str(int(temp_f)).encode('ascii') + b"\r\n")
            _LOGGER.debug("Target temperature set successfully.")
        except Exception:
            self.disconnect()
            raise

    def set_fan(self, speed: str) -> None:
        """Set the fan speed to low, medium, high, or auto."""
        code_map = {"low": "1", "medium": "2", "high": "3", "auto": "0"}
        code = code_map.get(speed.lower())
        if not code:
            _LOGGER.error("Invalid fan speed: %s", speed)
            return
        tn = self._ensure_connection()
        try:
            tn.write(b"M\r\n")  # Return to main menu
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"1\r\n")  # Devices
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"3\r\n")  # Controls
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"4\r\n")  # Set Fan Speed
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(code.encode('ascii') + b"\r\n")
            _LOGGER.debug("Fan speed set successfully.")
        except Exception:
            self.disconnect()
            raise

    def set_mode(self, on: bool) -> None:
        """Set the operating mode to on or off."""
        tn = self._ensure_connection()
        try:
            if not on:
                tn.write(b"M\r\n")  # Return to main menu
                tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

                tn.write(b"1\r\n")  # Devices
                tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

                tn.write(b"3\r\n")  # Controls
                tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

                tn.write(b"3\r\n")  # Shut down device
                tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

                tn.write(b"Y\r\n")  # Yes to continue
                tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

                tn.write(b"E\r\n")  # Execute
                tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)
            else:
                tn.write(b"5\r\n")  # example
        except Exception:
            self.disconnect()
            raise
