"""Tests for config-flow connection validation."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.tripp_lite_srcool.connection import \
    async_validate_connection
from custom_components.tripp_lite_srcool.const import DOMAIN


def _user_input(**overrides):
    data = {
        "host": "10.0.0.61",
        "port": 23,
        "username": "localadmin",
        "password": "secret",
    }
    data.update(overrides)
    return data


@pytest.mark.asyncio
async def test_validate_unchanged_creds_uses_check_connection():
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry1": {}}}
    client = AsyncMock()
    hass.data[DOMAIN]["entry1"]["client"] = client

    entry = MagicMock()
    entry.entry_id = "entry1"
    entry.data = _user_input()

    with patch(
        "custom_components.tripp_lite_srcool.connection.get_host_lock",
        return_value=AsyncMock(),
    ) as mock_lock:
        lock = mock_lock.return_value
        lock.__aenter__ = AsyncMock(return_value=None)
        lock.__aexit__ = AsyncMock(return_value=None)

        await async_validate_connection(
            hass, _user_input(), config_entry=entry
        )

    client.check_connection.assert_awaited_once_with(host_lock_held=True)
    client.disconnect.assert_not_called()


@pytest.mark.asyncio
async def test_validate_changed_creds_disconnects_and_verifies():
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry1": {}}}
    client = AsyncMock()
    hass.data[DOMAIN]["entry1"]["client"] = client

    entry = MagicMock()
    entry.entry_id = "entry1"
    entry.data = _user_input()

    temp_client = AsyncMock()
    temp_client.verify_connection = AsyncMock()

    with patch(
        "custom_components.tripp_lite_srcool.connection.get_host_lock",
        return_value=AsyncMock(),
    ) as mock_lock:
        lock = mock_lock.return_value
        lock.__aenter__ = AsyncMock(return_value=None)
        lock.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "custom_components.tripp_lite_srcool.connection.SRCOOLClient",
            return_value=temp_client,
        ):
            await async_validate_connection(
                hass,
                _user_input(password="newsecret"),
                config_entry=entry,
            )

    client.disconnect.assert_awaited_once_with(host_lock_held=True)
    temp_client.verify_connection.assert_awaited_once_with(
        host_lock_held=True
    )


@pytest.mark.asyncio
async def test_validate_failure_restores_loaded_client():
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry1": {}}}
    client = AsyncMock()
    hass.data[DOMAIN]["entry1"]["client"] = client

    entry = MagicMock()
    entry.entry_id = "entry1"
    entry.data = _user_input()

    temp_client = AsyncMock()
    temp_client.verify_connection = AsyncMock(
        side_effect=ConnectionError("bad password")
    )

    with patch(
        "custom_components.tripp_lite_srcool.connection.get_host_lock",
        return_value=AsyncMock(),
    ) as mock_lock:
        lock = mock_lock.return_value
        lock.__aenter__ = AsyncMock(return_value=None)
        lock.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "custom_components.tripp_lite_srcool.connection.SRCOOLClient",
            return_value=temp_client,
        ):
            with pytest.raises(ConnectionError):
                await async_validate_connection(
                    hass,
                    _user_input(password="wrong"),
                    config_entry=entry,
                )

    client.connect.assert_awaited_once_with(host_lock_held=True)
