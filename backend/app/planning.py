"""The per-section planning pipeline, shared by the weekly plan and what-if
replanning so both go through exactly the same steps:

    prioritizer -> Stage A (comparison only) -> Stage B -> validator -> explain

It lives outside api/ because what-if needs to run it twice (baseline and
disrupted) against in-memory data, and outside scheduling/ because it
assembles API response shapes, which the scheduler itself never sees.

What-if disruptions are applied to copies of the loaded data and never
written back: a scenario is a question asked of the plan, not an edit to
the fixture data every other page reads.
"""

import hashlib
import json
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from app.datagen.reference_data import DEPARTMENT_TASK_ID_PREFIX, NTES_INTEGRATED_SECTIONS, SECTIONS
from app.models.block import BlockOpportunity
from app.models.task import MaintenanceTask
from app.scheduling.explain import explain_plan
from app.scheduling.prioritizer import score_task
from app.scheduling.stage_a import solve_stage_a
from app.scheduling.stage_b import solve_stage_b
from app.scheduling.validator import SafetyViolation, summarize_checks, validate_plan
from app.schemas.plan import (
    CancelBlock,
    CurtailBlock,
    Disruption,
    SafetyCheckSummary,
    ScheduledBlockSummary,
    SectionPlanResult,
    TaskChange,
    TaskSummary,
    UrgentDefect,
    WhatIfResponse,
    WhatIfSectionResult,
)

_SECTION_KM = {name: (km_start, km_end) for name, km_start, km_end in SECTIONS}


class UnsafePlanError(Exception):
    """The validator found a violation in solver output. Never swallowed:
    the API turns it into an HTTP 500 rather than publish an unsafe plan."""

    def __init__(self, section: str, violations: list[SafetyViolation]):
        self.section = section
        self.violations = violations
        super().__init__(f"Scheduler produced an unsafe plan for {section}: {violations}")


@dataclass
class SectionRun:
    result: SectionPlanResult
    assignments: dict[str, str | None]


def plan_section(
    section: str,
    tasks: list[MaintenanceTask],
    blocks: list[BlockOpportunity],
    reference_date: date,
    preferred_assignments: dict[str, str | None] | None = None,
) -> SectionRun:
    result_a = solve_stage_a(tasks, blocks, reference_date)
    result_b = solve_stage_b(tasks, blocks, reference_date, preferred_assignments=preferred_assignments)

    violations = validate_plan(tasks, blocks, result_b.assignments)
    if violations:
        raise UnsafePlanError(section, violations)

    explanations = {
        e.task_id: e
        for e in explain_plan(tasks, blocks, result_b.assignments, result_b.compatible_blocks_by_task)
    }
    breakdowns = {task.task_id: score_task(task, blocks) for task in tasks}
    tasks_by_id = {t.task_id: t for t in tasks}
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
            km_range=task.km_range,
            defect_type=task.defect_type,
            severity_code=task.severity_code,
            days_overdue=task.days_overdue,
            block_type_required=task.block_type_required,
            est_duration_min=task.est_duration_min,
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
            duration_min=blocks_by_id[block_id].duration_min,
            used_min=sum(tasks_by_id[tid].est_duration_min for tid in task_ids),
        )
        for block_id, task_ids in tasks_by_block.items()
    ]

    safety_checks = [
        SafetyCheckSummary(**vars(check))
        for check in summarize_checks(tasks, blocks, result_b.assignments, violations)
    ]

    blocks_used_a = len({b for b in result_a.assignments.values() if b is not None})
    blocks_opened_b = len(result_b.blocks_opened)
    km_start, km_end = _SECTION_KM.get(section, (0.0, 0.0))

    result = SectionPlanResult(
        section=section,
        km_start=km_start,
        km_end=km_end,
        ntes_integrated=section in NTES_INTEGRATED_SECTIONS,
        task_count=len(tasks),
        scheduled_count=sum(1 for v in result_b.assignments.values() if v is not None),
        blocks_opened=blocks_opened_b,
        blocks_used_without_merging=blocks_used_a,
        blocks_saved=blocks_used_a - blocks_opened_b,
        tasks=task_summaries,
        blocks=sorted(block_summaries, key=lambda b: b.start_time),
        safety_checks=safety_checks,
    )
    result.fingerprint = plan_fingerprint(reference_date, [result])
    return SectionRun(result=result, assignments=result_b.assignments)


