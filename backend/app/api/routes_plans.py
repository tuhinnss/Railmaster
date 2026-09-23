"""Generates and exposes the weekly block plan: prioritizer -> Stage B
CP-SAT scheduler -> safety validator -> explainability, run per section
and combined. Also runs Stage A per section purely for the
blocks-used comparison (the "blocks saved" number).
"""

from collections import defaultdict
from datetime import date, datetime

from fastapi import APIRouter, HTTPException

from app.data_access import load_blocks, load_tasks
from app.models.enums import Horizon
from app.scheduling.explain import explain_plan
from app.scheduling.prioritizer import score_task
from app.scheduling.stage_a import solve_stage_a
from app.scheduling.stage_b import solve_stage_b
from app.scheduling.validator import validate_plan
from app.schemas.plan import PlanResponse, ScheduledBlockSummary, SectionPlanResult, TaskSummary

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/{horizon}", response_model=PlanResponse)
def get_plan(horizon: Horizon):
    if horizon != Horizon.WEEKLY:
        raise HTTPException(status_code=400, detail="Only the WEEKLY horizon is supported in this build")

    all_tasks = load_tasks()
    all_blocks = load_blocks()
    today = date.today()

    sections = sorted({t.section for t in all_tasks} | {b.section for b in all_blocks})
    section_results: list[SectionPlanResult] = []

    for section in sections:
        tasks = [t for t in all_tasks if t.section == section]
        blocks = [b for b in all_blocks if b.section == section]
        if not tasks:
            continue

        result_a = solve_stage_a(tasks, blocks, today)
        result_b = solve_stage_b(tasks, blocks, today)

        violations = validate_plan(tasks, blocks, result_b.assignments)
        if violations:
            raise HTTPException(
                status_code=500,
                detail=f"Scheduler produced an unsafe plan for {section}: {violations}",
            )

        explanations = {
            e.task_id: e
            for e in explain_plan(tasks, blocks, result_b.assignments, result_b.compatible_blocks_by_task)
        }
        breakdowns = {task.task_id: score_task(task, blocks) for task in tasks}

        blocks_by_id = {b.block_id: b for b in blocks}
        tasks_by_block: dict[str, list[str]] = defaultdict(list)
        for task_id, block_id in result_b.assignments.items():
            if block_id is not None:
                tasks_by_block[block_id].append(task_id)

        task_summaries = [
            TaskSummary(
                task_id=task.task_id,
                department=task.department,
                section=task.section,
                defect_type=task.defect_type,
                severity_code=task.severity_code,
                days_overdue=task.days_overdue,
                block_type_required=task.block_type_required,
                priority_score=breakdowns[task.task_id].score,
                criticality=breakdowns[task.task_id].criticality,
                urgency=breakdowns[task.task_id].urgency,
                availability_impact=breakdowns[task.task_id].availability_impact,
                dominant_component=breakdowns[task.task_id].dominant_component,
                safety_override=breakdowns[task.task_id].safety_override,
                scheduled=result_b.assignments[task.task_id] is not None,
                block_id=result_b.assignments[task.task_id],
                reason=explanations[task.task_id].reason,
            )
            for task in tasks
        ]

        block_summaries = [
            ScheduledBlockSummary(
                block_id=block_id,
                section=section,
                start_time=blocks_by_id[block_id].start_time,
                end_time=blocks_by_id[block_id].end_time,
                block_type_possible=blocks_by_id[block_id].block_type_possible,
                task_ids=task_ids,
                data_source=blocks_by_id[block_id].data_source,
            )
            for block_id, task_ids in tasks_by_block.items()
        ]

        blocks_used_a = len({b for b in result_a.assignments.values() if b is not None})
        blocks_opened_b = len(result_b.blocks_opened)

        section_results.append(
            SectionPlanResult(
                section=section,
                task_count=len(tasks),
                scheduled_count=sum(1 for v in result_b.assignments.values() if v is not None),
                blocks_opened=blocks_opened_b,
                blocks_used_without_merging=blocks_used_a,
                blocks_saved=blocks_used_a - blocks_opened_b,
                tasks=task_summaries,
                blocks=sorted(block_summaries, key=lambda b: b.start_time),
            )
        )

    return PlanResponse(
        horizon=horizon,
        start_date=today,
        generated_at=datetime.now(),
        sections=section_results,
    )
