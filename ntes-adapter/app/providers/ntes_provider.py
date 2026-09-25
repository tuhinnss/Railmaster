"""Best-effort client for NTES's undocumented, unofficial "Live Station"
query. NOT an authorized integration -- there is no public developer API
for NTES; this reverse-engineers the same request the enquiry.indianrail
.gov.in web app itself makes. See README.md's investigation section for
what was actually confirmed (real captured responses, real station
codes) vs. assumed. Opt-in only: nothing in this service uses this by
default, including all tests.

Mechanics (confirmed by live investigation, Sept 2026):
1. GET /mntes once, to establish session cookies (JSESSIONID + others).
2. GET /mntes/GetCSRFToken?t=<ms-timestamp> -> a fresh, session-tied,
   randomly-named hidden form field each time. Single-use in the real
   app's flow; we fetch one per query rather than reusing it.
3. POST /mntes/q?opt=LiveStation&subOpt=show with the station formatted
   as "CODE - NAME" (exactly as the app's own JS builds it), an nHr
   radio value (confirmed choices: 2, 4, 8), and the CSRF field.
4. The response is a full server-rendered HTML page, not JSON -- parsed
   by ntes_parser.parse_live_station_html.

Respect NTES's own behavior: no retry storms, no bypassing CAPTCHA (none
was encountered on this specific query during investigation, but nothing
here should be built assuming that holds under heavy or automated load),
no parallel hammering. The background poller (poller.py) is the only
caller and runs on a modest configurable interval.
"""

import re
import time
from datetime import datetime

import httpx

from app.config import CORRIDORS
from app.models import StationLiveBoard
from app.providers.base import RailwayDataProvider
from app.providers.ntes_parser import parse_live_station_html

BASE_URL = "https://enquiry.indianrail.gov.in/mntes"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_CSRF_FIELD_RE = re.compile(r"name='([^']+)'\s+value='([^']+)'")

STATION_NAMES: dict[str, str] = {}
for _corridor in CORRIDORS:
    STATION_NAMES[_corridor.station_a] = _corridor.station_a_name
    STATION_NAMES[_corridor.station_b] = _corridor.station_b_name


class NTESProvider(RailwayDataProvider):
    name = "ntes_live"
    records_observations = True

    def __init__(self, timeout_seconds: float = 15.0):
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={"User-Agent": USER_AGENT, "Referer": BASE_URL},
            timeout=timeout_seconds,
            follow_redirects=True,
        )
        self._session_established = False

    def close(self) -> None:
        self._client.close()

    def _ensure_session(self) -> None:
        if not self._session_established:
            self._client.get("")
            self._session_established = True

    def _get_csrf_field(self) -> tuple[str, str]:
        resp = self._client.get(f"/GetCSRFToken?t={int(time.time() * 1000)}")
        resp.raise_for_status()
        match = _CSRF_FIELD_RE.search(resp.text)
        if not match:
            raise RuntimeError(
                "NTES: couldn't find a CSRF token field in the response -- "
                "the page format has likely changed since this was written"
            )
        return match.group(1), match.group(2)

    def get_live_station(self, station_code: str, window_hours: int = 4) -> StationLiveBoard:
        if station_code not in STATION_NAMES:
            raise ValueError(
                f"NTESProvider is scoped to the configured corridors only; "
                f"{station_code!r} isn't one of {sorted(STATION_NAMES)}"
            )
        if window_hours not in (2, 4, 8):
            raise ValueError(f"NTES only supports 2/4/8 hour windows for this query, got {window_hours}")

        self._ensure_session()
        csrf_name, csrf_value = self._get_csrf_field()
        query_time = datetime.now()

        resp = self._client.post(
            "/q",
            params={"opt": "LiveStation", "subOpt": "show"},
            data={
                "lan": "en",
                "jFromStationInput": f"{station_code} - {STATION_NAMES[station_code]}",
                "jToStationInput": "",
                "nHr": str(window_hours),
                "appLang": "en",
                "jStnName": "",
                "jStation": "",
                csrf_name: csrf_value,
            },
        )
        resp.raise_for_status()
        return parse_live_station_html(resp.text, station_code, query_time, window_hours)
