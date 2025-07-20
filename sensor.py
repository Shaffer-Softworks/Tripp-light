import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# key -> (Friendly Name, Unit)
SENSOR_TYPES: dict[str, tuple[str, str | None]] = {
    # Device info
    "device_name":    ("Device Name",          None),
    "vendor":         ("Vendor",               None),
    "product":        ("Product",              None),
    "protocol":       ("Protocol",             None),
    "date_installed": ("Date Installed",       None),
    "state":          ("Device State",         None),
    "type":           ("Device Type",          None),
    "port_mode":      ("Port Mode",            None),
    "port_name":      ("Port Name",            None),
    # Live status
    "water_status":   ("Water Status",         None),
    "quiet_mode":     ("Quiet Mode",           None),
    "auto_fan":       ("Auto Fan Speed",       None),
    "fan":            ("Fan Speed",            None),
    "mode":           ("Operating Mode",       None),
    "current_temp":   ("Return Air Temperature", UnitOfTemperature.FAHRENHEIT),
    "target_temp":    ("Target Temperature",   UnitOfTemperature.FAHRENHEIT),
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SRCOOL status sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    sensors = []
    for key, (label, unit) in SENSOR_TYPES.items():
        sensors.append(
            SRCoolStatusSensor(coordinator, key, label, unit)
        )

    async_add_entities(sensors, True)


class SRCoolStatusSensor(CoordinatorEntity, SensorEntity):
    """Sensor for a single SRCOOL status or device info field."""

    def __init__(self, coordinator, key: str, name: str, unit: str | None):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"SRCOOL {name}"
        self._attr_native_unit_of_measurement = unit
        # Will be auto‑linked to the same device as other platform entities

    @property
    def unique_id(self) -> str:
        """Return a unique ID combining the port and the key."""
        port = self.coordinator.data.get("port_name") or "unknown_port"
        return f"{port}_{self._key}"

    @property
    def native_value(self):
        """Return the latest value from the coordinator."""
        return self.coordinator.data.get(self._key)

