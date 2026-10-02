"""Tests for the HTTP client against the simulated FRITZ!Box."""

from __future__ import annotations

import aiohttp
import pytest

from custom_components.fritzbox_docsis.api import (
    FritzAuthError,
    FritzConnectionError,
    FritzDataError,
    FritzDocsisClient,
)

from .mock_fritzbox import PASSWORD, USERNAME


async def test_login_pbkdf2_and_docinfo(fritzbox) -> None:
    box, url = fritzbox
    async with aiohttp.ClientSession() as session:
        client = FritzDocsisClient(session, url, USERNAME, PASSWORD)
        info, raw = await client.get_docsis()
        assert len(info.downstream) == 26
        assert raw["pid"] == "docInfo"
        assert box.logins == 1
        # Second fetch reuses the existing session
        await client.get_docsis()
        assert box.logins == 1


async def test_login_md5(fritzbox) -> None:
    box, url = fritzbox
    box.md5 = True
    async with aiohttp.ClientSession() as session:
        client = FritzDocsisClient(session, url, USERNAME, PASSWORD)
        info, _ = await client.get_docsis()
        assert info.downstream


async def test_session_expiry_relogin(fritzbox) -> None:
    box, url = fritzbox
    async with aiohttp.ClientSession() as session:
        client = FritzDocsisClient(session, url, USERNAME, PASSWORD)
        await client.get_docsis()
        box.expire_sessions = True
        info, _ = await client.get_docsis()
        assert info.downstream
        assert box.logins == 2


async def test_wrong_password(fritzbox) -> None:
    _, url = fritzbox
    async with aiohttp.ClientSession() as session:
        client = FritzDocsisClient(session, url, USERNAME, "wrong")
        with pytest.raises(FritzAuthError):
            await client.get_docsis()


async def test_log(fritzbox) -> None:
    _, url = fritzbox
    async with aiohttp.ClientSession() as session:
        client = FritzDocsisClient(session, url, USERNAME, PASSWORD)
        entries = await client.get_log()
        assert len(entries) == 7


async def test_no_cable_data(fritzbox) -> None:
    box, url = fritzbox
    box.fail_docinfo = True
    async with aiohttp.ClientSession() as session:
        client = FritzDocsisClient(session, url, USERNAME, PASSWORD)
        with pytest.raises(FritzDataError):
            await client.get_docsis()


async def test_unreachable(socket_enabled) -> None:
    async with aiohttp.ClientSession() as session:
        client = FritzDocsisClient(session, "http://127.0.0.1:1", USERNAME, PASSWORD)
        with pytest.raises(FritzConnectionError):
            await client.get_docsis()
