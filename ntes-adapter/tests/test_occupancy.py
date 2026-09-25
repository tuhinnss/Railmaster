from datetime import datetime

from app.models import EventType, StationLiveBoard, TrainEvent, TrainEventStatus
from app.occupancy import derive_corridor_occupancy, is_window_clear, pair_section_occupancy


def make_event(train_no, station_code, event_type, actual_time, **overrides):
    defaults = dict(
        train_no=train_no,
        train_name=f"TRAIN {train_no}",
        station_code=station_code,
        event_type=event_type,
        status=TrainEventStatus.ON_TIME,
        scheduled_time=actual_time,
        actual_or_expected_time=actual_time,
        delay_minutes=0,
    )
    defaults.update(overrides)
    return TrainEvent(**defaults)


def test_pairs_departure_with_matching_arrival_by_train_number():
    dep = make_event("101", "GHY", EventType.DEPARTURE, datetime(2026, 9, 22, 23, 0))
    arr = make_event("101", "LMG", EventType.ARRIVAL, datetime(2026, 9, 23, 1, 0))
    intervals = pair_section_occupancy("GHY-LMG", [dep], [arr])
    assert len(intervals) == 1
    assert intervals[0].train_no == "101"
    assert intervals[0].occupied_from == datetime(2026, 9, 22, 23, 0)
    assert intervals[0].occupied_to == datetime(2026, 9, 23, 1, 0)


def test_pairing_across_midnight_crossing():
    """A train departing station A late at night and arriving at station B
    after 00:00 the next calendar day must still pair correctly -- this is
    exactly the case a weekly maintenance-block scheduler cares about."""
    dep = make_event("202", "GHY", EventType.DEPARTURE, datetime(2026, 9, 22, 23, 50))
    arr = make_event("202", "LMG", EventType.ARRIVAL, datetime(2026, 9, 23, 0, 35))
    intervals = pair_section_occupancy("GHY-LMG", [dep], [arr])
    assert len(intervals) == 1
    interval = intervals[0]
    assert interval.occupied_from.date() == datetime(2026, 9, 22).date()
    assert interval.occupied_to.date() == datetime(2026, 9, 23).date()
    assert interval.occupied_to > interval.occupied_from


def test_does_not_pair_unrelated_train_numbers():
    dep = make_event("101", "GHY", EventType.DEPARTURE, datetime(2026, 9, 22, 23, 0))
    arr = make_event("999", "LMG", EventType.ARRIVAL, datetime(2026, 9, 23, 1, 0))
    intervals = pair_section_occupancy("GHY-LMG", [dep], [arr])
    assert intervals == []


def test_rejects_pairing_beyond_max_transit_minutes():
    dep = make_event("101", "GHY", EventType.DEPARTURE, datetime(2026, 9, 22, 23, 0))
    arr = make_event("101", "LMG", EventType.ARRIVAL, datetime(2026, 9, 23, 12, 0))  # 13h later
    intervals = pair_section_occupancy("GHY-LMG", [dep], [arr], max_transit_minutes=240)
    assert intervals == []


def test_picks_earliest_qualifying_arrival_when_multiple_candidates():
    """Same train number could plausibly appear twice (different service
    dates); the earliest valid arrival after departure should win."""
    dep = make_event("101", "GHY", EventType.DEPARTURE, datetime(2026, 9, 22, 23, 0))
    early_arr = make_event("101", "LMG", EventType.ARRIVAL, datetime(2026, 9, 23, 1, 0))
    late_arr = make_event("101", "LMG", EventType.ARRIVAL, datetime(2026, 9, 23, 2, 30))
    intervals = pair_section_occupancy("GHY-LMG", [dep], [late_arr, early_arr])
    assert len(intervals) == 1
    assert intervals[0].occupied_to == datetime(2026, 9, 23, 1, 0)


def test_source_and_terminating_events_have_no_time_and_are_ignored():
    source_event = TrainEvent(
        train_no="303",
        train_name="ORIGIN TRAIN",
        station_code="GHY",
        event_type=EventType.DEPARTURE,
        status=TrainEventStatus.SOURCE,
    )
    arr = make_event("303", "LMG", EventType.ARRIVAL, datetime(2026, 9, 23, 1, 0))
    intervals = pair_section_occupancy("GHY-LMG", [source_event], [arr])
    assert intervals == []


def test_derive_corridor_occupancy_covers_both_directions():
    board_a = StationLiveBoard(
        station_code="GHY",
        fetched_at=datetime(2026, 9, 22, 22, 0),
        window_hours=4,
        events=[
            make_event("101", "GHY", EventType.DEPARTURE, datetime(2026, 9, 22, 23, 0)),
            make_event("202", "GHY", EventType.ARRIVAL, datetime(2026, 9, 22, 22, 30)),
        ],
    )
    board_b = StationLiveBoard(
        station_code="LMG",
        fetched_at=datetime(2026, 9, 22, 22, 0),
        window_hours=4,
        events=[
            make_event("101", "LMG", EventType.ARRIVAL, datetime(2026, 9, 23, 1, 0)),
            make_event("202", "LMG", EventType.DEPARTURE, datetime(2026, 9, 22, 20, 30)),
        ],
    )
    intervals = derive_corridor_occupancy("GHY-LMG", board_a, board_b)
    train_nos = {iv.train_no for iv in intervals}
    assert train_nos == {"101", "202"}


