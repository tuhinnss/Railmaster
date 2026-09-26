"""Stage A: single-section CP-SAT scheduler, hard constraints only (spec
section 5).

Deliberately no merging: each block holds at most one task. Stage B adds
the y_b "block opened" variable, the beta/gamma consolidation incentive,
and the km-range/no-safety-conflict compatibility set that governs when
two tasks may share a block. Layering that on before this stage's plain
task-to-block assignment mechanics (capacity, block-type match, dependency
order, priority-driven allocation of scarce blocks) are correct and
tested would make either stage's bugs hard to isolate -- hence building
them separately, per spec.

"Delay" isn't formally defined in the spec text beyond its use in the
objective. We take it as days from the reference date to the chosen
block's date: a task scheduled sooner has lower delay. Leaving a task
unscheduled is modeled as worse than any in-horizon delay, so the solver
always prefers scheduling when a compatible block exists, and uses
priority to arbitrate when blocks are scarce.
"""

from dataclasses import dataclass, field
from datetime import date

from ortools.sat.python import cp_model

from app.models.block import BlockOpportunity
from app.models.task import MaintenanceTask
from app.scheduling.common import PRIORITY_SCALE, UNSCHEDULED_PENALTY_DAYS, delay_days, hold_for_owner, new_solver
from app.scheduling.compatibility import task_fits_block
from app.scheduling.config import DEFAULT_PRIORITY_WEIGHTS, PriorityWeights
from app.scheduling.prioritizer import score_task


@dataclass
class StageAResult:
    section: str
    assignments: dict[str, str | None]  # task_id -> block_id, or None if unscheduled
    objective_value: int
    solver_status: str
    compatible_blocks_by_task: dict[str, list[str]] = field(default_factory=dict)


def solve_stage_a(
    tasks: list[MaintenanceTask],
    blocks: list[BlockOpportunity],
    reference_date: date,
    weights: PriorityWeights = DEFAULT_PRIORITY_WEIGHTS,
) -> StageAResult:
    """tasks and blocks must already be filtered to a single section."""
    sections = {t.section for t in tasks} | {b.section for b in blocks}
    if len(sections) > 1:
        raise ValueError(f"Stage A is single-section only, got: {sorted(sections)}")
    section = next(iter(sections), "")

    model = cp_model.CpModel()

    priority_by_task = {t.task_id: score_task(t, blocks, weights).score for t in tasks}
    tasks_by_id = {t.task_id: t for t in tasks}

    x: dict[tuple[str, str], cp_model.IntVar] = {}
    compatible_blocks_by_task: dict[str, list[BlockOpportunity]] = {t.task_id: [] for t in tasks}

    for task in tasks:
        for block in blocks:
            if task_fits_block(task, block):
                var = model.NewBoolVar(f"x_{task.task_id}_{block.block_id}")
                x[(task.task_id, block.block_id)] = var
                compatible_blocks_by_task[task.task_id].append(block)

    # Each task assigned to at most one block.
    for task in tasks:
        task_vars = [x[(task.task_id, b.block_id)] for b in compatible_blocks_by_task[task.task_id]]
        if task_vars:
            model.Add(sum(task_vars) <= 1)

    # Each block holds at most one task (Stage A: no merging).
    for block in blocks:
        block_vars = [x[(t.task_id, block.block_id)] for t in tasks if (t.task_id, block.block_id) in x]
        if block_vars:
            model.Add(sum(block_vars) <= 1)

    hold_for_owner(model, x, blocks)

    # Dependency order: a dependency in this section's task set must be
    # scheduled at or before its dependent, and the dependent can only be
    # scheduled if the dependency is too. Cross-section dependencies are
    # out of scope for a single-section solve and are left unenforced here.
    for task in tasks:
        for dep_id in task.depends_on:
            if dep_id not in tasks_by_id:
                continue
            task_vars = [x[(task.task_id, b.block_id)] for b in compatible_blocks_by_task[task.task_id]]
            dep_vars = [x[(dep_id, b.block_id)] for b in compatible_blocks_by_task[dep_id]]
            if not task_vars:
                continue
            if dep_vars:
                model.Add(sum(task_vars) <= sum(dep_vars))
            else:
                model.Add(sum(task_vars) == 0)
            for b_t in compatible_blocks_by_task[task.task_id]:
                for b_dep in compatible_blocks_by_task[dep_id]:
                    if b_dep.start_time > b_t.start_time:
                        model.Add(x[(task.task_id, b_t.block_id)] + x[(dep_id, b_dep.block_id)] <= 1)

    objective_terms = []
    for (task_id, block_id), var in x.items():
        block = next(b for b in blocks if b.block_id == block_id)
        delay = delay_days(block, reference_date)
        priority_int = round(priority_by_task[task_id] * PRIORITY_SCALE)
        benefit = priority_int * (UNSCHEDULED_PENALTY_DAYS - delay)
        objective_terms.append(benefit * var)
    if objective_terms:
        model.Maximize(sum(objective_terms))

    solver = new_solver()
    status = solver.Solve(model)

    assignments: dict[str, str | None] = {t.task_id: None for t in tasks}
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for (task_id, block_id), var in x.items():
            if solver.Value(var) == 1:
                assignments[task_id] = block_id

    return StageAResult(
        section=section,
        assignments=assignments,
        objective_value=int(solver.ObjectiveValue()) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else 0,
        solver_status=solver.StatusName(status),
        compatible_blocks_by_task={
            task_id: [b.block_id for b in bs] for task_id, bs in compatible_blocks_by_task.items()
        },
    )
