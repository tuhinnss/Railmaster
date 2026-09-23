from datetime import datetime

import pytest

from app.models import EventType
from app.providers.fixture_provider import CapturedFixtureProvider


def test_serves_real_captured_trains_for_ghy():
    board = CapturedFixtureProvider().get_live_station("GHY")

    assert board.station_code == "GHY"
    assert len(board.events) > 10
    # Real train identities from the captured NTES response -- if the
    # fixture or parser regresses, these disappear.
    train_nos = {e.train_no for e in board.events}
    assert "15602" in train_nos
    assert "13174" in train_nos
    names = {e.train_name for e in board.events}
    assert "AVADH ASSAM EXP" in names


def test_serves_real_captured_trains_for_lmg():
    board = CapturedFixtureProvider().get_live_station("LMG")

    assert board.station_code == "LMG"
    train_nos = {e.train_no for e in board.events}
    assert "12424" in train_nos  # DBRT RAJDHANI
    assert any(e.event_type == EventType.ARRIVAL for e in board.events)
    assert any(e.event_type == EventType.DEPARTURE for e in board.events)


def test_times_are_anchored_to_today_not_capture_date():
    """The captured HTML carries only HH:MM, so the parser anchors to the
    query moment. Documented behavior, not an accident -- the times are
    real, the date they're shown against is today's."""
    board = CapturedFixtureProvider().get_live_station("GHY")
    timed = [e for e in board.events if e.actual_or_expected_time is not None]

    assert timed, "expected at least some events with parsed times"
    today = datetime.now().date()
    # Every event lands on today or tomorrow (the parser rolls past-midnight
    # times onto the next calendar day).
    for event in timed:
        assert (event.actual_or_expected_time.date() - today).days in (0, 1)


def test_uncaptured_station_raises_rather_than_substituting_mock_data():
    """RNY was never captured. Raising makes the poller back off and the
    corridor honestly report no data -- silently returning canned trains
    here would present fake data as real."""
    with pytest.raises(ValueError, match="No captured NTES response"):
        CapturedFixtureProvider().get_live_station("RNY")
