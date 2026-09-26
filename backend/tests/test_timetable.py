from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app.api import routes_corridors
from app.main import app
from app.timetable import not_counted, quiet_slots, trains_through

DAILY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def train(no, from_station, departs, to_station, arrives, days=DAILY):
    return {
        "train_no": no,
        "train_name": f"TRAIN {no}",
        "train_type": "Mail Express",
        "running_days": days,
        "from_station": from_station,
        "departs": departs,
        "to_station": to_station,
        "arrives": arrives,
    }


# GHY-LMG runs km 0-180. Worked out by hand:
# - 101 leaves GHY 01:00, reaches LMG 04:00: 1 km/min, so km 90 at 02:30.
# - 202 leaves LMG 23:00 on Fridays only, reaches GHY 02:00: km 90 at 00:30
#   the next morning, km 10 at 01:50.
# - 303 starts at a neighbouring station, so it isn't counted.
TIMETABLE = {
    "fetched_at": "2026-09-26T13:11:00",
    "provider": "captured_fixture",
    "a_to_b": [train("101", "GHY", "01:00", "LMG", "04:00"), train("303", "KYQ", "01:30", "LMG", "04:30")],
    "b_to_a": [train("202", "LMG", "23:00", "GHY", "02:00", days=["Fri"])],
}
TUE, SAT, SUN = date(2026, 9, 29), date(2026, 10, 3), date(2026, 10, 4)


def at(day, hh, mm=0):
    return datetime(day.year, day.month, day.day, hh, mm)


def test_a_train_is_placed_at_a_steady_speed_along_the_section():
    passes, left_out = trains_through(TIMETABLE, "GHY-LMG", 90.0, 91.0, at(TUE, 2), at(TUE, 3))
    assert [(p.train_no, p.direction, p.passes_from, p.passes_to) for p in passes] == [
        ("101", "GHY → LMG", at(TUE, 2, 30), at(TUE, 2, 31))
    ]
    assert left_out == 1


def test_a_train_in_the_other_direction_reaches_low_km_last():
    passes, _ = trains_through(TIMETABLE, "GHY-LMG", 9.0, 10.0, at(SAT, 1, 45), at(SAT, 2))
    assert [(p.train_no, p.passes_from, p.passes_to) for p in passes] == [("202", at(SAT, 1, 50), at(SAT, 1, 51))]


def test_running_days_count_from_the_day_the_train_leaves():
    # 202 leaves on Friday night, so it crosses km 90 early on Saturday...
    saturday, _ = trains_through(TIMETABLE, "GHY-LMG", 90.0, 91.0, at(SAT, 0), at(SAT, 1))
    assert [p.train_no for p in saturday] == ["202"]
    # ...and not on Sunday morning, since it doesn't leave on Saturdays.
    sunday, _ = trains_through(TIMETABLE, "GHY-LMG", 90.0, 91.0, at(SUN, 0), at(SUN, 1))
    assert sunday == []


def test_a_window_clear_of_every_pass_finds_nothing():
    passes, _ = trains_through(TIMETABLE, "GHY-LMG", 90.0, 91.0, at(TUE, 3), at(TUE, 6))
    assert passes == []


def test_quiet_slots_avoid_trains_stay_near_the_current_time_and_dont_overlap():
    slots = quiet_slots(TIMETABLE, "GHY-LMG", 90.0, 91.0, TUE, 120, around=at(TUE, 2))
    assert len(slots) == 3
    assert all(s.trains == [] for s in slots)
    # 101 passes 02:30-02:31, so a clear two-hour slot must end by 02:30 or
    # start after 02:31; the nearest such start to 02:00, in 5-minute steps,
    # is 02:35 (35 minutes away, against 00:30's 90).
    assert slots[0].start == at(TUE, 2, 35)
    for a in slots:
        for b in slots:
            assert a is b or a.end <= b.start or b.end <= a.start
    assert not_counted(TIMETABLE, "GHY-LMG") == 1


# --- API ---------------------------------------------------------------------

client = TestClient(app)


@pytest.fixture
def adapter_has(monkeypatch):
    def install(timetable):
        monkeypatch.setattr(routes_corridors, "fetch_timetable", lambda section: timetable)

    return install


def test_check_endpoint_lists_the_trains_and_where_the_timetable_came_from(adapter_has):
    adapter_has(TIMETABLE)
    body = client.get(
        "/api/corridors/GHY-LMG/timetable-check",
        params={"km_from": 90, "km_to": 91, "start": "2026-09-29T02:00:00", "duration_min": 60},
    ).json()
    assert body["available"] is True
    assert body["provider"] == "captured_fixture"
    assert [t["train_no"] for t in body["trains"]] == ["101"]
    assert body["not_counted"] == 1


def test_without_a_timetable_the_answer_is_not_checked_rather_than_clear(adapter_has):
    adapter_has(None)
    body = client.get(
        "/api/corridors/GHY-LMG/timetable-check",
        params={"km_from": 90, "km_to": 91, "start": "2026-09-29T02:00:00", "duration_min": 60},
    ).json()
    assert body["available"] is False
    assert "not checked" in body["reason"]
    assert body["trains"] == []


def test_quiet_slots_endpoint(adapter_has):
    adapter_has(TIMETABLE)
    body = client.get(
        "/api/corridors/GHY-LMG/quiet-slots",
        params={"km_from": 90, "km_to": 91, "day": "2026-09-29", "duration_min": 120, "around": "2026-09-29T02:00:00"},
    ).json()
    assert body["available"] is True
    assert len(body["slots"]) == 3
    assert all(s["trains"] == [] for s in body["slots"])


def test_check_endpoint_rejects_a_range_outside_the_section(adapter_has):
    adapter_has(TIMETABLE)
    response = client.get(
        "/api/corridors/GHY-LMG/timetable-check",
        params={"km_from": 170, "km_to": 190, "start": "2026-09-29T02:00:00", "duration_min": 60},
    )
    assert response.status_code == 422
