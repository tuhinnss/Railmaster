"""Explainability (spec section 7): a one-line, generated reason for every
task in a solved plan. No SHAP or model introspection -- the score is a
hand-written formula, not a trained model, so the reason is derived
directly from what the prioritizer and scheduler already computed:

- Scheduled: which component (criticality/urgency/availability impact,
  or the safety override) drove its priority, and which other tasks
  share its block if it was merged.
- Unscheduled: the specific reason it didn't make it in -- an unmet
  dependency, no compatible block at all, or losing out to higher-
  priority tasks for the compatible blocks that did exist.

Stage-agnostic: works against either StageAResult or StageBResult, since
both expose the same assignments / compatible_blocks_by_task shape.
"""

from dataclasses import dataclass

from app.models.block import BlockOpportunity
from app.models.task import MaintenanceTask
from app.scheduling.config import DEFAULT_PRIORITY_WEIGHTS, PriorityWeights
from app.scheduling.prioritizer import PriorityBreakdown, score_task

_COMPONENT_LABELS = {
    "criticality": "criticality",
    "urgency": "urgency (days overdue)",
    "availability_impact": "impact on train operations",
}


@dataclass
class TaskExplanation:
    task_id: str
    scheduled: bool
    reason: str


def explain_scheduled_task(
    block: BlockOpportunity,
    breakdown: PriorityBreakdown,
    co_scheduled_task_ids: list[str],
) -> str:
    if breakdown.safety_override:
        driver = "the safety-critical override (severity A, overdue)"
    else:
        driver = _COMPONENT_LABELS[breakdown.dominant_component]
    reason = (
        f"Scheduled into {block.block_id} on {block.start_time.date()}, "
        f"prioritized by {driver} (score {breakdown.score:.2f})."
    )
    if co_scheduled_task_ids:
        others = ", ".join(sorted(co_scheduled_task_ids))
        reason += f" Shares this block with {others}."
    return reason


def explain_unscheduled_task(
    task: MaintenanceTask,
    compatible_block_ids: list[str],
    assignments: dict[str, str | None],
    tasks_by_id: dict[str, MaintenanceTask],
) -> str:
    for dep_id in task.depends_on:
        if dep_id in tasks_by_id and assignments.get(dep_id) is None:
            return f"Not scheduled: depends on {dep_id}, which is not scheduled this week."

    if not compatible_block_ids:
        return (
            f"Not scheduled: no block this week offers {task.block_type_required.value} "
            f"capacity with enough duration in {task.section}."
        )

    claimants_by_block = {
        block_id: [tid for tid, b in assignments.items() if b == block_id]
        for block_id in compatible_block_ids
    }
    if all(claimants_by_block[b] for b in compatible_block_ids):
        claimants = sorted({tid for ids in claimants_by_block.values() for tid in ids})
        shown = ", ".join(claimants[:3]) + ("..." if len(claimants) > 3 else "")
        return (
            f"Not scheduled: all {len(compatible_block_ids)} compatible block(s) were "
            f"claimed by higher-priority tasks ({shown})."
        )

    return (
        "Not scheduled: didn't fit within a compatible block's remaining capacity "
        "or sharing constraints this week."
    )


def explain_plan(
    tasks: list[MaintenanceTask],
    blocks: list[BlockOpportunity],
    assignments: dict[str, str | None],
    compatible_blocks_by_task: dict[str, list[str]],
    weights: PriorityWeights = DEFAULT_PRIORITY_WEIGHTS,
) -> list[TaskExplanation]:
    tasks_by_id = {t.task_id: t for t in tasks}
    blocks_by_id = {b.block_id: b for b in blocks}
    breakdowns_by_task = {t.task_id: score_task(t, blocks, weights) for t in tasks}

    tasks_by_block: dict[str, list[str]] = {}
    for task_id, block_id in assignments.items():
        if block_id is not None:
            tasks_by_block.setdefault(block_id, []).append(task_id)

    explanations: list[TaskExplanation] = []
    for task in tasks:
        block_id = assignments.get(task.task_id)
        if block_id is not None:
            block = blocks_by_id[block_id]
            co_scheduled = [tid for tid in tasks_by_block[block_id] if tid != task.task_id]
            reason = explain_scheduled_task(block, breakdowns_by_task[task.task_id], co_scheduled)
            explanations.append(TaskExplanation(task_id=task.task_id, scheduled=True, reason=reason))
        else:
            compatible_ids = compatible_blocks_by_task.get(task.task_id, [])
            reason = explain_unscheduled_task(task, compatible_ids, assignments, tasks_by_id)
            explanations.append(TaskExplanation(task_id=task.task_id, scheduled=False, reason=reason))

    return explanations
