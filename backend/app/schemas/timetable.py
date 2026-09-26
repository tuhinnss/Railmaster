"""Wire shapes for checking a block's time against the booked timetable
(app/timetable.py). `available` is false whenever there is no timetable to
check against, with the reason -- the page must then say "not checked",
never "no trains"."""

from datetime import datetime

from pydantic import BaseModel


class TrainPassSummary(BaseModel):
    train_no: str
    train_name: str
    train_type: str
    direction: str
    passes_from: datetime  # estimated
    passes_to: datetime


class TimetableSource(BaseModel):
    section: str
    available: bool
    reason: str | None = None
    fetched_at: datetime | None = None  # when the timetable was obtained from NTES
    provider: str | None = None  # "ntes_live" or "captured_fixture"
    # Trains NTES listed that start or end at a neighbouring station, and
    # so weren't counted (e.g. other Delhi terminals on NDLS-GZB).
    not_counted: int = 0


class TimetableCheck(TimetableSource):
    trains: list[TrainPassSummary] = []


class QuietSlotSummary(BaseModel):
    start: datetime
    end: datetime
    trains: list[TrainPassSummary]


class QuietSlots(TimetableSource):
    slots: list[QuietSlotSummary] = []
