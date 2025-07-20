import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .srcool_telnet import SRCOOLClient

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=30)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tripp Lite SRCOOL from a config entry."""
    host = entry.data["host"]
    port = entry.data.get("port", 23)
    username = entry.data["username"]
    password = entry.data["password"]

    client = SRCOOLClient(host, port, username, password)

    async def _async_update():
        _LOGGER.debug("Coordinator polling SRCOOL status...")
        try:
            return await hass.async_add_executor_job(client.get_status)
        except Exception as err:
            _LOGGER.error("Error updating SRCOOL: %s", err)
            raise UpdateFailed(f"SRCOOL update failed: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Tripp Lite SRCOOL",
        update_method=_async_update,
        update_interval=SCAN_INTERVAL,
    )

    # Initial poll
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, ["climate", "sensor"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["climate"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
