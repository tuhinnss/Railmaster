"""Replays the real NTES responses captured during investigation.

These are genuine NTES "Live Station" pages for GHY and LMG -- real train
numbers, names, delays and platforms -- saved under tests/fixtures/ and
parsed by the same ntes_parser.py that handles live responses. Nothing
here is invented.

What IS adjusted: the captured HTML carries only HH:MM times, no dates
(NTES's rows have no clean per-row date field -- see ntes_parser), so the
parser anchors them to whatever query time it's given. This provider
anchors to "now", which means the captured evening's timetable is
replayed against today's date. Train identities and timings are real; the
calendar date they're shown against is not the date they were observed.
Anything surfacing this data should say so.

It also replays the "Trains between stations" timetables captured on
2026-09-26 for NDLS-GZB and GHY-LMG, reporting the capture time as when
they were fetched.

Only captured stations are available. RNY was never captured, so it raises
like any other fetch failure -- the poller backs off and the corridor
honestly reports no data, rather than quietly substituting mock trains for
real ones.

Fixtures are produced by scripts/capture_fixture.py. The window each one
was captured at is recorded here rather than taken from the caller, so a
board never claims a 4-hour window while holding 8 hours of movements.
"""

from datetime import datetime
from pathlib import Path

from app.config import Corridor
from app.models import CorridorTimetable, StationLiveBoard
from app.providers.base import RailwayDataProvider
from app.providers.ntes_parser import parse_live_station_html
from app.providers.timetable_parser import parse_trains_between_html

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"

# Station code -> (captured response, window_hours it was captured at).
CAPTURED_STATIONS: dict[str, tuple[str, int]] = {
    "GHY": ("ntes_real_live_station_GHY.html", 4),
    "LMG": ("ntes_real_live_station_LMG.html", 4),
    "NDLS": ("ntes_real_live_station_NDLS.html", 8),
    "GZB": ("ntes_real_live_station_GZB.html", 8),
}


# Corridor -> (a-to-b capture, b-to-a capture, when they were captured).
# Real "Trains between stations" answers; the capture time is reported as
# fetched_at, so a replayed timetable never claims to be today's.
CAPTURED_TIMETABLES: dict[str, tuple[str, str, datetime]] = {
    "NDLS-GZB": (
        "ntes_real_trains_between_NDLS_GZB.html",
        "ntes_real_trains_between_GZB_NDLS.html",
        datetime(2026, 9, 26, 13, 10),
    ),
    "GHY-LMG": (
        "ntes_real_trains_between_GHY_LMG.html",
        "ntes_real_trains_between_LMG_GHY.html",
        datetime(2026, 9, 26, 13, 11),
    ),
}


class CapturedFixtureProvider(RailwayDataProvider):
    name = "captured_fixture"

    def __init__(self, fixture_dir: Path = FIXTURE_DIR):
        self._fixture_dir = fixture_dir

    def get_timetable(self, corridor: Corridor) -> CorridorTimetable | None:
        captured = CAPTURED_TIMETABLES.get(corridor.corridor_id)
        if captured is None:
            return None  # LMG-RNY's timetable was never captured
        a_to_b, b_to_a, captured_at = captured
        return CorridorTimetable(
            corridor=corridor.corridor_id,
            fetched_at=captured_at,
            provider=self.name,
            a_to_b=self._parse_capture(a_to_b),
            b_to_a=self._parse_capture(b_to_a),
        )

    def _parse_capture(self, filename: str):
        html = (self._fixture_dir / filename).read_text(encoding="utf-8", errors="replace")
        return parse_trains_between_html(html)

    def get_live_station(self, station_code: str, window_hours: int = 4) -> StationLiveBoard:
        captured = CAPTURED_STATIONS.get(station_code)
        if captured is None:
            raise ValueError(
                f"No captured NTES response for station {station_code!r} "
                f"(captured: {sorted(CAPTURED_STATIONS)})"
            )
        filename, captured_hours = captured

        html = (self._fixture_dir / filename).read_text(encoding="utf-8", errors="replace")
        return parse_live_station_html(html, station_code, datetime.now(), captured_hours)
