"""Climate platform for Tripp Lite SRCOOL."""
import logging

from datetime import timedelta
import telnetlib  # to catch ConnectionError
from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .srcool_telnet import SRCOOLClient

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tripp Lite SRCOOL from a config entry."""
    data = entry.data
    client = SRCOOLClient(
        data["host"],
        data.get("port", 23),
        data["username"],
        data["password"]
    )

    # Open the Telnet session once at startup
    try:
        await hass.async_add_executor_job(client.connect)
    except ConnectionError as err:
        _LOGGER.error("Initial SRCOOL login failed: %s", err)
        raise ConfigEntryNotReady from err

    async def _async_update():
        try:
            # synchronous get_status in executor
            return await hass.async_add_executor_job(client.get_status)
        except ConnectionError as err:
            _LOGGER.warning(
                "SRCOOL connection lost: %s – keeping old data", err)
            return coordinator.data or {}
        except Exception as err:
            _LOGGER.error("Unexpected error polling SRCOOL: %s", err)
            raise UpdateFailed(err)

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
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["climate", "sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
