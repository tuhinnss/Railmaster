"""Corridor block availability, derived from COA (train timetable gaps +
goods forecast)."""

from datetime import date, time
from pydantic import BaseModel


class BlockWindow(BaseModel):
    """A single available maintenance window on a corridor for a given day."""

    corridor_id: str
    section: str
    date: date
    start_time: time
    end_time: time


class TrainTimetableEntry(BaseModel):
    train_no: str
    section: str
    scheduled_departure: time
    scheduled_arrival: time
    priority: str  # e.g. "SUPERFAST" | "MAIL" | "PASSENGER" | "GOODS"


class GoodsForecast(BaseModel):
    section: str
    date: date
    expected_goods_volume: float
