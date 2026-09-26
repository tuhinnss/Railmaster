"""Wire shapes for the two dashboards that write data: Report Defect (field
staff) and Control Office (block decisions). See app/operations.py."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import BlockType, Department, SeverityCode


class DefectReportRequest(BaseModel):
    section: str
    department: Department
    defect_type: str
    km_from: float
    km_to: float
    severity_code: SeverityCode
    est_duration_min: int = Field(gt=0, le=720)
    block_type_required: BlockType
    description: str = Field(default="", max_length=500)
    reported_by: str = Field(default="", max_length=80)


class DefectReport(DefectReportRequest):
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
