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

from app.models import StationLiveBoard
from app.providers.base import RailwayDataProvider
from app.providers.ntes_parser import parse_live_station_html

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"

# Station code -> (captured response, window_hours it was captured at).
CAPTURED_STATIONS: dict[str, tuple[str, int]] = {
    "GHY": ("ntes_real_live_station_GHY.html", 4),
    "LMG": ("ntes_real_live_station_LMG.html", 4),
    "NDLS": ("ntes_real_live_station_NDLS.html", 8),
    "GZB": ("ntes_real_live_station_GZB.html", 8),
}


class CapturedFixtureProvider(RailwayDataProvider):
    name = "captured_fixture"

    def __init__(self, fixture_dir: Path = FIXTURE_DIR):
        self._fixture_dir = fixture_dir

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
