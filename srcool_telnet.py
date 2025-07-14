import asyncio, telnetlib, re, logging
from .const import TELNET_TIMEOUT
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)

class SRCOOLClient:
    """Minimal Telnet/SSH client for SRCOOLNET‑LX cards."""

    def __init__(self, host, port, username, password):
        self._host, self._port = host, port
        self._user, self._pwd = username, password
        self._lock = asyncio.Lock()

    async def _run(self, command: str) -> str:
        """Run command and return raw response."""
        async with self._lock:
            return await asyncio.to_thread(self._run_sync, command)

    def _run_sync(self, command: str) -> str:
        with telnetlib.Telnet(self._host, self._port, TELNET_TIMEOUT) as tn:
            tn.read_until(b"login: ")
            tn.write(self._user.encode() + b"\n")
            tn.read_until(b"Password: ")
            tn.write(self._pwd.encode() + b"\n")
            tn.read_until(b"> ")              # prompt
            tn.write(command.encode() + b"\n")
            output = tn.read_until(b"> ").decode()
            tn.write(b"exit\n")
            return output

    async def get_status(self) -> Dict[str, Any]:
        """
        Parse the newer **Device Status Menu** block, e.g.

            Water Status           : Not Full
            Quiet Mode             : Disabled
            Operating Mode         : Cooling
            Return Air Temperature : 66.0 F
            Auto Fan Speed         : On
            Fan Speed              : Medium
        """
        raw: str = await self._run("1\n")
        raw: str = await self._run("1\n")

        def _match(pattern: str, cast=lambda x: x, group: int = 1) -> Optional[Any]:
            m = re.search(pattern, raw, re.IGNORECASE)
            return cast(m.group(group).strip()) if m else None

        data: Dict[str, Any] = {
            # “house-keeping” flags
            "water_status": _match(r"Water\s+Status\s*:\s*([^\n]+)"),
            "quiet_mode":   _match(r"Quiet\s+Mode\s*:\s*([^\n]+)"),

            # HVAC state
            "mode":         (_match(r"Operating\s+Mode\s*:\s*([^\n]+)", str, 1) or "unknown").lower(),
            "current_temp": _match(r"Return\s+Air\s+Temperature\s*:\s*([\d\.]+)", float),
            "auto_fan":     (_match(r"Auto\s+Fan\s+Speed\s*:\s*([^\n]+)") or "off").lower(),
            "fan":          (_match(r"Fan\s+Speed\s*:\s*([^\n]+)") or "unknown").lower(),
        }
        return data

    # Simple setters ---------------------------------------------------------
    async def set_target_temp(self, temp_f): await self._run(f"device temp {temp_f}")
    async def set_mode(self, on: bool):      await self._run("device control on" if on else "device control off")
    async def set_fan(self, fan):            await self._run(f"device fan {fan}")
