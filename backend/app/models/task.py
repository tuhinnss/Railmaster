"""Maintenance task. Field names and types match build spec section 2
exactly — this is the one shape every data source (synthetic today, real
TMS/SMMS/TDMS later) converts into."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import Department, SeverityCode, BlockType


class MaintenanceTask(BaseModel):
    task_id: str
    department: Department
    asset_id: str
    section: str
    km_range: tuple[float, float]
    defect_type: str
    severity_code: SeverityCode
    date_raised: date
    due_date: date
    days_overdue: int
    est_duration_min: int
    crew_required: int
    block_type_required: BlockType
    depends_on: list[str] = Field(default_factory=list)
    # Not part of the original spec section 2 shape -- provenance metadata,
    # like BlockOpportunity.data_source. "reported" marks a defect someone
    # entered on the Report Defect page (app/operations.py), so it is never
    # shown the same way as the generated backlog.
    data_source: Literal["synthetic", "reported"] = "synthetic"
