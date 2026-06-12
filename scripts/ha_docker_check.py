#!/usr/bin/env python3
"""Read Tripp Lite SRCOOL entity states from Docker HA database."""
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

DB = Path("/config/home-assistant_v2.db")
ENTITIES = [
    "climate.sr_x_cool12k_tripp_lite_srcool",
    "sensor.sr_x_cool12k_return_air_temperature",
    "sensor.sr_x_cool12k_target_temperature",
    "sensor.sr_x_cool12k_fan_speed",
    "sensor.sr_x_cool12k_operating_mode",
    "binary_sensor.sr_x_cool12k_water_tank_full",
    "switch.sr_x_cool12k_dehumidify_mode",
]


def main() -> None:
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    print("=== Entity states (HA recorder DB) ===")
    for eid in ENTITIES:
        row = db.execute(
            "SELECT s.state, s.last_updated_ts FROM states s "
            "JOIN states_meta sm ON s.metadata_id = sm.metadata_id "
            "WHERE sm.entity_id = ? "
            "ORDER BY s.last_updated_ts DESC LIMIT 1",
            (eid,),
        ).fetchone()
        if row:
            ts = datetime.fromtimestamp(row["last_updated_ts"], tz=UTC)
            print(f"{eid}: {row['state']} ({ts.isoformat()})")
        else:
            print(f"{eid}: NOT FOUND")

    print("\n=== Config entry ===")
    entries = json.loads(
        Path("/config/.storage/core.config_entries").read_text()
    )
    for entry in entries["data"]["entries"]:
        if entry["domain"] == "tripp_lite_srcool":
            print(f"title: {entry['title']}")
            print(f"entry_id: {entry['entry_id']}")
            print(f"state data: {entry['data']}")


if __name__ == "__main__":
    main()
