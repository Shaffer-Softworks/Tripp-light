"""Tests for SRCOOL telnet screen parsers."""
from custom_components.tripp_lite_srcool.srcool_telnet import SRCOOLClient

STATUS_SCREEN = """
Device Status Menu
Operating Mode: Cooling
Return Air Temperature: 72.5 F
Fan Speed: Med
Auto Fan Speed: Off
Water Status: OK
Quiet Mode: Off
>>

"""

PREFS_SCREEN = """
Set Point Temperature: 68 F
Dehumidifying Status: Not Dehumidifying
Units: Fahrenheit
>>

"""

AUTO_FAN_STATUS = """
Device Status Menu
Operating Mode: Cooling
Return Air Temperature: 70.0 F
Auto Fan Speed: On
Fan Speed: Low
Water Status: OK
>>


"""


def test_extract_field_operating_mode():
    assert SRCOOLClient._extract_field(
        "Operating Mode", STATUS_SCREEN
    ) == "Cooling"


def test_extract_field_return_air_temperature():
    assert SRCOOLClient._extract_field(
        "Return Air Temperature",
        STATUS_SCREEN,
        lambda v: float(v.split()[0]),
        0.0,
    ) == 72.5


def test_parse_fan_speed_normalizes_med():
    assert SRCOOLClient._parse_fan_speed(STATUS_SCREEN) == "medium"


def test_parse_fan_speed_skips_auto_fan_line():
    assert SRCOOLClient._parse_fan_speed(AUTO_FAN_STATUS) == "low"


def test_parse_target_temp_from_preferences():
    assert SRCOOLClient._parse_target_temp(PREFS_SCREEN) == 68.0


def test_auto_fan_forces_auto_mode():
    extract = SRCOOLClient._extract_field
    auto_fan = (
        extract("Auto Fan Speed", AUTO_FAN_STATUS) or "off"
    ).lower()
    assert auto_fan == "on"
    if auto_fan == "on":
        fan = "auto"
    else:
        fan = SRCOOLClient._parse_fan_speed(AUTO_FAN_STATUS)
    assert fan == "auto"
