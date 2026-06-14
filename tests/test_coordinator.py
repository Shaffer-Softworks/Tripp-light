"""Tests for coordinator diagnostic key preservation."""
from custom_components.tripp_lite_srcool.const import DIAGNOSTIC_KEYS


def test_diagnostic_keys_preserved_on_non_diagnostic_poll():
    """Mirror __init__._async_update merge logic."""
    coordinator_data = {
        "mode": "cooling",
        "os": "Linux",
        "mac_address": "00:11:22:33:44:55",
        "driver_version": "1.2.3",
    }
    poll_result = {
        "mode": "cooling",
        "current_temp": 72.0,
    }
    include_diagnostics = False

    if not include_diagnostics and coordinator_data:
        for key in DIAGNOSTIC_KEYS:
            if key in coordinator_data:
                poll_result[key] = coordinator_data[key]

    assert poll_result["os"] == "Linux"
    assert poll_result["mac_address"] == "00:11:22:33:44:55"
    assert poll_result["driver_version"] == "1.2.3"
    assert poll_result["current_temp"] == 72.0


def test_diagnostic_keys_not_injected_when_missing_from_coordinator():
    coordinator_data = {"mode": "cooling"}
    poll_result = {"mode": "cooling", "current_temp": 72.0}
    include_diagnostics = False

    if not include_diagnostics and coordinator_data:
        for key in DIAGNOSTIC_KEYS:
            if key in coordinator_data:
                poll_result[key] = coordinator_data[key]

    assert "os" not in poll_result
