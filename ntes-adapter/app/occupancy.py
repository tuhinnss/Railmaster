"""Section occupancy derivation: pairs a train's actual departure from
station A with its actual arrival at station B (and vice versa) to
compute when the SECTION between them -- not just either station -- was
occupied. Station-level data alone doesn't answer "was this block clear
between 01:00 and 05:00"; this pairing step is the actual point of this
service.
"""

from datetime import datetime, timedelta

from app.config import MAX_SECTION_TRANSIT_MINUTES
from app.models import EventType, SectionOccupancyInterval, StationLiveBoard, TrainEvent


def pair_section_occupancy(
    corridor: str,
    departures_from_a: list[TrainEvent],
    arrivals_at_b: list[TrainEvent],
    max_transit_minutes: int = MAX_SECTION_TRANSIT_MINUTES,
) -> list[SectionOccupancyInterval]:
    """Match each departure from A with the earliest qualifying arrival at
    B for the same train number. Both timestamps are full datetimes (not
    bare times of day), so a departure just before midnight paired with an
    arrival just after falls out correctly with no special-casing -- the
    arrival's date is simply the next calendar day. max_transit_minutes
    guards against pairing a departure with an unrelated later arrival of
    a train that only runs this route occasionally.
    """
    arrivals_by_train: dict[str, list[TrainEvent]] = {}
    for ev in arrivals_at_b:
        if ev.event_type != EventType.ARRIVAL or ev.actual_or_expected_time is None:
            continue
        arrivals_by_train.setdefault(ev.train_no, []).append(ev)
    for events in arrivals_by_train.values():
        events.sort(key=lambda e: e.actual_or_expected_time)

    intervals: list[SectionOccupancyInterval] = []
    for dep in departures_from_a:
        if dep.event_type != EventType.DEPARTURE or dep.actual_or_expected_time is None:
            continue
        match = None
        for arr in arrivals_by_train.get(dep.train_no, []):
            gap = arr.actual_or_expected_time - dep.actual_or_expected_time
            if timedelta(0) <= gap <= timedelta(minutes=max_transit_minutes):
                match = arr
                break
        if match is not None:
            intervals.append(
                SectionOccupancyInterval(
                    corridor=corridor,
                    train_no=dep.train_no,
                    occupied_from=dep.actual_or_expected_time,
                    occupied_to=match.actual_or_expected_time,
                )
            )

    return intervals


def derive_corridor_occupancy(
    corridor: str,
    board_a: StationLiveBoard,
    board_b: StationLiveBoard,
    max_transit_minutes: int = MAX_SECTION_TRANSIT_MINUTES,
) -> list[SectionOccupancyInterval]:
    """Both directions of travel: A->B and B->A."""
    a_departures = [e for e in board_a.events if e.event_type == EventType.DEPARTURE]
    b_arrivals = [e for e in board_b.events if e.event_type == EventType.ARRIVAL]
    b_departures = [e for e in board_b.events if e.event_type == EventType.DEPARTURE]
    a_arrivals = [e for e in board_a.events if e.event_type == EventType.ARRIVAL]

    return pair_section_occupancy(
        corridor, a_departures, b_arrivals, max_transit_minutes
    ) + pair_section_occupancy(corridor, b_departures, a_arrivals, max_transit_minutes)


def is_window_clear(
    window_start: datetime, window_end: datetime, intervals: list[SectionOccupancyInterval]
) -> bool:
    """A window is clear only if no occupancy interval overlaps it at all."""
    return not any(iv.occupied_from < window_end and window_start < iv.occupied_to for iv in intervals)
