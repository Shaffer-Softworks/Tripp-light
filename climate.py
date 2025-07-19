import logging
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

FAN_MODES = ["low", "medium", "high", "auto"]

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    client = data["client"]
    coordinator = data["coordinator"]

    async_add_entities([SRCOOLClimate(hass, client, coordinator)], True)

class SRCOOLClimate(ClimateEntity):
    def __init__(self, hass, client, coordinator):
        self.hass = hass
        self._client = client
        self.coordinator = coordinator
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        )
        self._attr_hvac_modes = [HVACMode.COOL, HVACMode.OFF]
        self._attr_fan_modes = FAN_MODES
        self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
        self._attr_name = "Tripp Lite SRCOOL"

    @property
    def extra_state_attributes(self):
        return {
            "water_status": self.coordinator.data.get("water_status"),
            "quiet_mode": self.coordinator.data.get("quiet_mode"),
        }

    @property
    def hvac_mode(self) -> HVACMode:
        mode = self.coordinator.data.get("mode")
        return HVACMode.COOL if mode == "cooling" else HVACMode.OFF

    @property
    def current_temperature(self):
        return self.coordinator.data.get("current_temp")

    @property
    def fan_mode(self):
        return self.coordinator.data.get("fan")

    async def async_set_temperature(self, **kwargs):
        temp = int(kwargs.get("temperature"))
        _LOGGER.debug("Setting temperature to %s", temp)
        await self.hass.async_add_executor_job(self._client.set_target_temp, temp)