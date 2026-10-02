"""Async client for the FRITZ!Box web interface (login_sid.lua / data.lua)."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
from typing import Any
import xml.etree.ElementTree as ET

import aiohttp

from .const import INVALID_SID
from .parser import DocsisInfo, LogEntry, parse_docinfo, parse_log

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class FritzError(Exception):
    """Base class for errors."""


class FritzConnectionError(FritzError):
    """FRITZ!Box not reachable."""


class FritzAuthError(FritzError):
    """Login rejected."""

    def __init__(self, message: str, block_time: int = 0) -> None:
        super().__init__(message)
        self.block_time = block_time


class FritzDataError(FritzError):
    """Unexpected response or no cable data."""


def _pbkdf2_response(challenge: str, password: str) -> str:
    """Response for the PBKDF2 method (login_sid.lua?version=2, FRITZ!OS >= 7.24)."""
    _, iter1, salt1, iter2, salt2 = challenge.split("$")
    hash1 = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt1), int(iter1)
    )
    hash2 = hashlib.pbkdf2_hmac("sha256", hash1, bytes.fromhex(salt2), int(iter2))
    return f"{salt2}${hash2.hex()}"


def _md5_response(challenge: str, password: str) -> str:
    """Response for the legacy MD5 method."""
    # AVM replaces characters outside Latin-1 with a dot
    safe = "".join(c if ord(c) < 256 else "." for c in password)
    digest = hashlib.md5(f"{challenge}-{safe}".encode("utf-16le")).hexdigest()
    return f"{challenge}-{digest}"


def compute_response(challenge: str, password: str) -> str:
    if challenge.startswith("2$"):
        return _pbkdf2_response(challenge, password)
    return _md5_response(challenge, password)


class FritzDocsisClient:
    """Reads cable information and the event log of a FRITZ!Box Cable."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._username = username
        self._password = password
        self._sid: str | None = None
        self._lock = asyncio.Lock()

    @property
    def url(self) -> str:
        return self._url

    # ------------------------------------------------------------------ #
    # Login
    # ------------------------------------------------------------------ #

    async def _get_xml(self, method: str, **kwargs: Any) -> ET.Element:
        try:
            async with self._session.request(
                method,
                f"{self._url}/login_sid.lua",
                timeout=REQUEST_TIMEOUT,
                **kwargs,
            ) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise FritzConnectionError(f"HTTP {resp.status} from login_sid.lua")
        except (TimeoutError, aiohttp.ClientError) as err:
            raise FritzConnectionError(f"FRITZ!Box not reachable: {err}") from err
        try:
            return ET.fromstring(text)
        except ET.ParseError as err:
            raise FritzConnectionError(
                "Unexpected response from login_sid.lua (is the URL correct?)"
            ) from err

    async def login(self) -> str:
        """Log in and return the SID."""
        root = await self._get_xml("GET", params={"version": "2"})
        challenge = root.findtext("Challenge") or ""
        block_time = int(root.findtext("BlockTime") or 0)
        if block_time > 0:
            raise FritzAuthError(
                f"Login blocked for {block_time} s (too many failed attempts)",
                block_time,
            )
        if not challenge:
            raise FritzConnectionError("No challenge received from the FRITZ!Box")

        loop = asyncio.get_running_loop()
        # PBKDF2 with many iterations is CPU-heavy -> keep it off the event loop
        response = await loop.run_in_executor(
            None, compute_response, challenge, self._password
        )

        root = await self._get_xml(
            "POST",
            params={"version": "2"},
            data={"username": self._username, "response": response},
        )
        sid = root.findtext("SID") or INVALID_SID
        if sid == INVALID_SID:
            block_time = int(root.findtext("BlockTime") or 0)
            raise FritzAuthError("Invalid username or password", block_time)
        self._sid = sid
        _LOGGER.debug("Logged in to %s", self._url)
        return sid

    async def logout(self) -> None:
        if not self._sid:
            return
        with contextlib.suppress(FritzError):
            await self._get_xml("GET", params={"logout": "1", "sid": self._sid})
        self._sid = None

    # ------------------------------------------------------------------ #
    # data.lua
    # ------------------------------------------------------------------ #

    async def _post_data(
        self, page: str, extra: dict[str, str] | None
    ) -> dict[str, Any] | None:
        """Make one data.lua request. Returns None if the session is invalid."""
        form = {
            "xhr": "1",
            "sid": self._sid or "",
            "lang": "de",
            "page": page,
            "xhrId": "all",
            "no_sidrenew": "",
        }
        if extra:
            form.update(extra)
        try:
            async with self._session.post(
                f"{self._url}/data.lua", data=form, timeout=REQUEST_TIMEOUT
            ) as resp:
                if resp.status in (401, 403):
                    return None
                if resp.status >= 400:
                    raise FritzConnectionError(f"HTTP {resp.status} from data.lua")
                text = await resp.text()
        except (TimeoutError, aiohttp.ClientError) as err:
            raise FritzConnectionError(f"FRITZ!Box not reachable: {err}") from err

        try:
            payload = await asyncio.get_running_loop().run_in_executor(
                None, _json_loads, text
            )
        except ValueError:
            # When the session has expired, the box returns the login page (HTML)
            return None
        if not isinstance(payload, dict) or "data" not in payload:
            return None
        sid = payload.get("sid")
        if isinstance(sid, str) and sid == INVALID_SID:
            return None
        return payload

    async def fetch_page(
        self, page: str, extra: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Fetch a data.lua page, logging in (again) if necessary."""
        async with self._lock:
            if not self._sid:
                await self.login()
            payload = await self._post_data(page, extra)
            if payload is None:
                _LOGGER.debug("Session invalid, logging in again")
                await self.login()
                payload = await self._post_data(page, extra)
            if payload is None:
                raise FritzAuthError(
                    "Access denied – does the user have the "
                    '"FRITZ!Box Settings" permission (and, if needed, internet access)?'
                )
            return payload

    async def get_docsis(self) -> tuple[DocsisInfo, dict[str, Any]]:
        payload = await self.fetch_page("docInfo")
        try:
            return parse_docinfo(payload), payload
        except ValueError as err:
            raise FritzDataError(str(err)) from err

    async def get_log(self) -> list[LogEntry]:
        payload = await self.fetch_page("log")
        try:
            return parse_log(payload)
        except ValueError as err:
            raise FritzDataError(str(err)) from err


def _json_loads(text: str) -> Any:
    return json.loads(text)
