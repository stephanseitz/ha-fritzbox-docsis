"""Gemeinsame Fixtures."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from aiohttp.test_utils import TestServer
import pytest

from .mock_fritzbox import MockFritzBox


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow custom integrations in all tests."""
    yield


@pytest.fixture
async def fritzbox(socket_enabled) -> AsyncGenerator[tuple[MockFritzBox, str]]:
    """Start a simulated FRITZ!Box on localhost."""
    box = MockFritzBox()
    server = TestServer(box.app())
    await server.start_server()
    try:
        yield box, str(server.make_url("")).rstrip("/")
    finally:
        await server.close()