def test_is_window_clear_true_when_no_overlap():
    intervals = [pair_section_occupancy(
        "GHY-LMG",
        [make_event("101", "GHY", EventType.DEPARTURE, datetime(2026, 9, 22, 20, 0))],
        [make_event("101", "LMG", EventType.ARRIVAL, datetime(2026, 9, 22, 21, 0))],
    )[0]]
    assert is_window_clear(datetime(2026, 9, 23, 1, 0), datetime(2026, 9, 23, 5, 0), intervals)


def test_is_window_clear_false_when_overlapping():
    intervals = pair_section_occupancy(
        "GHY-LMG",
        [make_event("101", "GHY", EventType.DEPARTURE, datetime(2026, 9, 22, 23, 0))],
        [make_event("101", "LMG", EventType.ARRIVAL, datetime(2026, 9, 23, 2, 0))],
    )
    assert not is_window_clear(datetime(2026, 9, 23, 1, 0), datetime(2026, 9, 23, 5, 0), intervals)


def test_short_corridor_yields_real_occupancy_from_a_single_capture():
    """Both captured boards of a ~25 km section contain the same trains, because
    a 30-50 minute transit fits inside one 8-hour capture window. So occupancy
    pairing produces real intervals here -- unlike GHY-LMG (180 km against a
    4-hour window), where the two boards share no trains at all. See README's
    known-limitations entry: the limitation is window-vs-transit, not a property
    of point-in-time captures in general.
    """
    from datetime import datetime

    from app.occupancy import derive_corridor_occupancy
    from app.providers.fixture_provider import CapturedFixtureProvider

    provider = CapturedFixtureProvider()
    intervals = derive_corridor_occupancy(
        "NDLS-GZB", provider.get_live_station("NDLS"), provider.get_live_station("GZB")
    )

    assert len(intervals) >= 5, "expected several paired transits on a short, busy section"
    for interval in intervals:
        transit = (interval.occupied_to - interval.occupied_from).total_seconds() / 60
        assert 0 <= transit <= 120, f"{interval.train_no} transit {transit} min is implausible for 25 km"
    assert isinstance(intervals[0].occupied_from, datetime)


def test_long_corridor_yields_no_occupancy_from_a_single_capture():
    """The counterpart: GHY-LMG's boards share no train numbers, so pairing
    correctly yields nothing rather than inventing transits."""
    from app.occupancy import derive_corridor_occupancy
    from app.providers.fixture_provider import CapturedFixtureProvider

    provider = CapturedFixtureProvider()
    intervals = derive_corridor_occupancy(
        "GHY-LMG", provider.get_live_station("GHY"), provider.get_live_station("LMG")
    )

    assert intervals == []


def test_train_paths_keep_direction_and_name():
    from app.occupancy import derive_train_paths

    board_a = StationLiveBoard(
        station_code="NDLS", fetched_at=datetime(2026, 9, 22, 23, 0), window_hours=8,
        events=[
            make_event("101", "NDLS", EventType.DEPARTURE, datetime(2026, 9, 23, 0, 10)),
            make_event("202", "NDLS", EventType.ARRIVAL, datetime(2026, 9, 23, 1, 40)),
        ],
    )
    board_b = StationLiveBoard(
        station_code="GZB", fetched_at=datetime(2026, 9, 22, 23, 0), window_hours=8,
        events=[
            make_event("101", "GZB", EventType.ARRIVAL, datetime(2026, 9, 23, 0, 50)),
            make_event("202", "GZB", EventType.DEPARTURE, datetime(2026, 9, 23, 1, 0)),
        ],
    )
    paths = derive_train_paths("NDLS-GZB", board_a, board_b)

    assert [(p.train_no, p.direction.value) for p in paths] == [("101", "a_to_b"), ("202", "b_to_a")]
    assert paths[0].train_name == "TRAIN 101"
    assert paths[1].departed_at == datetime(2026, 9, 23, 1, 0)
    assert paths[1].arrived_at == datetime(2026, 9, 23, 1, 40)


def test_train_paths_match_occupancy_on_the_real_capture():
    """Paths are the occupancy intervals plus direction -- never more, never
    fewer -- so the chart can't show a movement the occupancy log doesn't count."""
    from app.occupancy import derive_train_paths
    from app.providers.fixture_provider import CapturedFixtureProvider

    provider = CapturedFixtureProvider()
    ndls, gzb = provider.get_live_station("NDLS"), provider.get_live_station("GZB")
    paths = derive_train_paths("NDLS-GZB", ndls, gzb)
    intervals = derive_corridor_occupancy("NDLS-GZB", ndls, gzb)

    assert sorted((p.train_no, p.departed_at, p.arrived_at) for p in paths) == sorted(
        (iv.train_no, iv.occupied_from, iv.occupied_to) for iv in intervals
    )
    assert all(p.train_name for p in paths)
