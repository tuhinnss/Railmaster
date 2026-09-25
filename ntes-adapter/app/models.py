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
    # Which provider produced these boards: "mock" (canned), "captured_fixture"
    # (real NTES responses captured during investigation, replayed against
    # today's date), or "ntes_live" (fetched from NTES now). Consumers must
    # not present canned data as real -- see README.
    provider: str = "unknown"


class SectionOccupancyInterval(BaseModel):
    corridor: str
    train_no: str
    occupied_from: datetime
    occupied_to: datetime


class PathDirection(str, Enum):
    A_TO_B = "a_to_b"
    B_TO_A = "b_to_a"


class TrainPath(BaseModel):
    """One paired section traversal: the same interval as
    SectionOccupancyInterval, plus which way the train went and its name.
    Only the two endpoints are observed; anything drawn between them is
    interpolation, not a measured position."""

    corridor: str
    train_no: str
    train_name: str
    direction: PathDirection
    departed_at: datetime
    arrived_at: datetime


class CorridorTrainPaths(BaseModel):
    corridor: str
    station_a: str
    station_b: str
    paths: list[TrainPath]
    # The older of the two boards' fetch times, and the window each covers.
    # None when either board is missing -- pairing needs both ends.
    boards_fetched_at: datetime | None
    window_hours: int | None
    stale: bool
    provider: str = "unknown"


class PredictedWindow(BaseModel):
    corridor: str
    window: str
    observed_nights: int
    clear_nights: int
    predicted_availability: float
    last_updated: date
