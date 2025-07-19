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
    def __init__(self, host: str, port: int, username: str, password: str):
        self._host = host
        self._port = port
        self._username = username
        self._password = password

    def _run(self, command: str | None = None) -> str:
        """Open a Telnet session, run a single command, return raw output."""
        _LOGGER.debug("Connecting to %s:%d", self._host, self._port)
        tn = telnetlib.Telnet(self._host, self._port, timeout=TELNET_TIMEOUT)

        # --- login ---
        tn.read_until(PROMPT_LOGIN, timeout=TELNET_TIMEOUT)
        tn.write(self._username.encode("ascii") + b"\r\n")
        tn.read_until(PROMPT_PASSWORD, timeout=TELNET_TIMEOUT)
        tn.write(self._password.encode("ascii") + b"\r\n")

        # wait for prompt
        tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

        # send command
        if command:
            _LOGGER.debug("Sending command: %s", command.replace("\n", "\\n"))
            tn.write(command.encode("ascii") + b"\r\n")
            tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)
            tn.write(command.encode("ascii") + b"\r\n")
            raw = tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)
        else:
            tn.write(b"\r\n")
            raw = tn.read_until(PROMPT_READY, timeout=TELNET_TIMEOUT)

        # exit
        tn.write(b"Q\r\n")
        tn.close()

        decoded = raw.decode(errors="ignore")
        _LOGGER.debug("Raw response:\n%s", decoded)
        return decoded

    def get_status(self) -> Dict[str, Any]:
        """Parse status output into a dict for HA."""
        raw = self._run("1")

        def extract(label: str, cast=lambda v: v, default=None):
            m = re.search(rf"{re.escape(label)}\s*:\s*(.+)", raw)
            return cast(m.group(1).strip()) if m else default

        return {
            "water_status": extract("Water Status"),
            "quiet_mode": extract("Quiet Mode"),
            "mode": (extract("Operating Mode") or "off").lower(),
            "current_temp": extract("Return Air Temperature", lambda v: float(v.split()[0]), 0),
            "auto_fan": (extract("Auto Fan Speed") or "off").lower(),
            "fan": (extract("Fan Speed") or "unknown").lower(),
            "target_temp": None,
        }

    def set_target_temp(self, temp_f: int):
        _LOGGER.info("Setting target temp to %s°F", temp_f)
        self._run(f"3\n2\n{int(temp_f)}")

    def set_mode(self, on: bool):
        _LOGGER.info("Setting mode to %s", "cooling" if on else "off")
        self._run("3\n1")

    def set_fan(self, speed: str):
        fan_map = {"low": "1", "medium": "2", "high": "3", "auto": "4"}
        code = fan_map.get(speed.lower(), "4")
        _LOGGER.info("Setting fan to %s", speed)
        self._run(f"3\n3\n{code}")
