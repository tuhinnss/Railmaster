"""API response shapes. Separate from the domain models (app/models/) so
the wire format can evolve (e.g. adding dashboard-specific fields)
without touching what the scheduler itself operates on.
"""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.models.enums import BlockType, Department, Horizon, SeverityCode


class TaskSummary(BaseModel):
    task_id: str
    department: Department
    section: str
    km_range: tuple[float, float]
    defect_type: str
    severity_code: SeverityCode
    days_overdue: int
    block_type_required: BlockType
    est_duration_min: int
    priority_score: float
    criticality: float
    urgency: float
    availability_impact: float
    dominant_component: str
    safety_override: bool
    scheduled: bool
    block_id: str | None
    reason: str
    data_source: Literal["synthetic", "reported"] = "synthetic"


class ScheduledBlockSummary(BaseModel):
    block_id: str
    section: str
    start_time: datetime
    end_time: datetime
    block_type_possible: BlockType
    task_ids: list[str]
    data_source: Literal["synthetic", "ntes_live"]
    duration_min: int
    used_min: int  # sum of assigned tasks' est_duration_min


class SafetyCheckSummary(BaseModel):
    rule: str
    label: str
    description: str
    items_checked: int
    violations: int
    method: Literal["inspected", "structural"]


class SectionPlanResult(BaseModel):
    section: str
    km_start: float
    km_end: float
    ntes_integrated: bool
    task_count: int
    scheduled_count: int
    blocks_opened: int
    blocks_used_without_merging: int  # Stage A's block count, for the "blocks saved" comparison
    blocks_saved: int
    tasks: list[TaskSummary]
    blocks: list[ScheduledBlockSummary]
    safety_checks: list[SafetyCheckSummary]
    # Same fingerprint as PlanResponse's, over this section alone, so a
    # single-section printout identifies exactly what it shows.
    fingerprint: str = ""


class PlanResponse(BaseModel):
    horizon: Horizon
    start_date: date
    generated_at: datetime
    # SHA-256 over the plan's substance (which task goes in which block,
    # and when those blocks run) -- see app/planning.py:plan_fingerprint.
    fingerprint: str
    sections: list[SectionPlanResult]


# --- What-if replanning (spec step 8) ---------------------------------------


class CancelBlock(BaseModel):
    """Traffic control withdraws a block opportunity entirely."""

    kind: Literal["cancel_block"]
    block_id: str


class CurtailBlock(BaseModel):
    """A block is granted late: it starts minutes_lost later and ends on time."""

    kind: Literal["curtail_block"]
    block_id: str
    minutes_lost: int = Field(gt=0)


class MoveBlock(BaseModel):
    """A block is moved to a different time. It keeps its length unless a
    new one is given."""

    kind: Literal["move_block"]
    block_id: str
    new_start: datetime
    duration_min: int | None = Field(default=None, gt=0, le=720)


class UrgentDefect(BaseModel):
    """A new defect found mid-week that needs a block this week."""

    kind: Literal["urgent_defect"]
    section: str
    department: Department
    defect_type: str
    km_from: float
    km_to: float
    severity_code: SeverityCode = SeverityCode.A
    est_duration_min: int = Field(gt=0)
    block_type_required: BlockType


Disruption = Annotated[CancelBlock | CurtailBlock | MoveBlock | UrgentDefect, Field(discriminator="kind")]


class WhatIfRequest(BaseModel):
    disruptions: list[Disruption] = Field(min_length=1)


class TaskChange(BaseModel):
    task_id: str
    section: str
    change: Literal["dropped", "added", "moved", "new_scheduled", "new_unscheduled"]
    block_before: str | None
    block_after: str | None
    reason_after: str


class WhatIfSectionResult(BaseModel):
    section: str
    before: SectionPlanResult
    after: SectionPlanResult


class WhatIfResponse(BaseModel):
    applied: list[str]  # one plain-language line per disruption
    sections: list[WhatIfSectionResult]  # only sections a disruption touched
    changes: list[TaskChange]
    replan_seconds: float  # measured wall time of the replan, nothing added


class CorridorBlockSummary(BaseModel):
    block_id: str
    section: str
    start_time: datetime
    end_time: datetime
    duration_min: int
    block_type_possible: BlockType
    expected_train_impact: float
    goods_traffic_load: float
    data_source: Literal["synthetic", "ntes_live"]
