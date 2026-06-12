"""Host-level telnet session coordination for SRCOOL."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DEFAULT_PORT, DOMAIN
from .srcool_telnet import SRCOOLClient

_LOGGER = logging.getLogger(__name__)


def get_host_lock(hass: HomeAssistant, host: str) -> asyncio.Lock:
    """Return a per-host lock shared by the live client and config flow."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    locks: dict[str, asyncio.Lock] = domain_data.setdefault("host_locks", {})
    if host not in locks:
        locks[host] = asyncio.Lock()
    return locks[host]


def _credentials_unchanged(
    config_entry: ConfigEntry,
    user_input: dict,
) -> bool:
    return (
        config_entry.data.get("host") == user_input["host"]
        and config_entry.data.get("port", DEFAULT_PORT) == user_input["port"]
        and config_entry.data.get("username") == user_input["username"]
        and config_entry.data.get("password") == user_input["password"]
    )


async def async_validate_connection(
    hass: HomeAssistant,
    user_input: dict,
    *,
    config_entry: ConfigEntry | None = None,
) -> None:
    """Validate telnet credentials without overlapping live sessions."""
    host = user_input["host"]
    host_lock = get_host_lock(hass, host)
    loaded = (
        config_entry is not None
        and config_entry.entry_id in hass.data.get(DOMAIN, {})
    )
    loaded_client = None
    if loaded and config_entry is not None:
        loaded_client = hass.data[DOMAIN][config_entry.entry_id]["client"]
    creds_unchanged = (
        loaded
        and config_entry is not None
        and _credentials_unchanged(config_entry, user_input)
    )

    async with host_lock:
        if loaded_client and creds_unchanged:
            await loaded_client.check_connection(host_lock_held=True)
            return

        if loaded_client:
            await loaded_client.disconnect(host_lock_held=True)

        temp = SRCOOLClient(
            host,
            user_input["port"],
            user_input["username"],
            user_input["password"],
            host_lock=host_lock,
        )
        try:
            await temp.verify_connection(host_lock_held=True)
        except ConnectionError:
            if loaded_client:
                try:
                    await loaded_client.connect(host_lock_held=True)
                except ConnectionError:
                    _LOGGER.warning(
                        "Could not restore session after failed validation"
                    )
            raise
