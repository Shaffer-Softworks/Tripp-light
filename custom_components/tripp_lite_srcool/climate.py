"""Climate platform for Tripp Lite SRCOOL."""
import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode, ClimateEntityFeature, HVACAction
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

FAN_MODES = ["low", "medium", "high", "auto"]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the SRCOOL climate entity from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    client = data["client"]
    coordinator = data["coordinator"]

    _LOGGER.debug("Setting up SRCOOL climate for entry %s", entry.entry_id)

    async_add_entities(
        [SRCOOLClimate(entry.entry_id, client, coordinator)], update_before_add=True
    )


class SRCOOLClimate(CoordinatorEntity, ClimateEntity):
    """SRCOOL climate (temperature + fan + mode)."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
    )
    _attr_hvac_modes = [HVACMode.COOL, HVACMode.OFF]
    _attr_fan_modes = FAN_MODES
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT

    def __init__(self, entry_id: str, client, coordinator):
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._client = client
        self._attr_name = "Tripp Lite SRCOOL"

        # This unique_id never changes (tied to config entry)
        self._attr_unique_id = f"tripp_lite_srcool_{entry_id}"

        # Hold the last set‐point so the UI slider appears immediately
        self._target_temperature = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry info so all entities collapse under one device."""
        data = self.coordinator.data or {}
        port = data.get("port_name") or self._entry_id
        return DeviceInfo(
            identifiers={(DOMAIN, port)},
            name=data.get("device_name") or f"Device {port}",
            manufacturer=data.get("vendor"),
            model=data.get("product"),
            sw_version=data.get("date_installed"),
        )

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current HVAC mode (“cooling” or “off”)."""
        mode = self.coordinator.data.get("mode")
        state = None
        match mode:
            case "idle":
                action = HVACMode.COOL
            case "cooling":
                action = HVACMode.COOL
            case "defrosting":
                action = HVACMode.COOL
            case "off":
                action = HVACMode.OFF
            case _:
                action = None
        return action

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running HVAC action"""
        mode = self.coordinator.data.get("mode")
        action = None
        match mode:
            case "idle":
                action = HVACAction.IDLE
            case "cooling":
                action = HVACAction.COOLING
            case "defrosting":
                action = HVACAction.DEFROSTING
            case "off":
                action = HVACAction.OFF
            case _:
                action = None
        return action

    @property
    def current_temperature(self) -> float | None:
        """Return current measured temperature."""
        return self.coordinator.data.get("current_temp")

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
        """Device’s minimum settable temperature."""
        return 63.0

    @property
    def max_temp(self) -> float:
        """Device’s maximum settable temperature."""
        return 86.0

    @property
    def fan_mode(self) -> str | None:
        """Return current fan speed (“low”, “medium”, etc.)."""
        fan = self.coordinator.data.get("fan")
        return fan if fan in self._attr_fan_modes else None

    async def async_set_temperature(self, **kwargs):
        """Handle UI temperature changes."""
        temp = float(kwargs.get("temperature"))
        _LOGGER.debug("UI set temperature → %s°F", temp)
        await self.hass.async_add_executor_job(self._client.set_target_temp, temp)
        self._target_temperature = temp
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str):
        """Handle UI fan mode changes."""
        _LOGGER.debug("UI set fan mode → %s", fan_mode)
        await self.hass.async_add_executor_job(self._client.set_fan, fan_mode)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        """Handle UI HVAC mode changes."""
        on = hvac_mode == HVACMode.COOL
        _LOGGER.debug("UI set HVAC mode → %s", hvac_mode)
        await self.hass.async_add_executor_job(self._client.set_mode, on)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()
