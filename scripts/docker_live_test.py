#!/usr/bin/env python3
"""Live async stress test for SRCOOLClient (Docker / manual)."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "custom_components"))

from tripp_lite_srcool.srcool_telnet import SRCOOLClient  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description="SRCOOL live telnet stress test")
    parser.add_argument("--host", default="10.10.0.61")
    parser.add_argument("--port", type=int, default=23)
    parser.add_argument("--username", default="localadmin")
    parser.add_argument("--password", default="localadmin")
    parser.add_argument("--polls", type=int, default=5)
    args = parser.parse_args()

    client = SRCOOLClient(
        args.host, args.port, args.username, args.password
    )
    try:
        for i in range(args.polls):
            data = await client.get_status(include_diagnostics=(i == 0))
            print(
                f"poll {i + 1}/{args.polls}: "
                f"mode={data.get('mode')} "
                f"fan={data.get('fan')} "
                f"temp={data.get('current_temp')} "
                f"target={data.get('target_temp')}"
            )
            if i + 1 < args.polls:
                await asyncio.sleep(2)
    finally:
        await client.disconnect()
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
