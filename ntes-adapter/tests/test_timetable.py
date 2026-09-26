"""Booked timetables: the "Trains between stations" parser against the
real responses captured on 2026-09-26, the providers, the poller's
about-daily refresh, and the API endpoint."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import CORRIDORS, TIMETABLE_MAX_AGE_HOURS, TIMETABLE_RETRY_MINUTES
from app.models import CorridorTimetable, TimetabledTrain
from app.poller import Poller
from app.providers.base import RailwayDataProvider
from app.providers.fixture_provider import CapturedFixtureProvider
from app.providers.mock_provider import MockProvider
from app.providers.timetable_parser import parse_trains_between_html
from app.store import Store

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


# --- poller ------------------------------------------------------------------


class CountingProvider(RailwayDataProvider):
    name = "counting"

    def __init__(self, fail: bool = False):
        self.calls: list[str] = []
        self.fail = fail

    def get_live_station(self, station_code, window_hours=4):
        raise NotImplementedError

    def get_timetable(self, corridor):
        self.calls.append(corridor.corridor_id)
        if self.fail:
            raise RuntimeError("NTES down")
        return CorridorTimetable(corridor=corridor.corridor_id, fetched_at=datetime(2026, 9, 26, 20, 0), provider=self.name, a_to_b=[], b_to_a=[])


NOW = datetime(2026, 9, 26, 20, 0)


def test_one_corridor_per_cycle_then_nothing_until_a_day_later():
    provider, store = CountingProvider(), Store()
    poller = Poller(provider, store)
    for minute in range(0, 12, 3):
        poller._refresh_timetables(NOW + timedelta(minutes=minute))
    assert provider.calls == ["GHY-LMG", "LMG-RNY", "NDLS-GZB"]
    assert store.get_timetable("NDLS-GZB") is not None

    poller._refresh_timetables(NOW + timedelta(hours=TIMETABLE_MAX_AGE_HOURS, minutes=1))
    assert provider.calls[-1] == "GHY-LMG" and len(provider.calls) == 4


def test_a_failed_fetch_waits_before_retrying_and_keeps_nothing_false():
    provider, store = CountingProvider(fail=True), Store()
    poller = Poller(provider, store)
    poller._refresh_timetables(NOW)
    poller._refresh_timetables(NOW + timedelta(minutes=1))  # moves on to the next corridor
    poller._refresh_timetables(NOW + timedelta(minutes=2))
    poller._refresh_timetables(NOW + timedelta(minutes=3))  # all three waiting to retry
    assert provider.calls == ["GHY-LMG", "LMG-RNY", "NDLS-GZB"]
    assert store.get_timetable("GHY-LMG") is None

    poller._refresh_timetables(NOW + timedelta(minutes=TIMETABLE_RETRY_MINUTES + 1))
    assert provider.calls[-1] == "GHY-LMG"


def test_a_restart_does_not_refetch_a_fresh_timetable_from_the_same_provider():
    store = Store()
    store.set_timetable(CorridorTimetable(corridor="GHY-LMG", fetched_at=NOW - timedelta(hours=2), provider="counting", a_to_b=[], b_to_a=[]))
    store.set_timetable(CorridorTimetable(corridor="LMG-RNY", fetched_at=NOW - timedelta(hours=2), provider="captured_fixture", a_to_b=[], b_to_a=[]))
    provider = CountingProvider()
    Poller(provider, store)._refresh_timetables(NOW)
    # GHY-LMG is this provider's and two hours old: skipped. LMG-RNY came
    # from a different provider, so it is replaced.
    assert provider.calls == ["LMG-RNY"]


# --- API ---------------------------------------------------------------------

client = TestClient(main.app)


@pytest.fixture
def fresh_store():
    main.store = Store(data_dir=None)
    yield


def test_timetable_endpoint_is_404_until_one_is_fetched(fresh_store):
    assert client.get("/api/v1/corridors/GHY-LMG/timetable").status_code == 404
    main.store.set_timetable(CapturedFixtureProvider().get_timetable(CORRIDOR["GHY-LMG"]))
    body = client.get("/api/v1/corridors/GHY-LMG/timetable").json()
    assert body["provider"] == "captured_fixture"
    assert len(body["a_to_b"]) == 31
    assert client.get("/api/v1/corridors/NOPE-NOPE/timetable").status_code == 404
