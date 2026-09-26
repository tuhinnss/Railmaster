"""Wire shapes for the two dashboards that write data: Report Defect (field
staff) and the control office (block decisions, and blocks added for work
that didn't fit). See app/operations.py."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import BlockType, Department, SeverityCode


class DefectReportRequest(BaseModel):
    section: str
    department: Department
    # In the reporter's own words. Only ever shown, never used to plan, so
    # it isn't held to the generator's list of defect types.
    defect_type: str = Field(max_length=80)
    km_from: float
    km_to: float
    # 1 (minor) to 10 (safety-critical). The planner works with the A/B/C
    # band it falls in -- see operations.severity_from_score.
    severity_score: int = Field(ge=1, le=10)
    est_duration_min: int = Field(gt=0, le=720)
    block_type_required: BlockType
    description: str = Field(default="", max_length=500)
    reported_by: str = Field(default="", max_length=80)


class DefectReport(DefectReportRequest):
    # None on reports saved before scores existed, which picked A/B/C directly.
    severity_score: int | None = Field(default=None, ge=1, le=10)
    severity_code: SeverityCode
    report_id: str  # also the task_id it is planned under
    reported_at: datetime


Decision = Literal["granted", "granted_late", "rescheduled", "cancelled"]


class BlockDecisionRequest(BaseModel):
    decision: Decision
    minutes_lost: int = Field(default=0, ge=0)  # only meaningful for granted_late
    # Only meaningful for rescheduled: when the block now starts, and its
    # length (the planned length when left out).
    new_start: datetime | None = None
    duration_min: int | None = Field(default=None, gt=0, le=720)


class BlockDecision(BaseModel):
    block_id: str
    section: str
    # The block as planned, before this decision -- a cancelled block drops
    # out of the plan, so the Control page needs these to still show it.
    planned_start: datetime
    planned_end: datetime
    decision: Decision
    minutes_lost: int
    decided_at: datetime
    new_start: datetime | None = None  # set only when rescheduled
    new_end: datetime | None = None


class AddBlockRequest(BaseModel):
    task_id: str  # the work that didn't fit, which the block is for
    start: datetime
    duration_min: int = Field(gt=0, le=720)


class AddedBlock(BaseModel):
    block_id: str
    section: str
    start_time: datetime
    end_time: datetime
    duration_min: int
    block_type_possible: BlockType  # the type the work needs
    # Why it was added. The planner may put other work that fits in it too,
    # or, if the plan changes, none at all.
    for_task: str
    added_at: datetime
