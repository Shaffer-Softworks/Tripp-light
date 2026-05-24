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


def build_device_info(coordinator) -> DeviceInfo:
    """Build DeviceInfo from coordinator data and config entry."""
    data = coordinator.data or {}
    entry = coordinator.config_entry
    port = data.get("port_name") or entry.entry_id

    connections: set[tuple[str, str]] = set()
    mac = data.get("mac_address")
    if mac:
        connections.add((CONNECTION_NETWORK_MAC, mac.upper()))

    host = entry.data.get("host")
    config_url = f"http://{host}" if host else None

    return DeviceInfo(
        identifiers={(DOMAIN, port)},
        name=_device_name(data),
        manufacturer=_manufacturer(data.get("vendor")),
        model=data.get("product"),
        sw_version=_sw_version(data),
        serial_number=_serial_number(data),
        configuration_url=config_url,
        connections=connections or None,
    )
