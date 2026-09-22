"""Data shapes shared across providers, occupancy derivation, frequency
prediction, and the API. See README.md "Investigation findings" for what
in here is confirmed-real vs. best-effort/unverified.
"""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel


class EventType(str, Enum):
    ARRIVAL = "arrival"
    DEPARTURE = "departure"


class TrainEventStatus(str, Enum):
    ON_TIME = "on_time"
    DELAYED = "delayed"
    SOURCE = "source"  # train originates at this station -- no arrival event
    TERMINATING = "terminating"  # train ends at this station -- no departure event
    UNKNOWN = "unknown"  # row didn't match any known format; parsed defensively


class TrainEvent(BaseModel):
    train_no: str
    train_name: str
    station_code: str
    event_type: EventType
    status: TrainEventStatus
    scheduled_time: datetime | None = None
    actual_or_expected_time: datetime | None = None
    delay_minutes: int | None = None
    platform: str | None = None


class StationLiveBoard(BaseModel):
    station_code: str
    fetched_at: datetime
    window_hours: int
    events: list[TrainEvent]


class LiveCorridorStatus(BaseModel):
    corridor: str
    station_a: StationLiveBoard | None
    station_b: StationLiveBoard | None
    stale: bool
    last_successful_fetch: datetime | None


class SectionOccupancyInterval(BaseModel):
    corridor: str
    train_no: str
    occupied_from: datetime
    occupied_to: datetime


class PredictedWindow(BaseModel):
    corridor: str
    window: str
    observed_nights: int
    clear_nights: int
    predicted_availability: float
    last_updated: date
