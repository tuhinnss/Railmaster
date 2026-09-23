"""Canned, deterministic provider. Everything downstream -- API, poller,
and every test -- runs against this by default; NTESProvider is opt-in.

Default canned data gives each configured station a small, realistic set
of train events with a mix of on-time/delayed/source/terminating, timed
so that some nights the 01:00-05:00 window is clear and some it isn't,
useful for exercising the frequency math without needing real history.
Tests that need specific scenarios (a guaranteed-clear night, a forced
failure to simulate NTES being down, etc.) pass their own `events` or
`raise_error`.
"""

from datetime import datetime

from app.models import EventType, StationLiveBoard, TrainEvent, TrainEventStatus
from app.providers.base import RailwayDataProvider


def _default_events(station_code: str, query_time: datetime) -> list[TrainEvent]:
    today = query_time.date()
    return [
        TrainEvent(
            train_no="15602",
            train_name="MOCK EXPRESS",
            station_code=station_code,
            event_type=EventType.DEPARTURE,
            status=TrainEventStatus.ON_TIME,
            scheduled_time=datetime.combine(today, datetime.min.time()).replace(hour=22, minute=50),
            actual_or_expected_time=datetime.combine(today, datetime.min.time()).replace(hour=22, minute=50),
            delay_minutes=0,
            platform="4",
        ),
        TrainEvent(
            train_no="15909",
            train_name="MOCK ASSAM EXP",
            station_code=station_code,
            event_type=EventType.ARRIVAL,
            status=TrainEventStatus.DELAYED,
            scheduled_time=datetime.combine(today, datetime.min.time()).replace(hour=21, minute=30),
            actual_or_expected_time=datetime.combine(today, datetime.min.time()).replace(hour=22, minute=55),
            delay_minutes=85,
            platform="1",
        ),
    ]


class MockProvider(RailwayDataProvider):
    name = "mock"

    def __init__(
        self,
        events: dict[str, list[TrainEvent]] | None = None,
        raise_error: Exception | None = None,
    ):
        self._events = events
        self._raise_error = raise_error

    def get_live_station(self, station_code: str, window_hours: int = 4) -> StationLiveBoard:
        if self._raise_error is not None:
            raise self._raise_error

        query_time = datetime.now()
        events = (
            self._events.get(station_code, [])
            if self._events is not None
            else _default_events(station_code, query_time)
        )
        return StationLiveBoard(
            station_code=station_code,
            fetched_at=query_time,
            window_hours=window_hours,
            events=events,
        )