def sections_in(tasks: list[MaintenanceTask], blocks: list[BlockOpportunity]) -> list[str]:
    """Every section with work to plan. A section with blocks but no tasks
    has nothing to schedule and is left out of the plan."""
    with_tasks = {t.section for t in tasks}
    return sorted(s for s in with_tasks | {b.section for b in blocks} if s in with_tasks)


def plan_all(
    tasks: list[MaintenanceTask], blocks: list[BlockOpportunity], reference_date: date
) -> dict[str, SectionRun]:
    return {
        section: plan_section(
            section,
            [t for t in tasks if t.section == section],
            [b for b in blocks if b.section == section],
            reference_date,
        )
        for section in sections_in(tasks, blocks)
    }


def plan_fingerprint(reference_date: date, sections: list[SectionPlanResult]) -> str:
    """SHA-256 over what the plan commits to: which task goes in which block
    (including which were left out), and when and as what type those blocks
    run. Deliberately excludes generated_at and the explanatory text, so two
    requests that produce the same plan produce the same fingerprint --
    which only holds because the solver is deterministic (see
    scheduling/common.py:new_solver). This identifies a plan version; it is
    not a signature and proves nothing about who produced it."""
    payload = {
        "start_date": reference_date.isoformat(),
        "sections": [
            {
                "section": s.section,
                "assignments": sorted([t.task_id, t.block_id] for t in s.tasks),
                "blocks": [
                    [b.block_id, b.start_time.isoformat(), b.end_time.isoformat(), b.block_type_possible.value]
                    for b in sorted(s.blocks, key=lambda b: b.block_id)
                ],
            }
            for s in sorted(sections, key=lambda s: s.section)
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --- What-if ---------------------------------------------------------------


def apply_disruptions(
    tasks: list[MaintenanceTask],
    blocks: list[BlockOpportunity],
    disruptions: list[Disruption],
    reference_date: date,
) -> tuple[list[MaintenanceTask], list[BlockOpportunity], list[str], set[str], set[str]]:
    """Returns (tasks, blocks, applied-descriptions, affected sections,
    injected task ids). Works on copies; the inputs are left untouched.
    Raises ValueError for a disruption that can't apply (unknown block,
    km range outside the section, ...)."""
    tasks = [t.model_copy(deep=True) for t in tasks]
    blocks = [b.model_copy(deep=True) for b in blocks]
    applied: list[str] = []
    affected: set[str] = set()
    injected: set[str] = set()

    for d in disruptions:
        if isinstance(d, (CancelBlock, CurtailBlock)):
            block = next((b for b in blocks if b.block_id == d.block_id), None)
            if block is None:
                raise ValueError(f"Unknown block {d.block_id!r}")
            affected.add(block.section)
            if isinstance(d, CancelBlock):
                blocks.remove(block)
                applied.append(f"{block.block_id} ({block.section}) cancelled.")
            else:
                if d.minutes_lost >= block.duration_min:
                    raise ValueError(
                        f"{block.block_id} is only {block.duration_min} min long; losing "
                        f"{d.minutes_lost} min leaves nothing -- cancel it instead"
                    )
                block.start_time += timedelta(minutes=d.minutes_lost)
                block.duration_min -= d.minutes_lost
                applied.append(
                    f"{block.block_id} ({block.section}) granted {d.minutes_lost} min late: "
                    f"{block.duration_min} min left, from {block.start_time:%a %H:%M}."
                )

        elif isinstance(d, UrgentDefect):
            if d.section not in _SECTION_KM:
                raise ValueError(f"Unknown section {d.section!r}")
            km_start, km_end = _SECTION_KM[d.section]
            if not (km_start <= d.km_from < d.km_to <= km_end):
                raise ValueError(
                    f"km {d.km_from}-{d.km_to} is not a valid range inside {d.section} "
                    f"(km {km_start}-{km_end})"
                )
            task_id = f"{DEPARTMENT_TASK_ID_PREFIX[d.department]}-WHATIF-{len(injected) + 1:02d}"
            tasks.append(
                MaintenanceTask(
                    task_id=task_id,
                    department=d.department,
                    asset_id="WHATIF",
                    section=d.section,
                    km_range=(d.km_from, d.km_to),
                    defect_type=d.defect_type,
                    severity_code=d.severity_code,
                    date_raised=reference_date,
                    due_date=reference_date,
                    # Found today and due today: not overdue, so a severity-A
                    # injection gets top criticality but not the safety
                    # override, exactly as a real just-reported defect would.
                    days_overdue=0,
                    est_duration_min=d.est_duration_min,
                    crew_required=0,  # crew is not enforced anywhere (known gap)
                    block_type_required=d.block_type_required,
                )
            )
            injected.add(task_id)
            affected.add(d.section)
            applied.append(
                f"New severity-{d.severity_code.value} {d.department.value} defect {task_id} "
                f"({d.defect_type.replace('_', ' ')}) at km {d.km_from}-{d.km_to} in {d.section}, "
                f"needs {d.est_duration_min} min of {d.block_type_required.value} block."
            )

    return tasks, blocks, applied, affected, injected


_CHANGE_ORDER = {"dropped": 0, "new_unscheduled": 1, "new_scheduled": 2, "moved": 3, "added": 4}


def diff_assignments(
    section: str,
    before: dict[str, str | None],
    after: SectionRun,
    injected: set[str],
) -> list[TaskChange]:
    reasons = {t.task_id: t.reason for t in after.result.tasks}
    changes: list[TaskChange] = []
    for task_id, block_after in after.assignments.items():
        block_before = before.get(task_id)
        if task_id in injected:
            kind = "new_scheduled" if block_after else "new_unscheduled"
        elif block_before and not block_after:
            kind = "dropped"
        elif block_after and not block_before:
            kind = "added"
        elif block_before != block_after:
            kind = "moved"
        else:
            continue
        changes.append(
            TaskChange(
                task_id=task_id,
                section=section,
                change=kind,
                block_before=block_before,
                block_after=block_after,
                reason_after=reasons[task_id],
            )
        )
    return changes


def run_what_if(
    tasks: list[MaintenanceTask],
    blocks: list[BlockOpportunity],
    disruptions: list[Disruption],
    reference_date: date,
) -> WhatIfResponse:
    new_tasks, new_blocks, applied, affected, injected = apply_disruptions(
        tasks, blocks, disruptions, reference_date
    )

    section_results: list[WhatIfSectionResult] = []
    changes: list[TaskChange] = []
    replan_seconds = 0.0

    for section in sorted(affected):
        baseline = plan_section(
            section,
            [t for t in tasks if t.section == section],
            [b for b in blocks if b.section == section],
            reference_date,
        )
        started = time.perf_counter()
        replanned = plan_section(
            section,
            [t for t in new_tasks if t.section == section],
            [b for b in new_blocks if b.section == section],
            reference_date,
            preferred_assignments=baseline.assignments,
        )
        replan_seconds += time.perf_counter() - started

        section_results.append(WhatIfSectionResult(section=section, before=baseline.result, after=replanned.result))
        changes.extend(diff_assignments(section, baseline.assignments, replanned, injected))

    changes.sort(key=lambda c: (_CHANGE_ORDER[c.change], c.section, c.task_id))
    return WhatIfResponse(
        applied=applied,
        sections=section_results,
        changes=changes,
        replan_seconds=round(replan_seconds, 3),
    )
