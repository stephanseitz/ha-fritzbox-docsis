"""Simulation of the relevant FRITZ!Box endpoints for tests.

The channel values are realistic sample values from a FRITZ!Box 6591 Cable on a
German Vodafone network.
"""

from __future__ import annotations

import copy
import hashlib
import secrets
from typing import Any

from aiohttp import web

PASSWORD = "secret-123"
USERNAME = "homeassistant"

DS30 = [
    # channelID, freq, power, mse, corr, noncorr
    (3, "570.000", 6.5, -37.6, 16, 0),
    (1, "114.000", -1.2, -35.8, 85844, 0),
    (2, "130.000", 0.1, -36.6, 16, 0),
    (4, "578.000", 6.5, -37.4, 1063112, 0),
    (5, "586.000", 6.0, -37.4, 37, 0),
    (6, "594.000", 5.6, -37.6, 33, 0),
    (7, "602.000", 5.9, -37.6, 26, 0),
    (8, "618.000", 6.6, -37.4, 11, 0),
    (9, "626.000", 6.8, -37.4, 31, 0),
    (10, "634.000", 7.1, -37.6, 39, 0),
    (11, "642.000", 7.4, -37.6, 31, 0),
    (12, "650.000", 7.0, -37.4, 25, 0),
    (13, "658.000", 6.7, -37.4, 55, 0),
    (14, "666.000", 6.5, -37.4, 28, 0),
    (15, "674.000", 7.0, -37.4, 26, 0),
    (16, "682.000", 7.1, -37.1, 26, 0),
    (17, "690.000", 7.1, -37.6, 12, 0),
    (18, "698.000", 7.4, -37.4, 28, 0),
    (19, "706.000", 7.6, -37.6, 22, 0),
    (20, "714.000", 7.6, -37.4, 24, 0),
    (21, "722.000", 8.0, -37.4, 15, 0),
    (22, "730.000", 8.3, -37.4, 17, 0),
    (23, "738.000", 8.3, -37.6, 18, 0),
    (24, "746.000", 8.1, -37.4, 34, 0),
]


def docinfo_payload(
    sid: str, corr_offset: int = 0, field_style: str = "new"
) -> dict[str, Any]:
    """Build a docInfo response. ``corr_offset`` is added to the 578 MHz channel."""
    mod_key = "modulation" if field_style == "new" else "type"
    ds30 = []
    for cid, freq, power, mse, corr, noncorr in DS30:
        if freq == "578.000":
            corr += corr_offset
        ds30.append(
            {
                "channelID": cid,
                "frequency": freq,
                "powerLevel": str(power),
                mod_key: "256QAM",
                "mse": str(mse),
                "latency": 0.32,
                "corrErrors": corr,
                "nonCorrErrors": noncorr,
            }
        )
    return {
        "pid": "docInfo",
        "sid": sid,
        "data": {
            "channelDs": {
                "docsis30": ds30,
                "docsis31": [
                    {
                        "channelID": 33,
                        "frequency": "134.975 - 324.975",
                        "powerLevel": "2.9",
                        mod_key: "4096QAM",
                        "mer": "39",
                        "plc": "264",
                        "fft": "4K",
                        "nonCorrErrors": 0,
                    },
                    {
                        "channelID": 34,
                        "frequency": "750.975 - 860.975",
                        "powerLevel": "2.4",
                        mod_key: "4096QAM",
                        "mer": "36",
                        "plc": "822",
                        "fft": "4K",
                        "nonCorrErrors": 61,
                    },
                ],
            },
            "channelUs": {
                "docsis30": [
                    {
                        "channelID": 2,
                        "frequency": "37.201",
                        "powerLevel": "41.5",
                        mod_key: "64QAM",
                        "multiplex": "ATDMA",
                    },
                    {
                        "channelID": 3,
                        "frequency": "44.601",
                        "powerLevel": "40.5",
                        mod_key: "64QAM",
                        "multiplex": "ATDMA",
                    },
                    {
                        "channelID": 1,
                        "frequency": "30.801",
                        "powerLevel": "41.8",
                        mod_key: "64QAM",
                        "multiplex": "ATDMA",
                    },
                ],
                "docsis31": [
                    {
                        "channelID": 5,
                        "frequency": "48.025 - 64.825",
                        "powerLevel": "34.8",
                        mod_key: "256QAM",
                        "activesub": "320",
                        "fft": "2K",
                    },
                ],
            },
        },
    }


