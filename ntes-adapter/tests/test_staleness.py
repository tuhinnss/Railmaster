from datetime import datetime, timedelta

from app.config import STALE_THRESHOLD_SECONDS
from app.models import EventType, StationLiveBoard, TrainEvent, TrainEventStatus
from app.store import Store


def make_board(station_code: str, fetched_at: datetime) -> StationLiveBoard:
    return StationLiveBoard(
        station_code=station_code,
        fetched_at=fetched_at,
        window_hours=4,
        events=[
            TrainEvent(
                train_no="101",
                train_name="TEST",
                station_code=station_code,
                event_type=EventType.DEPARTURE,
                status=TrainEventStatus.ON_TIME,
            )
        ],
    )


def test_fresh_fetch_is_not_stale():
    store = Store(data_dir=None)
    now = datetime.now()
    store.set_live_board("GHY", make_board("GHY", now))
    last_fetch = store.get_last_successful_fetch("GHY")
    age_seconds = (datetime.now() - last_fetch).total_seconds()
    assert age_seconds < STALE_THRESHOLD_SECONDS


def test_old_fetch_is_stale():
    store = Store(data_dir=None)
    old_time = datetime.now() - timedelta(seconds=STALE_THRESHOLD_SECONDS + 60)
    store.set_live_board("GHY", make_board("GHY", old_time))
    last_fetch = store.get_last_successful_fetch("GHY")
    age_seconds = (datetime.now() - last_fetch).total_seconds()
    assert age_seconds > STALE_THRESHOLD_SECONDS


def test_no_fetch_ever_returns_none_last_fetch():
    store = Store(data_dir=None)
    assert store.get_last_successful_fetch("GHY") is None
    assert store.get_live_board("GHY") is None


def test_poller_failure_does_not_wipe_previous_good_cache():
    """The whole point of caching: a failed refresh must leave the last
    good board in place, not clear it, so the API can serve stale-but-real
    data with a flag instead of nothing at all."""
    from app.poller import Poller
    from app.providers.mock_provider import MockProvider

    store = Store(data_dir=None)
    good_provider = MockProvider()
    poller = Poller(good_provider, store, interval_seconds=60)
    poller.poll_once()

    board_after_success = store.get_live_board("GHY")
    assert board_after_success is not None

    failing_provider = MockProvider(raise_error=ConnectionError("simulated outage"))
    poller_2 = Poller(failing_provider, store, interval_seconds=60)
    poller_2.poll_once()

    board_after_failure = store.get_live_board("GHY")
    assert board_after_failure == board_after_success  # untouched, not cleared
