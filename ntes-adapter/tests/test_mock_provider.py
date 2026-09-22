from app.providers.mock_provider import MockProvider


def test_default_mock_returns_deterministic_shape():
    provider = MockProvider()
    board = provider.get_live_station("GHY")
    assert board.station_code == "GHY"
    assert len(board.events) > 0


def test_mock_provider_honors_injected_events():
    from datetime import datetime

    from app.models import EventType, TrainEvent, TrainEventStatus

    custom_event = TrainEvent(
        train_no="99999",
        train_name="TEST TRAIN",
        station_code="GHY",
        event_type=EventType.DEPARTURE,
        status=TrainEventStatus.ON_TIME,
        scheduled_time=datetime(2026, 9, 22, 2, 0),
        actual_or_expected_time=datetime(2026, 9, 22, 2, 0),
        delay_minutes=0,
    )
    provider = MockProvider(events={"GHY": [custom_event]})
    board = provider.get_live_station("GHY")
    assert board.events == [custom_event]


def test_mock_provider_can_simulate_failure():
    provider = MockProvider(raise_error=ConnectionError("simulated NTES outage"))
    try:
        provider.get_live_station("GHY")
        assert False, "expected ConnectionError"
    except ConnectionError:
        pass
