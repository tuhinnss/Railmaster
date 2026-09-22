"""Maintenance task / defect, sourced from TMS, SMMS, or TDMS. Fields to be
refined as real source-system data shapes become clear."""

from datetime import date
from pydantic import BaseModel

from app.models.enums import Department, Severity, TaskStatus


class MaintenanceTask(BaseModel):
    id: str
    department: Department
    source_system: str  # "TMS" | "SMMS" | "TDMS"
    asset_id: str
    section: str
    km_marker: float
    description: str
    severity: Severity
    reported_date: date
    due_date: date
    estimated_block_hours: float
    status: TaskStatus = TaskStatus.OPEN
