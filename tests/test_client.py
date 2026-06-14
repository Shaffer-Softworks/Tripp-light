"""Tests for async SRCOOLClient telnet I/O."""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.tripp_lite_srcool.srcool_telnet import (PROMPT_LOGIN,
                                                               PROMPT_PASSWORD,
                                                               PROMPT_READY,
                                                               SRCOOLClient)

OPEN_PATCH = (
    "custom_components.tripp_lite_srcool.srcool_telnet"
    ".telnetlib3.open_connection"
)

STATUS_BODY = """
Device Status Menu
Operating Mode: Cooling
Return Air Temperature: 72.0 F
Fan Speed: Low
Auto Fan Speed: Off
Water Status: OK
Quiet Mode: Off
"""

ID_BODY = """
Device Name: Rack AC
Port Name: SRCOOL1
Serial Number: SN12345
"""

PREFS_BODY = """
Set Point Temperature: 70 F
Dehumidifying Status: Not Dehumidifying
Units: Fahrenheit
"""


def _make_reader(chunks: list[bytes]) -> AsyncMock:
    reader = AsyncMock()
    read_queue = list(chunks)

    async def readuntil(sep: bytes) -> bytes:
        if not read_queue:
            raise AssertionError(f"Unexpected readuntil({sep!r})")
        chunk = read_queue.pop(0)
        return chunk + sep

    reader.readuntil = readuntil
    return reader


def _make_writer() -> AsyncMock:
    writer = AsyncMock()
    writer.write = Mock()
    writer.drain = AsyncMock()
    writer.close = Mock()
    writer.wait_closed = AsyncMock()
    return writer


def _login_chunks() -> list[bytes]:
    return [PROMPT_LOGIN, PROMPT_PASSWORD, PROMPT_READY]


def _screen_nav_chunks() -> list[bytes]:
    """Two menu navigations before the screen body on each devices submenu."""
    return [b"", b""]


def _status_poll_chunks(
    screens: list[str],
) -> list[bytes]:
    chunks: list[bytes] = []
    for screen in screens:
        chunks.extend(_screen_nav_chunks())
        chunks.append(screen.encode("ascii"))
    return chunks


def _disconnect_chunks() -> list[bytes]:
    return [b"", b""]


@pytest.mark.asyncio
async def test_verify_connection_login_and_disconnect():
    reader = _make_reader(_login_chunks() + _disconnect_chunks())
    writer = _make_writer()

    with patch(
        OPEN_PATCH,
        new=AsyncMock(return_value=(reader, writer)),
    ):
        client = SRCOOLClient("10.0.0.1", 23, "user", "pass")
        await client.verify_connection()

    assert writer.write.called
    writer.wait_closed.assert_awaited()


@pytest.mark.asyncio
async def test_get_status_parses_operating_mode():
    chunks = (
        _login_chunks()
        + _status_poll_chunks([STATUS_BODY, ID_BODY, PREFS_BODY])
        + _disconnect_chunks()
    )
    reader = _make_reader(chunks)
    writer = _make_writer()

    with patch(
        OPEN_PATCH,
        new=AsyncMock(return_value=(reader, writer)),
    ):
        client = SRCOOLClient("10.0.0.1", 23, "user", "pass")
        data = await client.get_status(include_diagnostics=False)
        await client.disconnect()

    assert data["mode"] == "cooling"
    assert data["port_name"] == "SRCOOL1"
    assert data["target_temp"] == 70.0
    assert data["fan"] == "low"


@pytest.mark.asyncio
async def test_get_status_retries_after_desync():
    bad_screen = "Controls Menu\nNo status here\n"
    first_attempt = _status_poll_chunks([bad_screen])
    reconnect = _login_chunks() + _status_poll_chunks(
        [STATUS_BODY, ID_BODY, PREFS_BODY]
    )
    chunks = (
        _login_chunks()
        + first_attempt
        + _disconnect_chunks()
        + reconnect
        + _disconnect_chunks()
    )
    reader = _make_reader(chunks)
    writer = _make_writer()

    with patch(
        OPEN_PATCH,
        new=AsyncMock(return_value=(reader, writer)),
    ):
        client = SRCOOLClient("10.0.0.1", 23, "user", "pass")
        data = await client.get_status(include_diagnostics=False)
        await client.disconnect()

    assert data["mode"] == "cooling"
