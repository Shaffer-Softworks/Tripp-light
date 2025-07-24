import telnetlib
import logging
import re
from typing import Any, Dict

_LOGGER = logging.getLogger(__name__)

PROMPT_LOGIN = b"ogin:"       # matches Login: or login:
PROMPT_PASSWORD = b"assword:" # matches Password:
PROMPT_READY = b">>"          # menu prompt
TELNET_TIMEOUT = 10


class SRCOOLClient:
    def __init__(self, host, port, username, password):
        self._host = host
        self._port = port
        self._username = username
        self._password = password

    # -------------------------------
    # Internal helper: login and return session
    # -------------------------------
    def _login(self):
        _LOGGER.debug("Connecting to %s:%d", self._host, self._port)
        tn = telnetlib.Telnet(self._host, self._port, timeout=TELNET_TIMEOUT)
        tn.read_until(PROMPT_LOGIN, timeout=TELNET_TIMEOUT)
        tn.write(self._username.encode('ascii') + b'\r\n')
        tn.read_until(PROMPT_PASSWORD, timeout=TELNET_TIMEOUT)
        tn.write(self._password.encode('ascii') + b'\r\n')
        tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)
        _LOGGER.debug("Login successful.")
        return tn

    # -------------------------------
    # Internal helper: safely close session
    # -------------------------------
    def _logout(self, tn):
        try:
            tn.write(b"Q\r\n")
        except Exception:
            pass
        tn.close()
        _LOGGER.debug("Connection closed.")

    def get_diagnostics(self) -> dict:
        """Fetch and parse the About/Diagnostics screen (menu 5)."""
        _LOGGER.debug("Fetching diagnostics…")
        tn = self._login()
        try:
            tn.write(b"5\r\n")  # About
            raw = tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT).decode(errors="ignore")
        finally:
            self._logout(tn)

        _LOGGER.debug("About Screen:\n%s", raw)

        def extract(label: str, raw: str, default=None):
            for line in raw.splitlines():
                if label in line:
                    # grab everything after the first colon
                    val = line.split(":", 1)[1].strip()
                    return val
            return default

        return {
            "os":                   extract("OS", raw),
            "agent_type":           extract("Agent Type", raw),
            "mac_address":          extract("MAC Address", raw),
            "card_serial_number":   extract("Card Serial Number", raw),
            "driver_version":       extract("Driver Version", raw),
            "engine_version":       extract("Engine Version", raw),
            "driver_file_status":   extract("Driver File Status", raw),
        }

    # -------------------------------
    # Get combined device info and status
    # -------------------------------
    def get_status(self):
        _LOGGER.debug("Polling SRCOOL status...")
        tn = self._login()
        try:
            # --- Device Info Screen ---
            tn.write(b"1\r\n")  # Devices
            device_info_raw = tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT).decode(errors="ignore")

            # --- Status Screen ---
            tn.write(b"1\r\n")  # Status submenu
            status_raw = tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT).decode(errors="ignore")
        finally:
            self._logout(tn)

        _LOGGER.debug("Device Info Screen:\n%s", device_info_raw)
        _LOGGER.debug("Status Screen:\n%s", status_raw)

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
                    after = line[colon + 1 :].strip()
                    # split on two-or-more spaces to strip off any next column
                    parts = re.split(r"\s{2,}", after)
                    val = parts[0].strip()
                    try:
                        return cast(val)
                    except Exception:
                        return default
            return default

        # Device info
        device_info = {
            "device_name":    extract("Device Name",    device_info_raw),
            "vendor":         extract("Vendor",         device_info_raw),
            "product":        extract("Product",        device_info_raw),
            "protocol":       extract("Protocol",       device_info_raw),
            "date_installed": extract("Date Installed", device_info_raw),
            "state":          extract("State",          device_info_raw),
            "type":           extract("Type",           device_info_raw),
            "port_mode":      extract("Port Mode",      device_info_raw),
            "port_name":      extract("Port Name",      device_info_raw),
        }

        # Status info
        status = {
            "water_status": extract("Water Status", status_raw),
            "quiet_mode":   extract("Quiet Mode", status_raw),
            "mode":         (extract("Operating Mode", status_raw) or "off").lower(),
            "current_temp": extract(
                                "Return Air Temperature",
                                status_raw,
                                lambda v: float(v.split()[0]),
                                0,
                            ),
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

        # ─── Step B: Fetch Current “Set-Point” Temperature ───────────────────────
        tn = self._login()
        try:
            tn.write(b"1\r\n")  # Devices
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"3\r\n")  # Controls
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"2\r\n")  # Set Set Point
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

            tn.write(b"1\r\n")  # Temperature (F)
            setpoint_raw = tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT).decode(errors="ignore")
            _LOGGER.debug("Set‑Point Screen:\n%s", setpoint_raw)
        finally:
            self._logout(tn)

        # Parse "Value : 65" from the detail screen
        m = re.search(r"Value\s*:\s*([0-9]+(?:\.[0-9]+)?)", setpoint_raw)
        if m:
            status["target_temp"] = float(m.group(1))
        else:
            _LOGGER.warning("Could not parse target_temp from screen")

        # ─── Merge & Return ─────────────────────────────────────────────────────
        merged = {**device_info, **status}
        
        # ─── Now merge diagnostics ────────────────────────────
        try:
            diag = self.get_diagnostics()
            merged.update(diag)
        except Exception as err:
            _LOGGER.error("Error fetching diagnostics: %s", err)

        _LOGGER.debug("Final merged status: %s", merged)
        return merged
        
    # -------------------------------
    # Set target temperature
    # -------------------------------
    def set_target_temp(self, temp_f: float):
        _LOGGER.info("Setting target temperature to %.1f°F", temp_f)
        tn = self._login()
        try:
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
            _LOGGER.info(str(int(temp_f)).encode('ascii') + b"\r\n")
            _LOGGER.info("Target temperature set successfully.")
        finally:
            self._logout(tn)

    # -------------------------------
    # Set fan speed
    # -------------------------------
    def set_fan(self, speed: str):
        fan_map = {"low": "1", "medium": "2", "high": "3", "auto": "0"}
        code = fan_map.get(speed.lower())
        if code is None:
            _LOGGER.error("Invalid fan speed: %s", speed)
            return
        _LOGGER.info("Setting fan speed to %s", speed)
        tn = self._login()
        try:
            tn.write(b"1\r\n")  # Devices
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)
            tn.write(b"3\r\n")  # Controls
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)
            tn.write(b"4\r\n")  # Set Fan Speed
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)
            tn.write(code.encode('ascii') + b"\r\n")
            _LOGGER.info("Fan speed set successfully.")
        finally:
            self._logout(tn)

    # -------------------------------
    # Set mode (cool/on or off)
    # -------------------------------
    def set_mode(self, on: bool):
        _LOGGER.info("Setting mode to %s", "cooling" if on else "off")
        # NOTE: If there's a menu option to power on/off or set cooling, implement similarly
        # Placeholder logic (adjust if menu structure known):
        tn = self._login()
        try:
            if not on:
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
        finally:
            self._logout(tn)
