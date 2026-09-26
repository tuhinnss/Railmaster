"""Checks a block's time against the booked passenger timetable -- the
"Trains between stations" data ntes-adapter fetches from NTES -- and
suggests quieter times. Used when the control office moves a block.

This warns; it never blocks a decision. In practice trains are held or
regulated around a block, so a clash is a cost to weigh, not a
prohibition. Everything here is an estimate, and the page says so:

- Only passenger trains. Goods trains are in no public timetable, so "no
  trains" means no *passenger* trains booked, not an empty line.
- Only trains NTES shows running from one end of the section to the other.
  A query from NDLS also lists trains from other Delhi terminals (DLI,
  ANVT, NZM ...) that reach GZB partly by other routes; they are left out
  and reported as not_counted.
- Where a train is between the ends is interpolated at a steady speed
  along the section's km range. NTES gives times only at the two ends,
  and the km figures are illustrative (datagen/reference_data.py), so a
  passing time is approximate.
- A train's running days are read as the days it leaves the first
  station. NTES doesn't say whether they count from there or from the
  train's origin -- unconfirmed, see the adapter README.
- Both directions count: which line of a double track a block closes
  isn't modelled.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.datagen.reference_data import SECTIONS

_SECTION_KM = {name: (km_start, km_end) for name, km_start, km_end in SECTIONS}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
# Fine enough to find a gap between two trains a few minutes apart; 15 missed
# a real 90-minute night gap on GHY-LMG (between 01:37 and 03:14 at km 20).
SLOT_STEP_MIN = 5


@dataclass(frozen=True)
class TrainPass:
    train_no: str
    train_name: str
    train_type: str
    direction: str  # "GHY → LMG"
    passes_from: datetime  # estimated time at the near end of the km range
    passes_to: datetime  # ... and at the far end


def _minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def _end_to_end(timetable: dict, section: str) -> tuple[list[tuple[dict, str, str]], int]:
    """(trains running the whole section with their direction, how many
    listed trains were left out because they start or end elsewhere)."""
    a, b = section.split("-")
    kept, left_out = [], 0
    for key, origin, dest in (("a_to_b", a, b), ("b_to_a", b, a)):
        for train in timetable[key]:
            if train["from_station"] == origin and train["to_station"] == dest:
                kept.append((train, origin, dest))
            else:
                left_out += 1
    return kept, left_out


def not_counted(timetable: dict, section: str) -> int:
    """How many listed trains start or end at a neighbouring station and
    are left out (e.g. other Delhi terminals on NDLS-GZB)."""
    return _end_to_end(timetable, section)[1]


def trains_through(
    timetable: dict, section: str, km_from: float, km_to: float, start: datetime, end: datetime
) -> tuple[list[TrainPass], int]:
    """Passenger trains booked over km_from-km_to between start and end,
    earliest first, and the count of listed trains not considered."""
    km_start, km_end = _SECTION_KM[section]
    length = km_end - km_start
    a = section.split("-")[0]
    kept, left_out = _end_to_end(timetable, section)

    passes: list[TrainPass] = []
    for train, origin, dest in kept:
        dep = _minutes(train["departs"])
        run = (_minutes(train["arrives"]) - dep) % 1440  # arriving "earlier" means the next day
        # How far along its own journey the train reaches each end of the range.
        if origin == a:
            near, far = (km_from - km_start) / length, (km_to - km_start) / length
        else:
            near, far = (km_end - km_to) / length, (km_end - km_from) / length
        # A train still on the section at `start` may have left a day or two earlier.
        day = start.date() - timedelta(days=2)
        while day <= end.date():
            if WEEKDAYS[day.weekday()] in train["running_days"]:
                departed = datetime.combine(day, time()) + timedelta(minutes=dep)
                p_from = departed + timedelta(minutes=run * near)
                p_to = departed + timedelta(minutes=run * far)
                if p_from < end and p_to > start:
                    passes.append(
                        TrainPass(
                            train_no=train["train_no"],
                            train_name=train["train_name"],
                            train_type=train["train_type"],
                            direction=f"{origin} → {dest}",
                            passes_from=p_from,
                            passes_to=p_to,
                        )
                    )
            day += timedelta(days=1)
    passes.sort(key=lambda p: p.passes_from)
    return passes, left_out


@dataclass(frozen=True)
class QuietSlot:
    start: datetime
    end: datetime
    trains: list[TrainPass]


def quiet_slots(
    timetable: dict,
    section: str,
    km_from: float,
    km_to: float,
    day: date,
    duration_min: int,
    around: datetime | None = None,
    count: int = 3,
) -> list[QuietSlot]:
    """The `count` start times on `day` (every SLOT_STEP_MIN minutes) whose window
    crosses the fewest booked trains, not overlapping one another. Among
    equally quiet times, the one nearest `around` (the block's current
    start) wins, so a suggestion moves the block as little as it can."""
    length = timedelta(minutes=duration_min)
    candidates = []
    for i in range(24 * 60 // SLOT_STEP_MIN):
        start = datetime.combine(day, time()) + timedelta(minutes=i * SLOT_STEP_MIN)
        trains, _ = trains_through(timetable, section, km_from, km_to, start, start + length)
        distance = abs((start - around).total_seconds()) if around else i
        candidates.append((len(trains), distance, start, trains))
    candidates.sort(key=lambda c: (c[0], c[1]))

    chosen: list[QuietSlot] = []
    for _, _, start, trains in candidates:
        if all(start + length <= s.start or start >= s.end for s in chosen):
            chosen.append(QuietSlot(start=start, end=start + length, trains=trains))
            if len(chosen) == count:
                break
    return chosen
