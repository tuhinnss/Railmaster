"""Output of the scheduling engine: a set of maintenance tasks assigned to
corridor block windows over a given horizon."""

from datetime import date, time
from pydantic import BaseModel

from app.models.enums import Horizon


class ScheduledBlock(BaseModel):
    task_id: str
    corridor_id: str
    section: str
    date: date
    start_time: time
    end_time: time
    priority_score: float


class BlockPlan(BaseModel):
    id: str
    horizon: Horizon
    start_date: date
    end_date: date
    entries: list[ScheduledBlock] = []
