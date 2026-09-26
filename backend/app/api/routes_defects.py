"""Exposes maintenance tasks/defects ranked by priority score -- the
Task queue dashboard page's backing data. Scheduling status (whether a
plan actually assigns the task to a block) comes from /plans, not here;
this is the pre-scheduling priority view.
"""

from datetime import date

from fastapi import APIRouter, Query

from app.data_access import load_blocks, load_tasks
from app.models.enums import Department, SeverityCode
from app.operations import list_reports, reported_tasks
from app.scheduling.prioritizer import rank_tasks

router = APIRouter(prefix="/defects", tags=["defects"])


@router.get("/")
def list_defects(
    department: Department | None = Query(default=None),
    severity_code: SeverityCode | None = Query(default=None),
):
    tasks = load_tasks() + reported_tasks(list_reports(), date.today())
    blocks = load_blocks()
    tasks_by_id = {t.task_id: t for t in tasks}

    if department is not None:
        tasks = [t for t in tasks if t.department == department]
    if severity_code is not None:
        tasks = [t for t in tasks if t.severity_code == severity_code]

    ranked = rank_tasks(tasks, blocks)
    return [
        {
            "task_id": b.task_id,
            "department": tasks_by_id[b.task_id].department,
            "section": tasks_by_id[b.task_id].section,
            "defect_type": tasks_by_id[b.task_id].defect_type,
            "severity_code": tasks_by_id[b.task_id].severity_code,
            "days_overdue": tasks_by_id[b.task_id].days_overdue,
            "priority_score": b.score,
            "safety_override": b.safety_override,
            "dominant_component": b.dominant_component,
        }
        for b in ranked
    ]
