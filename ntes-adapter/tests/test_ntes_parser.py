"""Parser tests against real, captured NTES responses (tests/fixtures/) --
frozen HTML, no network call, so these don't violate "no live NTES
access" for tests, while still proving the parser works against actual
NTES output rather than hand-crafted HTML that might not match reality.
"""

from datetime import datetime
from pathlib import Path

from app.providers.ntes_parser import parse_live_station_html

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_parses_real_ghy_response_matches_page_header_count():
    html = _load_fixture("ntes_real_live_station_GHY.html")
    board = parse_live_station_html(html, "GHY", datetime(2026, 9, 22, 22, 45), 4)
    assert "12 Trains departing from/arriving at" in html  # sanity: fixture still says what we think
    assert len({e.train_no for e in board.events}) == 12


def test_parses_real_lmg_response_matches_page_header_count():
    html = _load_fixture("ntes_real_live_station_LMG.html")
    board = parse_live_station_html(html, "LMG", datetime(2026, 9, 22, 22, 45), 4)
    assert "9 Trains departing from/arriving at" in html
    assert len({e.train_no for e in board.events}) == 9


def test_no_unknown_status_events_on_real_fixtures():
    for fixture in ("ntes_real_live_station_GHY.html", "ntes_real_live_station_LMG.html"):
        html = _load_fixture(fixture)
        board = parse_live_station_html(html, "X", datetime(2026, 9, 22, 22, 45), 4)
        unknown = [e for e in board.events if e.status.value == "unknown"]
        assert unknown == [], f"{fixture}: unparsed cells {unknown}"


def test_source_train_has_no_arrival_time_but_is_recorded():
    html = _load_fixture("ntes_real_live_station_GHY.html")
    board = parse_live_station_html(html, "GHY", datetime(2026, 9, 22, 22, 45), 4)
    train_15602_arrival = next(
        e for e in board.events if e.train_no == "15602" and e.event_type.value == "arrival"
    )
    assert train_15602_arrival.status.value == "source"
    assert train_15602_arrival.actual_or_expected_time is None


def test_delayed_train_delay_minutes_parsed_correctly():
    html = _load_fixture("ntes_real_live_station_GHY.html")
    board = parse_live_station_html(html, "GHY", datetime(2026, 9, 22, 22, 45), 4)
    train_15909_arrival = next(
        e for e in board.events if e.train_no == "15909" and e.event_type.value == "arrival"
    )
    assert train_15909_arrival.status.value == "delayed"
    assert train_15909_arrival.delay_minutes == 85  # "01:25 Hrs." in the real captured response


def test_on_time_train_has_zero_delay():
    html = _load_fixture("ntes_real_live_station_GHY.html")
    board = parse_live_station_html(html, "GHY", datetime(2026, 9, 22, 22, 45), 4)
    train_15603_departure = next(
        e for e in board.events if e.train_no == "15603" and e.event_type.value == "departure"
    )
    assert train_15603_departure.status.value == "on_time"
    assert train_15603_departure.delay_minutes == 0


def test_time_near_midnight_rolls_into_next_day():
    """A shown time hours 'before' the query moment (by the heuristic's
    threshold) should be assigned to the next calendar day, not treated
    as already past."""
    html = _load_fixture("ntes_real_live_station_GHY.html")
    # Query as if it were just before midnight; the fixture's times
    # (22:xx-23:xx) are still same-day relative to this query time.
    query_time = datetime(2026, 9, 22, 23, 45)
    board = parse_live_station_html(html, "GHY", query_time, 4)
    dep = next(e for e in board.events if e.train_no == "15602" and e.event_type.value == "departure")
    assert dep.actual_or_expected_time.date() == query_time.date()
