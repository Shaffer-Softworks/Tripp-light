import logging
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

FAN_MODES = ["low", "medium", "high", "auto"]

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    client = data["client"]
    coordinator = data["coordinator"]
    async_add_entities([SRCOOLClimate(hass, client, coordinator)], True)

class SRCOOLClimate(CoordinatorEntity, ClimateEntity):
    def __init__(self, hass, client, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"tripp_lite_srcool_{client._host}_{client._port}"
        self.hass = hass
        self._client = client
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        )
        self._attr_hvac_modes = [HVACMode.COOL, HVACMode.OFF]
        self._attr_fan_modes = FAN_MODES
        self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
        self._attr_name = "Tripp Lite SRCOOL"

        # initialize target temperature holder
        self._target_temperature: float | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        data = self.coordinator.data
        return {
            # this tuple must be unique per physical device
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": data.get("device_name") or self.name,
            "manufacturer": data.get("vendor"),
            "model": data.get("product"),
            "sw_version": data.get("date_installed"),
        }

    @property
    def extra_state_attributes(self):
        return {
            "water_status": self.coordinator.data.get("water_status"),
            "quiet_mode": self.coordinator.data.get("quiet_mode"),
            "auto_fan": self.coordinator.data.get("auto_fan"),
            "device_name": self.coordinator.data.get("device_name"),
            "vendor": self.coordinator.data.get("vendor"),
            "product": self.coordinator.data.get("product"),
            "protocol": self.coordinator.data.get("protocol"),
            "date_installed": self.coordinator.data.get("date_installed"),
            "state": self.coordinator.data.get("state"),
            "type": self.coordinator.data.get("type"),
            "port_mode": self.coordinator.data.get("port_mode"),
            "port_name": self.coordinator.data.get("port_name"),
        }

    @property
    def device_info(self):
        """Return device registry information for this device."""
        data = self.coordinator.data
        return {
            "identifiers": {(DOMAIN, data.get("port_name") or self.unique_id)},
            "manufacturer": data.get("vendor"),
            "model":        data.get("product"),
            "name":         self.name,
            "sw_version":   data.get("date_installed"),
        }

    @property
    def hvac_mode(self):
        mode = self.coordinator.data.get("mode")
        return HVACMode.COOL if mode == "cooling" else HVACMode.OFF

    @property
    def current_temperature(self):
        return self.coordinator.data.get("current_temp")

    @property
    def fan_mode(self):
        fan = self.coordinator.data.get("fan")
        _LOGGER.debug("Reporting fan_mode: %s", fan)
        if fan in self._attr_fan_modes:
            return fan
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the last user‐set target, or current temperature if unset."""
        self._target_temperature = self.coordinator.data.get("target_temp")

        if self._target_temperature is not None:
            return self._target_temperature
        # seed the slider with the current temperature
        return self.current_temperature

    @property
    def min_temp(self) -> float:
        """Return the minimum settable temperature."""
        return 63.0

    @property
    def max_temp(self) -> float:
        """Return the maximum settable temperature."""
        return 86.0

    async def async_set_temperature(self, **kwargs):
        """Handle temperature change requests from the UI."""
        temp = float(kwargs.get("temperature"))
        _LOGGER.debug("UI requested set temperature to %s°F", temp)

        # 1) perform the blocking telnet call
        await self.hass.async_add_executor_job(self._client.set_target_temp, temp)

        # 2) store the new setpoint so the slider reflects it
        self._target_temperature = temp

        # 3) refresh status if you want to update other attributes
        await self.coordinator.async_request_refresh()

        # 4) write state immediately so slider moves
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str):
        _LOGGER.debug("UI requested set fan mode to %s", fan_mode)
        await self.hass.async_add_executor_job(self._client.set_fan, fan_mode)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        _LOGGER.debug("UI requested HVAC mode %s", hvac_mode)
        on = hvac_mode == HVACMode.COOL
        await self.hass.async_add_executor_job(self._client.set_mode, on)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

