"""API response shapes. Separate from the domain models (app/models/) so
the wire format can evolve (e.g. adding dashboard-specific fields)
without touching what the scheduler itself operates on.
"""

from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import BlockType, Department, Horizon, SeverityCode


class TaskSummary(BaseModel):
    task_id: str
    department: Department
    section: str
    defect_type: str
    severity_code: SeverityCode
    days_overdue: int
    block_type_required: BlockType
    priority_score: float
    criticality: float
    urgency: float
    availability_impact: float
    dominant_component: str
    safety_override: bool
    scheduled: bool
    block_id: str | None
    reason: str


class ScheduledBlockSummary(BaseModel):
    block_id: str
    section: str
    start_time: datetime
    end_time: datetime
    block_type_possible: BlockType
    task_ids: list[str]


class SectionPlanResult(BaseModel):
    section: str
    task_count: int
    scheduled_count: int
    blocks_opened: int
    blocks_used_without_merging: int  # Stage A's block count, for the "blocks saved" comparison
    blocks_saved: int
    tasks: list[TaskSummary]
    blocks: list[ScheduledBlockSummary]


class PlanResponse(BaseModel):
    horizon: Horizon
    start_date: date
    generated_at: datetime
    sections: list[SectionPlanResult]


class CorridorBlockSummary(BaseModel):
    block_id: str
    section: str
    start_time: datetime
    end_time: datetime
    duration_min: int
    block_type_possible: BlockType
    expected_train_impact: float
    goods_traffic_load: float
