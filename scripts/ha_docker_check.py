#!/usr/bin/env python3
"""Read Tripp Lite SRCOOL entity states from Docker HA database."""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "docker" / "config"


def _entity_ids(config_dir: Path) -> list[str]:
    """Return tripp_lite_srcool entity ids from the dev HA database."""
    db_path = config_dir / "home-assistant_v2.db"
    if not db_path.is_file():
        return []
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT sm.entity_id FROM states_meta sm "
            "WHERE sm.entity_id LIKE '%tripp_lite_srcool%' "
            "ORDER BY sm.entity_id"
        ).fetchall()
    finally:
        conn.close()
    return [row[0] for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect Tripp Lite SRCOOL states in Docker dev HA"
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=DEFAULT_CONFIG,
        help="HA config directory (default: docker/config)",
    )
    args = parser.parse_args()
    config_dir = args.config_dir.resolve()
    db_path = config_dir / "home-assistant_v2.db"
    entries_path = config_dir / ".storage" / "core.config_entries"

    if not db_path.is_file():
        print(f"No database at {db_path}")
        print("Start dev HA: cd docker && docker compose up -d")
        raise SystemExit(1)

    entity_ids = _entity_ids(config_dir)
    if not entity_ids:
        print("No tripp_lite_srcool entities in DB yet.")
        print("Add the integration at http://localhost:8125")
        raise SystemExit(0)

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    print("=== Entity states (HA recorder DB) ===")
    for eid in entity_ids:
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
    db.close()

    print("\n=== Config entry ===")
    if not entries_path.is_file():
        print(f"No config entries file at {entries_path}")
        return
    entries = json.loads(entries_path.read_text())
    found = False
    for entry in entries["data"]["entries"]:
        if entry["domain"] == "tripp_lite_srcool":
            found = True
            print(f"title: {entry['title']}")
            print(f"entry_id: {entry['entry_id']}")
            print(f"state data: {entry['data']}")
    if not found:
        print("No tripp_lite_srcool config entry yet.")


if __name__ == "__main__":
    main()
