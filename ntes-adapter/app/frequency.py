"""Historical frequency prediction (spec point 3): a plain frequency
count over self-collected data -- predicted_availability = clear_nights
/ observed_nights -- computed offline/on a schedule, never live during a
request. This is a frequency count, not a trained model; don't present
it as one.

"observed_nights" specifically means nights where the poller actually
had live coverage during that window (at least one successful poll
timestamp falling inside it) -- not just any night with no recorded
occupancy. Those are different: a night nobody polled looks identical to
a genuinely clear night if you only look at the occupancy log, so
frequency prediction needs the poll-coverage log too, not occupancy
alone. NTES exposes no historical archive (see README) -- these nights
can only be nights the poller was actually running and reachable, never
backfilled.
"""

from datetime import date, datetime, time, timedelta

from app.models import PredictedWindow, SectionOccupancyInterval
from app.occupancy import is_window_clear


def parse_window(window: str) -> tuple[time, time]:
    start_str, end_str = window.split("-")
    start_h, start_m = (int(x) for x in start_str.split(":"))
    end_h, end_m = (int(x) for x in end_str.split(":"))
    return time(start_h, start_m), time(end_h, end_m)


def window_datetimes(night: date, window_start: time, window_end: time) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(night, window_start)
    end_dt = datetime.combine(night, window_end)
    if window_end <= window_start:
        end_dt += timedelta(days=1)  # window crosses midnight
    return start_dt, end_dt


def compute_predicted_window(
    corridor: str,
    window: str,
    intervals: list[SectionOccupancyInterval],
    poll_timestamps: list[datetime],
    nights: list[date],
    today: date,
) -> PredictedWindow:
    window_start, window_end = parse_window(window)

    observed_nights = 0
    clear_nights = 0
    for night in nights:
        start_dt, end_dt = window_datetimes(night, window_start, window_end)
        had_coverage = any(start_dt <= ts <= end_dt for ts in poll_timestamps)
        if not had_coverage:
            continue
        observed_nights += 1
        if is_window_clear(start_dt, end_dt, intervals):
            clear_nights += 1

    predicted_availability = round(clear_nights / observed_nights, 4) if observed_nights else 0.0

    return PredictedWindow(
        corridor=corridor,
        window=window,
        observed_nights=observed_nights,
        clear_nights=clear_nights,
        predicted_availability=predicted_availability,
        last_updated=today,
    )


def compute_predicted_windows(
    corridor: str,
    windows: list[str],
    intervals: list[SectionOccupancyInterval],
    poll_timestamps: list[datetime],
    lookback_nights: int,
    today: date,
) -> list[PredictedWindow]:
    nights = [today - timedelta(days=i) for i in range(1, lookback_nights + 1)]
    results = [
        compute_predicted_window(corridor, w, intervals, poll_timestamps, nights, today) for w in windows
    ]
    return sorted(results, key=lambda p: p.predicted_availability, reverse=True)
