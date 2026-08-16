"""Binary sensor platform for Tripp Lite SRCOOL."""
from homeassistant.components.binary_sensor import (BinarySensorDeviceClass,
                                                    BinarySensorEntity)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .device import build_device_info, entity_id_base


def _water_is_full(status: str | None) -> bool:
    """Return True when the condensate tank is full."""
    if not status:
        return False
    normalized = status.strip().lower()
    if normalized in ("not full", "not_full"):
        return False
    return "full" in normalized


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SRCOOL binary sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([SRCOOLWaterFullBinarySensor(coordinator)])


class SRCOOLWaterFullBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for condensate tank full condition."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:water-alert"
    _attr_name = "Water Tank Full"

    def __init__(self, coordinator):
        """Initialize the water-full binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{entity_id_base(coordinator)}_water_full"
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info shared with other platform entities."""
        return build_device_info(self.coordinator)

    @property
    def is_on(self) -> bool | None:
        """Return True when water status indicates tank is full."""
        if self.coordinator.data is None:
            return None
        return _water_is_full(self.coordinator.data.get("water_status"))