BASE_LOG = [
    {
        "date": "02.10.26",
        "time": "09:46:41",
        "msg": "Internetverbindung wurde erfolgreich hergestellt. IP-Adresse: 203.0.113.42",
        "group": "net",
        "id": 23,
    },
    {
        "date": "02.10.26",
        "time": "09:46:38",
        "msg": "Kabel-Internet ist verfügbar (Synchronisierung besteht mit 1126400/52480 kbit/s).",
        "group": "net",
        "id": 712,
    },
    {
        "date": "02.10.26",
        "time": "09:45:30",
        "msg": "Kabel-Internet Synchronisierung beginnt (Training).",
        "group": "net",
        "id": 711,
    },
    {
        "date": "01.10.26",
        "time": "23:52:28",
        "msg": "Kabel-Internet antwortet nicht (Keine Synchronisierung).",
        "group": "net",
        "id": 710,
    },
    {
        "date": "30.09.26",
        "time": "20:46:44",
        "msg": "Kabel-Internet antwortet nicht (Keine Synchronisierung).",
        "group": "net",
        "id": 710,
    },
    {
        "date": "30.09.26",
        "time": "12:16:40",
        "msg": "Kabel-Internet antwortet nicht (Keine Synchronisierung).",
        "group": "net",
        "id": 710,
    },
    {
        "date": "29.09.26",
        "time": "11:17:57",
        "msg": "Anmeldung des Benutzers admin an der FRITZ!Box-Benutzeroberfläche.",
        "group": "sys",
        "id": 1,
    },
]


class MockFritzBox:
    """State of the simulated box."""

    def __init__(self, md5: bool = False, iterations: int = 10) -> None:
        self.md5 = md5
        self.iterations = iterations
        self.sids: set[str] = set()
        self.challenge = ""
        self.corr_offset = 0
        self.field_style = "new"
        self.log = copy.deepcopy(BASE_LOG)
        self.log_as_lists = False
        self.logins = 0
        self.expire_sessions = False
        self.fail_docinfo = False

    def new_challenge(self) -> str:
        if self.md5:
            self.challenge = secrets.token_hex(4)
        else:
            s1, s2 = secrets.token_hex(16), secrets.token_hex(16)
            self.challenge = f"2${self.iterations}${s1}${self.iterations}${s2}"
        return self.challenge

    def expected(self) -> str:
        c = self.challenge
        if not c.startswith("2$"):
            d = hashlib.md5(f"{c}-{PASSWORD}".encode("utf-16le")).hexdigest()
            return f"{c}-{d}"
        _, i1, s1, i2, s2 = c.split("$")
        h1 = hashlib.pbkdf2_hmac(
            "sha256", PASSWORD.encode(), bytes.fromhex(s1), int(i1)
        )
        h2 = hashlib.pbkdf2_hmac("sha256", h1, bytes.fromhex(s2), int(i2))
        return f"{s2}${h2.hex()}"

    def add_log(self, date: str, time: str, msg: str) -> None:
        self.log.insert(
            0, {"date": date, "time": time, "msg": msg, "group": "net", "id": 710}
        )

    # --------------------------------------------------------------- #

    def app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/login_sid.lua", self.login_get)
        app.router.add_post("/login_sid.lua", self.login_post)
        app.router.add_post("/data.lua", self.data)
        return app

    @staticmethod
    def _xml(sid: str, challenge: str = "", block: int = 0) -> web.Response:
        body = (
            '<?xml version="1.0" encoding="utf-8"?><SessionInfo>'
            f"<SID>{sid}</SID><Challenge>{challenge}</Challenge>"
            f"<BlockTime>{block}</BlockTime><Rights></Rights></SessionInfo>"
        )
        return web.Response(text=body, content_type="text/xml")

    async def login_get(self, request: web.Request) -> web.Response:
        if request.query.get("logout"):
            self.sids.discard(request.query.get("sid", ""))
            return self._xml("0000000000000000", self.new_challenge())
        return self._xml("0000000000000000", self.new_challenge())

    async def login_post(self, request: web.Request) -> web.Response:
        form = await request.post()
        if form.get("username") == USERNAME and form.get("response") == self.expected():
            sid = secrets.token_hex(8)
            self.sids.add(sid)
            self.logins += 1
            return self._xml(sid)
        return self._xml("0000000000000000", self.new_challenge(), block=0)

    async def data(self, request: web.Request) -> web.Response:
        form = await request.post()
        sid = str(form.get("sid", ""))
        if self.expire_sessions:
            self.sids.clear()
            self.expire_sessions = False
        if sid not in self.sids:
            # This is how the box behaves: login page instead of JSON
            return web.Response(
                text="<html><body>Anmeldung</body></html>", content_type="text/html"
            )
        page = form.get("page")
        if page == "docInfo":
            if self.fail_docinfo:
                return web.json_response({"pid": "docInfo", "sid": sid, "data": {}})
            return web.json_response(
                docinfo_payload(sid, self.corr_offset, self.field_style)
            )
        if page == "log":
            log: list[Any] = self.log
            if self.log_as_lists:
                log = [
                    [e["date"], e["time"], e["msg"], e["id"], e["group"]]
                    for e in self.log
                ]
            return web.json_response({"pid": "log", "sid": sid, "data": {"log": log}})
        return web.json_response({"pid": page, "sid": sid, "data": {}})
