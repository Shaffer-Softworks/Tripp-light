"""Switch platform for Tripp Lite SRCOOL."""
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .device import build_device_info, entity_id_base

_LOGGER = logging.getLogger(__name__)


def _dehumidifying_is_on(status: str | None) -> bool:
    """Return True when dehumidifying mode is active."""
    return (status or "").strip().lower() == "dehumidifying"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SRCOOL switches from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [SRCOOLDehumidifyingSwitch(data["client"], data["coordinator"])],
    )


class SRCOOLDehumidifyingSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to enable or disable dehumidify mode on the AC unit."""

    _attr_icon = "mdi:water-percent"
    _attr_name = "Dehumidify Mode"

    def __init__(self, client, coordinator):
        """Initialize the dehumidifying switch."""
        super().__init__(coordinator)
        self._client = client
        self._attr_unique_id = (
            f"{entity_id_base(coordinator)}_dehumidifying"
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info shared with other platform entities."""
        return build_device_info(self.coordinator)

    @property
    def is_on(self) -> bool | None:
        """Return True when dehumidifying mode is active."""
        if self.coordinator.data is None:
            return None
        return _dehumidifying_is_on(
            self.coordinator.data.get("dehumidifying_status"),
        )

    async def async_turn_on(self, **kwargs):
        """Enable dehumidifying mode."""
        _LOGGER.debug("UI enable dehumidifying")
        await self._client.set_dehumidifying(True)
        self._merge_coordinator_data(dehumidifying_status="dehumidifying")
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Disable dehumidifying mode."""
        _LOGGER.debug("UI disable dehumidifying")
        await self._client.set_dehumidifying(False)
        self._merge_coordinator_data(
            dehumidifying_status="not dehumidifying",
        )
        self.async_write_ha_state()

    def _merge_coordinator_data(self, **updates):
        """Apply optimistic updates without an immediate device poll."""
        if self.coordinator.data is None:
            return
        self.coordinator.async_set_updated_data(
            {**self.coordinator.data, **updates}
        )
