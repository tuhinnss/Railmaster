"""Rolls scheduled blocks up into weekly/monthly BlockPlan documents."""

from datetime import date

from app.models.block_plan import BlockPlan, ScheduledBlock
from app.models.enums import Horizon


def build_plan(
    entries: list[ScheduledBlock],
    horizon: Horizon,
    start_date: date,
    end_date: date,
) -> BlockPlan:
    raise NotImplementedError
