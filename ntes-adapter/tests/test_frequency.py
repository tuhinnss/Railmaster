from datetime import date, datetime

from app.frequency import compute_predicted_window, compute_predicted_windows
from app.models import SectionOccupancyInterval


def occupancy(night: date, hour: int, minute: int, duration_minutes: int = 30) -> SectionOccupancyInterval:
    start = datetime(night.year, night.month, night.day, hour, minute)
    from datetime import timedelta

    return SectionOccupancyInterval(
        corridor="GHY-LMG", train_no="101", occupied_from=start, occupied_to=start + timedelta(minutes=duration_minutes)
    )


def test_predicted_availability_is_clear_over_observed():
    today = date(2026, 9, 22)
    nights = [date(2026, 9, 21), date(2026, 9, 20), date(2026, 9, 19), date(2026, 9, 18)]

    # Two nights with a train inside the window (occupied), two clear.
    intervals = [
        occupancy(date(2026, 9, 21), 2, 0),
        occupancy(date(2026, 9, 20), 3, 0),
    ]
    # Poll coverage for all 4 nights, inside the window each time.
    poll_timestamps = [datetime(n.year, n.month, n.day, 2, 30) for n in nights]

    result = compute_predicted_window("GHY-LMG", "01:00-05:00", intervals, poll_timestamps, nights, today)

    assert result.observed_nights == 4
    assert result.clear_nights == 2
    assert result.predicted_availability == 0.5


def test_nights_without_poll_coverage_are_not_counted_as_observed():
    """A night nobody polled must not be silently counted as 'clear' just
    because there's no occupancy record for it -- those are different
    things (see frequency.py docstring)."""
    today = date(2026, 9, 22)
    nights = [date(2026, 9, 21), date(2026, 9, 20)]
    intervals: list[SectionOccupancyInterval] = []  # no occupancy recorded at all
    poll_timestamps = [datetime(2026, 9, 21, 2, 30)]  # only one of the two nights was actually polled

    result = compute_predicted_window("GHY-LMG", "01:00-05:00", intervals, poll_timestamps, nights, today)

    assert result.observed_nights == 1
    assert result.clear_nights == 1
    assert result.predicted_availability == 1.0


def test_zero_observed_nights_gives_zero_availability_not_a_crash():
    result = compute_predicted_window("GHY-LMG", "01:00-05:00", [], [], [date(2026, 9, 21)], date(2026, 9, 22))
    assert result.observed_nights == 0
    assert result.clear_nights == 0
    assert result.predicted_availability == 0.0


def test_window_crossing_midnight_is_handled():
    today = date(2026, 9, 22)
    nights = [date(2026, 9, 21)]
    # Occupancy just after midnight, inside a 22:00-02:00 window.
    interval = SectionOccupancyInterval(
        corridor="GHY-LMG",
        train_no="1",
        occupied_from=datetime(2026, 9, 22, 0, 30),
        occupied_to=datetime(2026, 9, 22, 1, 0),
    )
    poll_timestamps = [datetime(2026, 9, 22, 0, 0)]  # inside the 22:00-02:00 window (next-day 00:00)

    result = compute_predicted_window("GHY-LMG", "22:00-02:00", [interval], poll_timestamps, nights, today)
    assert result.observed_nights == 1
    assert result.clear_nights == 0  # the occupancy overlaps the window


def test_compute_predicted_windows_ranks_by_availability_descending():
    today = date(2026, 9, 22)
    nights = [date(2026, 9, 21), date(2026, 9, 20)]
    # Window A: always clear. Window B: always occupied.
    poll_timestamps_a = [datetime(n.year, n.month, n.day, 1, 30) for n in nights]
    poll_timestamps_b = [datetime(n.year, n.month, n.day, 22, 30) for n in nights]
    intervals = [occupancy(n, 22, 0) for n in nights]  # occupies the 22:00-23:xx window only

    results = compute_predicted_windows(
        "GHY-LMG",
        ["01:00-05:00", "22:00-23:00"],
        intervals,
        poll_timestamps_a + poll_timestamps_b,
        lookback_nights=2,
        today=today,
    )
    assert results[0].window == "01:00-05:00"
    assert results[0].predicted_availability >= results[1].predicted_availability
