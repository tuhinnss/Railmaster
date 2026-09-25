"""API tests against MockProvider, driving the store directly rather than
depending on the background poller's timing -- deterministic regardless
of thread scheduling. TestClient is created without the `with` context
manager so the lifespan (and its background poller thread) never starts;
these tests only exercise the route handlers against a store we control.
"""

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import main
from app.models import EventType, PredictedWindow, StationLiveBoard, TrainEvent, TrainEventStatus
from app.store import Store

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def fresh_store():
    """GHY-LMG and LMG-RNY share the LMG station, so a global store must
    be reset between tests -- otherwise one test's writes leak into
    another corridor's results regardless of execution order."""
    main.store = Store(data_dir=None)
    yield


def make_board(station_code: str, fetched_at: datetime) -> StationLiveBoard:
    return StationLiveBoard(
        station_code=station_code,
        fetched_at=fetched_at,
        window_hours=4,
        events=[
            TrainEvent(
                train_no="101",
                train_name="TEST TRAIN",
                station_code=station_code,
                event_type=EventType.DEPARTURE,
                status=TrainEventStatus.ON_TIME,
            )
        ],
    )


def test_list_corridors_returns_configured_corridors():
    resp = client.get("/api/v1/corridors")
    assert resp.status_code == 200
    body = resp.json()
    corridor_ids = {c["corridor"] for c in body}
    assert "GHY-LMG" in corridor_ids
    assert "LMG-RNY" in corridor_ids


def test_live_endpoint_unknown_corridor_404s():
    resp = client.get("/api/v1/corridors/NOPE-NOPE/live")
    assert resp.status_code == 404


def test_live_endpoint_fresh_data_not_stale():
    now = datetime.now()
    main.store.set_live_board("GHY", make_board("GHY", now))
    main.store.set_live_board("LMG", make_board("LMG", now))

    resp = client.get("/api/v1/corridors/GHY-LMG/live")
    assert resp.status_code == 200
    body = resp.json()
    assert body["stale"] is False
    assert body["station_a"]["station_code"] == "GHY"
    assert body["station_b"]["station_code"] == "LMG"


def test_live_endpoint_old_data_flagged_stale():
    old = datetime.now() - timedelta(seconds=main.STALE_THRESHOLD_SECONDS + 120)
    main.store.set_live_board("GHY", make_board("GHY", old))
    main.store.set_live_board("LMG", make_board("LMG", old))

    resp = client.get("/api/v1/corridors/GHY-LMG/live")
    assert resp.status_code == 200
    assert resp.json()["stale"] is True


def test_live_endpoint_never_fetched_is_stale_with_null_boards():
    resp = client.get("/api/v1/corridors/LMG-RNY/live")
    assert resp.status_code == 200
    body = resp.json()
    assert body["stale"] is True
    assert body["last_successful_fetch"] is None


def test_predicted_windows_endpoint_returns_cached_predictions_ranked():
    predictions = [
        PredictedWindow(
            corridor="GHY-LMG", window="01:00-05:00", observed_nights=84,
            clear_nights=77, predicted_availability=0.92, last_updated=date.today(),
        ),
        PredictedWindow(
            corridor="GHY-LMG", window="22:00-02:00", observed_nights=84,
            clear_nights=40, predicted_availability=0.48, last_updated=date.today(),
        ),
    ]
    main.store.set_predictions("GHY-LMG", predictions)

    resp = client.get("/api/v1/corridors/GHY-LMG/predicted-windows")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["predicted_availability"] >= body[1]["predicted_availability"]


def test_predicted_windows_unknown_corridor_404s():
    resp = client.get("/api/v1/corridors/NOPE-NOPE/predicted-windows")
    assert resp.status_code == 404


def test_predicted_windows_empty_before_any_data_collected():
    resp = client.get("/api/v1/corridors/LMG-RNY/predicted-windows")
    assert resp.status_code == 200
    assert resp.json() == []


def test_train_paths_pairs_cached_boards():
    now = datetime.now()
    dep = now + timedelta(minutes=10)
    main.store.set_live_board("NDLS", StationLiveBoard(
        station_code="NDLS", fetched_at=now, window_hours=8,
        events=[TrainEvent(train_no="101", train_name="TEST TRAIN", station_code="NDLS",
                           event_type=EventType.DEPARTURE, status=TrainEventStatus.ON_TIME,
                           actual_or_expected_time=dep)],
    ))
    main.store.set_live_board("GZB", StationLiveBoard(
        station_code="GZB", fetched_at=now, window_hours=8,
        events=[TrainEvent(train_no="101", train_name="TEST TRAIN", station_code="GZB",
                           event_type=EventType.ARRIVAL, status=TrainEventStatus.ON_TIME,
                           actual_or_expected_time=dep + timedelta(minutes=40))],
    ))

    resp = client.get("/api/v1/corridors/NDLS-GZB/train-paths")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "mock"
    assert body["window_hours"] == 8
    assert [(p["train_no"], p["direction"]) for p in body["paths"]] == [("101", "a_to_b")]


def test_train_paths_empty_when_a_board_is_missing():
    main.store.set_live_board("LMG", make_board("LMG", datetime.now()))
    body = client.get("/api/v1/corridors/LMG-RNY/train-paths").json()
    assert body["paths"] == []
    assert body["boards_fetched_at"] is None


def test_train_paths_unknown_corridor_404s():
    assert client.get("/api/v1/corridors/NOPE-NOPE/train-paths").status_code == 404
