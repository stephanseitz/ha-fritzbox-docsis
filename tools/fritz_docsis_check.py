#!/usr/bin/env python3
"""Check script: tests FRITZ!Box access and cable data – without Home Assistant.

Usage (only Python 3.10+ required, no extra packages):

    python fritz_docsis_check.py --url https://xxxx.myfritz.net:44443 --user homeassistant

You will be prompted for the password. The script
  1. logs in (PBKDF2 or MD5),
  2. reads the cable information (data.lua?page=docInfo) and prints it as a table,
  3. reads the event log and shows the latest cable events,
  4. saves the raw data as JSON (fritz_docsis_raw.json) – useful if something
     does not look right. The file contains no credentials and only the cable
     entries of the event log (the full log lists devices, IP addresses, logins
     and calls).
"""

from __future__ import annotations

import argparse
import contextlib
import getpass
import hashlib
import json
from pathlib import Path
import ssl
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "custom_components" / "fritzbox_docsis"))
sys.path.insert(0, str(HERE))

# Imported intentionally after the sys.path tweak above
from parser import (  # noqa: E402
    classify_cable_event,
    parse_docinfo,
    parse_log,
)

INVALID_SID = "0000000000000000"


def compute_response(challenge: str, password: str) -> str:
    if challenge.startswith("2$"):
        _, i1, s1, i2, s2 = challenge.split("$")
        h1 = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(s1), int(i1)
        )
        h2 = hashlib.pbkdf2_hmac("sha256", h1, bytes.fromhex(s2), int(i2))
        return f"{s2}${h2.hex()}"
    safe = "".join(c if ord(c) < 256 else "." for c in password)
    return f"{challenge}-{hashlib.md5(f'{challenge}-{safe}'.encode('utf-16le')).hexdigest()}"


def _log_message(item: object) -> str:
    if isinstance(item, dict):
        return str(item.get("msg") or item.get("message") or item.get("text") or "")
    if isinstance(item, (list, tuple)) and len(item) >= 3:
        return str(item[2])
    return ""


def cable_log_only(payload: dict) -> dict:
    """Keep only the cable entries of the event log for the raw data file."""
    data = payload.get("data")
    log = data.get("log") if isinstance(data, dict) else None
    if not isinstance(log, list):
        return {}
    return {"data": {"log": [i for i in log if classify_cable_event(_log_message(i))]}}


class Box:
    def __init__(self, url: str, insecure: bool) -> None:
        self.url = url.rstrip("/")
        self.ctx = ssl.create_default_context()
        if insecure:
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE

    def _req(
        self, path: str, data: dict | None = None, query: dict | None = None
    ) -> str:
        url = f"{self.url}{path}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        with urllib.request.urlopen(
            url, data=body, timeout=30, context=self.ctx
        ) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def login(self, user: str, password: str) -> str:
        root = ET.fromstring(self._req("/login_sid.lua", query={"version": "2"}))
        challenge = root.findtext("Challenge") or ""
        block = int(root.findtext("BlockTime") or 0)
        if block:
            sys.exit(f"Login blocked for {block} s (too many failed attempts).")
        print(f"  Method: {'PBKDF2' if challenge.startswith('2$') else 'MD5'}")
        root = ET.fromstring(
            self._req(
                "/login_sid.lua",
                data={
                    "username": user,
                    "response": compute_response(challenge, password),
                },
                query={"version": "2"},
            )
        )
        sid = root.findtext("SID") or INVALID_SID
        if sid == INVALID_SID:
            sys.exit(
                "Login failed: wrong username/password or the user has no internet access permission."
            )
        return sid

    def page(self, sid: str, page: str) -> dict:
        text = self._req(
            "/data.lua",
            data={
                "xhr": "1",
                "sid": sid,
                "lang": "de",
                "page": page,
                "xhrId": "all",
                "no_sidrenew": "",
            },
        )
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            sys.exit(
                f'Page {page}: no JSON response (missing permissions? The user needs "FRITZ!Box Settings").'
            )

    def logout(self, sid: str) -> None:
        with contextlib.suppress(Exception):
            self._req("/login_sid.lua", query={"logout": "1", "sid": sid})


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--url",
        required=True,
        help="e.g. https://xxxx.myfritz.net:44443 or http://192.168.178.1",
    )
    ap.add_argument("--user", required=True, help="FRITZ!Box username")
    ap.add_argument(
        "--insecure",
        action="store_true",
        help="do not verify the SSL certificate (only for https with an IP address)",
    )
    ap.add_argument("--out", default="fritz_docsis_raw.json", help="file for raw data")
    args = ap.parse_args()

    password = getpass.getpass("Password: ")
    box = Box(args.url, args.insecure)

    print("1) Login …")
    sid = box.login(args.user, password)
    print("  OK")
    try:
        print("2) Cable information …")
        raw_doc = box.page(sid, "docInfo")
        info = parse_docinfo(raw_doc)
        print(
            f"  {len(info.downstream)} downstream and {len(info.upstream)} upstream channels\n"
        )
        print(
            f"  {'Dir.':8} {'Frequency':>16} {'Power':>7} {'MSE/MER':>8} {'Mod.':>8} {'corr.':>10} {'uncorr.':>8}"
        )
        for ch in info.downstream.values():
            q = ch.mse_db if ch.docsis == "3.0" else ch.mer_db
            print(
                f"  DS {ch.docsis:5} {ch.label:>16} {ch.power_dbmv or 0:7.1f} {q if q is not None else '':>8} "
                f"{ch.modulation or '':>8} {ch.corr_errors if ch.corr_errors is not None else '-':>10} "
                f"{ch.noncorr_errors if ch.noncorr_errors is not None else '-':>8}"
            )
        for ch in info.upstream.values():
            print(
                f"  US {ch.docsis:5} {ch.label:>16} {ch.power_dbmv or 0:7.1f} {'':>8} {ch.modulation or '':>8}"
            )

        print("\n3) Event log …")
        raw_log = box.page(sid, "log")
        try:
            entries = parse_log(raw_log)
            cable = [e for e in entries if classify_cable_event(e.message)]
            print(
                f"  {len(entries)} entries, {len(cable)} of them cable events. Latest:"
            )
            for e in cable[:8]:
                print(f"   {e.timestamp:%d.%m.%Y %H:%M:%S}  {e.message}")
        except ValueError as err:
            print(f"  Could not read the log: {err}")

        raw_doc.pop("sid", None)
        Path(args.out).write_text(
            json.dumps(
                {"docInfo": raw_doc, "log": cable_log_only(raw_log)},
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        print(f"\nRaw data saved to {args.out}")
        print("All good – the integration can be set up.")
    finally:
        box.logout(sid)


if __name__ == "__main__":
    main()
