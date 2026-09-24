"""Captures a real NTES Live Station response and saves it as a test fixture.

This is the tool that produced everything in tests/fixtures/. It exists so
fixtures are reproducible and refreshable rather than mystery files, and so
adding a corridor doesn't mean hand-crafting HTML.

Usage (from ntes-adapter/):
    .venv/Scripts/python.exe -m scripts.capture_fixture NDLS "NEW DELHI" [--hours 8]

Deliberately one station per invocation, with no retry loop: this hits an
undocumented endpoint on a public enquiry site, and the project's ground rules
are to query sparingly and never hammer it. Run it by hand when you actually
need a fixture, not on a schedule.

The station name must be exactly what NTES itself uses -- the site builds the
form value as "CODE - NAME". The printed page header echoes the canonical name
back, so check it against what you passed and correct if they differ.
"""

import argparse
import re
import sys
import time
from pathlib import Path

import httpx

BASE_URL = "https://enquiry.indianrail.gov.in/mntes"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_CSRF_FIELD_RE = re.compile(r"name='([^']+)'\s+value='([^']+)'")
_HEADER_RE = re.compile(r"\d+\s+Trains?\s+departing\s+from/arriving\s+at\s+[^<]*")
FIXTURE_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def capture(station_code: str, station_name: str, hours: int) -> str:
    client = httpx.Client(
        base_url=BASE_URL,
        headers={"User-Agent": USER_AGENT, "Referer": f"{BASE_URL}/"},
        timeout=30.0,
        follow_redirects=True,
    )
    try:
        client.get("")  # establish session cookies
        token_resp = client.get(f"/GetCSRFToken?t={int(time.time() * 1000)}")
        token_resp.raise_for_status()
        match = _CSRF_FIELD_RE.search(token_resp.text)
        if match is None:
            raise RuntimeError("No CSRF field in response -- NTES page format has changed")

        resp = client.post(
            "/q",
            params={"opt": "LiveStation", "subOpt": "show"},
            data={
                "lan": "en",
                "jFromStationInput": f"{station_code} - {station_name}",
                "jToStationInput": "",
                "nHr": str(hours),
                "appLang": "en",
                "jStnName": "",
                "jStation": "",
                match.group(1): match.group(2),
            },
        )
        resp.raise_for_status()
        return resp.text
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture one real NTES Live Station response.")
    parser.add_argument("station_code")
    parser.add_argument("station_name", help='exactly as NTES spells it, e.g. "NEW DELHI"')
    parser.add_argument("--hours", type=int, default=8, choices=[2, 4, 8])
    args = parser.parse_args()

    html = capture(args.station_code, args.station_name, args.hours)

    if "myTable" not in html:
        print("FAILED: no results table in the response. Check the station name spelling.", file=sys.stderr)
        return 1

    header = _HEADER_RE.search(html)
    print(f"NTES says: {header.group(0).strip() if header else '(no header found)'}")

    out = FIXTURE_DIR / f"ntes_real_live_station_{args.station_code}.html"
    out.write_text(html, encoding="utf-8")
    print(f"Saved {len(html)} bytes to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
