import logging
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# key -> (Friendly Name, Unit)
SENSOR_TYPES: dict[str, tuple[str, str, str | None]] = {
    # Device info
    "device_name":    ("Device Name",          "mdi:information-variant", None),
    "vendor":         ("Vendor",               "mdi:label", None),
    "product":        ("Product",              "mdi:label", None),
    "protocol":       ("Protocol",             "mdi:protocol", None),
    "date_installed": ("Date Installed",       "mdi:calendar", None),
    "state":          ("Device State",         "mdi:state-machine", None),
    "type":           ("Device Type",          "mdi:power-socket-us", None),
    "port_mode":      ("Port Mode",            "mdi:serial-port", None),
    "port_name":      ("Port Name",            "mdi:label", None),
    # Live status
    "water_status":   ("Water Status",         "mdi:water-circle", None),
    "quiet_mode":     ("Quiet Mode",           "mdi:information-variant", None),
    "auto_fan":       ("Auto Fan Speed",       "mdi:fan-auto", None),
    "fan":            ("Fan Speed",            "mdi:fan", None),
    "mode":           ("Operating Mode",       "mdi:thermostat", None),
    "current_temp":   ("Return Air Temperature", "mdi:thermometer", UnitOfTemperature.FAHRENHEIT),
    "target_temp":    ("Target Temperature",   "mdi:thermometer", UnitOfTemperature.FAHRENHEIT),
    # Diagnostics keys:
    "os":                 ("OS",                   "mdi:information-variant", None),
    "agent_type":         ("Agent Type",           "mdi:information-variant", None),
    "mac_address":        ("MAC Address",          "mdi:information-variant", None),
    "card_serial_number": ("Card Serial Number",   "mdi:numeric", None),
    "driver_version":     ("Driver Version",       "mdi:numeric", None),
    "engine_version":     ("Engine Version",       "mdi:numeric", None),
    "driver_file_status": ("Driver File Status",   "mdi:information-variant", None),
}

DIAGNOSTIC_KEYS = {
    "os",
    "agent_type",
    "mac_address",
    "card_serial_number",
    "driver_version",
    "engine_version",
    "driver_file_status",
}

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SRCOOL status sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    sensors = []
    for key, (label, icon, unit) in SENSOR_TYPES.items():
        sensors.append(
            SRCoolStatusSensor(coordinator, key, label, icon, unit)
        )

    async_add_entities(sensors, True)


class SRCoolStatusSensor(CoordinatorEntity, SensorEntity):
    """Sensor for a single SRCOOL status or device info field."""

    def __init__(self, coordinator, key: str, name: str, icon: str, unit: str | None):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        if self._key in DIAGNOSTIC_KEYS:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        # Will be auto‑linked to the same device as other platform entities

    @property
    def device_info(self) -> DeviceInfo:
        """Tie this sensor into the same SRCOOL device as the climate entity."""
        data = self.coordinator.data
        # must match the climate entity identifiers exactly
        return {
            "identifiers": {(DOMAIN, f"tripp_lite_srcool_{data.get('port_name')}")},
            "name": data.get("device_name") or "Tripp Lite SRCOOL",
            "manufacturer": data.get("vendor"),
            "model": data.get("product"),
            "sw_version": data.get("date_installed"),
        }

    @property
    def unique_id(self) -> str:
        """Return a unique ID combining the port and the key."""
        port = self.coordinator.data.get("port_name") or "unknown_port"
        return f"{port}_{self._key}"

    @property
    def native_value(self):
        """Return the latest value from the coordinator."""
        return self.coordinator.data.get(self._key)
