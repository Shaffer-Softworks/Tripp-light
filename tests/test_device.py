"""Tests for stable device identifiers and entity unique_id base."""
from types import SimpleNamespace

from custom_components.tripp_lite_srcool.const import DOMAIN
from custom_components.tripp_lite_srcool.device import (build_device_info,
                                                        entity_id_base)


def _coordinator(data: dict | None, entry_id: str = "entry123"):
    entry = SimpleNamespace(entry_id=entry_id, data={"host": "10.10.0.61"})
    return SimpleNamespace(data=data, config_entry=entry)


def test_entity_id_base_prefers_port_name():
    coordinator = _coordinator({"port_name": "/com/1"})
    assert entity_id_base(coordinator) == "/com/1"


def test_entity_id_base_falls_back_to_entry_id():
    coordinator = _coordinator({})
    assert entity_id_base(coordinator) == "entry123"


def test_entity_id_base_never_unknown_port():
    coordinator = _coordinator(None)
    assert entity_id_base(coordinator) == "entry123"
    assert "unknown" not in entity_id_base(coordinator)


def test_device_info_identifier_stable_when_port_appears():
    empty = _coordinator({})
    filled = _coordinator(
        {
            "port_name": "/com/1",
            "product": "SR(X)COOL12K",
            "vendor": "TrippLite",
            "mac_address": "00:40:9d:43:35:97",
        }
    )
    assert build_device_info(empty)["identifiers"] == {(DOMAIN, "entry123")}
    assert build_device_info(filled)["identifiers"] == {(DOMAIN, "entry123")}


def test_device_info_adds_mac_connection():
    coordinator = _coordinator({"mac_address": "00:40:9d:43:35:97"})
    info = build_device_info(coordinator)
    assert ("mac", "00:40:9D:43:35:97") in info["connections"]


def test_entity_id_base_frozen_semantics():
    """Callers must freeze unique_ids at init; base may change later."""
    coordinator = _coordinator({})
    frozen = entity_id_base(coordinator)
    coordinator.data = {"port_name": "/com/1"}
    assert frozen == "entry123"
    assert entity_id_base(coordinator) == "/com/1"
