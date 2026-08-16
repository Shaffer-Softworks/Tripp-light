"""Shared device registry info for SRCOOL entities."""
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


def _manufacturer(vendor: str | None) -> str | None:
    if not vendor:
        return None
    if vendor.lower().replace(" ", "") == "tripplite":
        return "Tripp Lite"
    return vendor


def _sw_version(data: dict) -> str | None:
    for key in ("driver_version", "engine_version"):
        version = data.get(key)
        if version:
            return version
    return None


def _serial_number(data: dict) -> str | None:
    serial = data.get("serial_number")
    if not serial or not serial.strip("0"):
        return None
    return serial


def _device_name(data: dict) -> str:
    name = data.get("device_name")
    product = data.get("product")
    if name and not name.startswith("Device "):
        return name
    if product:
        return product
    return "Tripp Lite SRCOOL"


def entity_id_base(coordinator) -> str:
    """Stable unique_id prefix — freeze at entity init, never recompute.

    Prefer port_name when already known so existing installs keep registry
    IDs. Fall back to config entry id — never a sentinel like
    ``unknown_port`` (that created duplicate entities on later polls).
    """
    data = coordinator.data or {}
    return data.get("port_name") or coordinator.config_entry.entry_id


def build_device_info(coordinator) -> DeviceInfo:
    """Build DeviceInfo from coordinator data and config entry.

    Device identifiers always use the config entry id so the registry
    identity does not change when telnet fields (e.g. port_name) appear
    after the first poll. MAC is attached as a connection so HA can merge
    older devices that used port-based identifiers.
    """
    data = coordinator.data or {}
    entry = coordinator.config_entry

    connections: set[tuple[str, str]] = set()
    mac = data.get("mac_address")
    if mac:
        connections.add((CONNECTION_NETWORK_MAC, mac.upper()))

    host = entry.data.get("host")
    config_url = f"http://{host}" if host else None

    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=_device_name(data),
        manufacturer=_manufacturer(data.get("vendor")),
        model=data.get("product"),
        sw_version=_sw_version(data),
        serial_number=_serial_number(data),
        configuration_url=config_url,
        connections=connections or None,
    )
