DOMAIN = 'tripp_lite_srcool'
DEFAULT_PORT = 23
SCAN_INTERVAL = 60
DIAGNOSTICS_REFRESH_INTERVAL = 3600

# Fetched from telnet menu 5; preserved between hourly refreshes.
DIAGNOSTIC_KEYS = frozenset({
    'os',
    'agent_type',
    'mac_address',
    'card_serial_number',
    'driver_version',
    'engine_version',
    'driver_file_status',
})

# Redundant with the Dehumidify Mode switch; hidden unless diagnostics shown.
DIAGNOSTIC_ENTITY_KEYS = frozenset({
    'dehumidifying_status',
})
