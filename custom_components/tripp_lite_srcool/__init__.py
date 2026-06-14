"""Climate platform for Tripp Lite SRCOOL."""
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (DataUpdateCoordinator,
                                                      UpdateFailed)

from .connection import get_host_lock
from .const import (DIAGNOSTIC_KEYS, DIAGNOSTICS_REFRESH_INTERVAL, DOMAIN,
                    SCAN_INTERVAL)
from .srcool_telnet import SRCOOLClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tripp Lite SRCOOL from a config entry."""
    data = entry.data
    client = SRCOOLClient(
        data["host"],
        data.get("port", 23),
        data["username"],
        data["password"],
        host_lock=get_host_lock(hass, data["host"]),
    )

    poll_count = 0
    diag_every = max(1, DIAGNOSTICS_REFRESH_INTERVAL // SCAN_INTERVAL)

    async def _async_update():
        nonlocal poll_count
        poll_count += 1
        include_diagnostics = poll_count == 1 or poll_count % diag_every == 0
        try:
            result = await client.get_status(
                include_diagnostics=include_diagnostics,
            )
            if not include_diagnostics and coordinator.data:
                for key in DIAGNOSTIC_KEYS:
                    if key in coordinator.data:
                        result[key] = coordinator.data[key]
            return result
        except ConnectionError as err:
            _LOGGER.warning(
                "SRCOOL connection lost: %s – keeping old data", err)
            return coordinator.data or {}
        except Exception as err:
            _LOGGER.error("Unexpected error polling SRCOOL: %s", err)
            raise UpdateFailed(err) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Tripp Lite SRCOOL",
        config_entry=entry,
        update_method=_async_update,
        update_interval=timedelta(seconds=SCAN_INTERVAL),
        always_update=False,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(
        entry, ["binary_sensor", "climate", "sensor", "switch"]
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, ["binary_sensor", "climate", "sensor", "switch"]
    )
    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if entry_data is not None:
            await entry_data["client"].disconnect()
    return unload_ok
