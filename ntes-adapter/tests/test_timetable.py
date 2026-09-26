"""Booked timetables: the "Trains between stations" parser against the
real responses captured on 2026-09-26, and the providers."""

from datetime import datetime
from pathlib import Path

import pytest

from app.config import CORRIDORS
from app.models import TimetabledTrain
from app.providers.fixture_provider import CapturedFixtureProvider
from app.providers.mock_provider import MockProvider
from app.providers.timetable_parser import parse_trains_between_html

FIXTURES = Path(__file__).parent / "fixtures"
CORRIDOR = {c.corridor_id: c for c in CORRIDORS}


def captured(name: str) -> str:
    return (FIXTURES / f"ntes_real_trains_between_{name}.html").read_text(encoding="utf-8", errors="replace")


# --- parser ------------------------------------------------------------------


@pytest.mark.parametrize("name,count", [("NDLS_GZB", 160), ("GZB_NDLS", 169), ("GHY_LMG", 31), ("LMG_GHY", 30)])
def test_every_train_the_page_announces_is_parsed(name, count):
    assert len(parse_trains_between_html(captured(name))) == count


def test_a_train_card_parses_to_its_booked_times_and_days():
    first = parse_trains_between_html(captured("GHY_LMG"))[0]
    assert first == TimetabledTrain(
        train_no="15910",
        train_name="AVADH ASSAM EXP",
        train_type="Mail Express",
        running_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],  # "Daily"
        from_station="GHY",
        departs="01:15",
        to_station="LMG",
        arrives="04:25",
    )
    weekly = [t for t in parse_trains_between_html(captured("LMG_GHY")) if t.train_no == "14619"]
    assert weekly[0].running_days == ["Fri"]


def test_a_delhi_query_includes_neighbouring_terminals():
    """NTES answers "from NDLS" with every Delhi-area terminal. The parser
    keeps each train's real end station so consumers can filter."""
    trains = parse_trains_between_html(captured("NDLS_GZB"))
    starts = {t.from_station for t in trains}
    assert {"NDLS", "DLI", "ANVT", "NZM"} <= starts
    assert sum(t.from_station == "NDLS" for t in trains) == 48


def test_a_short_parse_is_an_error_not_a_smaller_timetable():
    html = captured("GHY_LMG")
    first_card = html.index('<tr class=" w3-round ">')
    second_card = html.index('<tr class=" w3-round ">', first_card + 1)
    with pytest.raises(ValueError, match="31 trains but 30 parsed"):
        parse_trains_between_html(html[:first_card] + html[second_card:])


def test_a_page_without_the_result_header_is_rejected():
    with pytest.raises(ValueError, match="header"):
        parse_trains_between_html("<html><body>Something else entirely</body></html>")


def test_unknown_running_days_are_refused():
    html = captured("GHY_LMG").replace("Daily | Mail Express", "Alternate days | Mail Express", 1)
    with pytest.raises(ValueError, match="running days"):
        parse_trains_between_html(html)


# --- providers ---------------------------------------------------------------


def test_fixture_timetable_reports_its_capture_time_not_today():
    timetable = CapturedFixtureProvider().get_timetable(CORRIDOR["NDLS-GZB"])
    assert timetable.provider == "captured_fixture"
    assert timetable.fetched_at == datetime(2026, 9, 26, 13, 10)
    assert (len(timetable.a_to_b), len(timetable.b_to_a)) == (160, 169)


def test_uncaptured_and_mock_timetables_are_absent_not_invented():
    assert CapturedFixtureProvider().get_timetable(CORRIDOR["LMG-RNY"]) is None
    assert MockProvider().get_timetable(CORRIDOR["GHY-LMG"]) is None
