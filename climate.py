from __future__ import annotations
import asyncio
from typing import Optional

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
)
from homeassistant.components.climate.const import (
    HVACMode, FAN_LOW, FAN_MEDIUM, FAN_HIGH, FAN_AUTO,
)
from homeassistant.const import TEMP_FAHRENHEIT
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL
from .srcool_telnet import SRCOOLClient

SUPPORTED_FAN = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
SUPPORTED_HVAC = [HVACMode.COOL, HVACMode.OFF]

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    info = discovery_info or config
    client = SRCOOLClient(
        info["host"], info["port"], info["username"], info["password"]
    )

    async def _async_update():
        try:
            return await client.get_status()
        except Exception as exc:
            raise UpdateFailed(exc) from exc

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER := __import__("logging").getLogger(__name__),
        name="SRCOOL",
        update_method=_async_update,
        update_interval=asyncio.timedelta(seconds=SCAN_INTERVAL),
    )
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([SRCOOLClimate(info.get("name"), client, coordinator)])

class SRCOOLClimate(ClimateEntity):
    _attr_hvac_modes = SUPPORTED_HVAC
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    _attr_fan_modes = SUPPORTED_FAN
    _attr_temperature_unit = TEMP_FAHRENHEIT
    _attr_min_temp, _attr_max_temp = 60, 95

    def __init__(self, name, client: SRCOOLClient, coordinator):
        self._client, self.coordinator = client, coordinator
        self._attr_name = name

    # -------------- Coordinator plumbing -----------------
    @property
    def available(self) -> bool: return not self.coordinator.last_update_success
    
    @property
    def extra_state_attributes(self): return {}

    async def async_update(self): await self.coordinator.async_request_refresh()
    @property
    def current_temperature(self): return self.coordinator.data["current_temp"]
    
    @property
    def fan_mode(self):
        fan = self.coordinator.data["fan"]
        return "auto" if self.coordinator.data.get("auto_fan") == "on" else fan
    
    @property
    def hvac_mode(self):
        return HVACMode.COOL if self.coordinator.data["mode"] == "cool" else HVACMode.OFF
    
    @property
    def extra_state_attributes(self):
        return {
            "water_status": self.coordinator.data.get("water_status"),
            "quiet_mode":   self.coordinator.data.get("quiet_mode"),
            "auto_fan":     self.coordinator.data.get("auto_fan"),
        }


    # -------------- Setters -----------------
    async def async_set_temperature(self, **kwargs):
        temp = int(kwargs["temperature"])
        await self._client.set_target_temp(temp)
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode):
        await self._client.set_mode(hvac_mode == HVACMode.COOL)
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode):
        await self._client.set_fan(fan_mode)
        await self.coordinator.async_request_refresh()
