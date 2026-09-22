"""Stage B: merging (spec section 5).

Extends Stage A's single-section model by letting multiple tasks share a
block, and adds the consolidation incentive: a fixed cost (beta) per
block opened, offset by a reward (gamma) per task scheduled into an
opened block, so that scheduling N tasks into one shared block always
beats spreading them across N separate blocks -- this is the mechanism
behind the demo's "blocks saved" headline number.

Two things the spec text leaves undefined, resolved here (see comments
at point of use for the reasoning): "Used_b" (we take it as the count of
tasks assigned to block b -- "rewards filling an opened block" read
literally), and the magnitudes of beta/gamma (chosen so scheduling always
beats leaving a task out, and merging always beats not merging, in the
same scaled units Stage A already uses for priority*delay).

Stage B compatibility set: two tasks may only share a block if
tasks_can_share_block() allows it -- same section, overlapping km range.
Block-type compatibility and power-isolation safety are enforced
per-task against whichever block is chosen (task_fits_block), not as an
extra pairwise check; see compatibility.py's docstring for why a
TRAFFIC_AND_POWER block safely mixing POWER- and TRAFFIC-requiring tasks
(the worked example) is correct, not a conflict.
"""

from dataclasses import dataclass
from datetime import date

from ortools.sat.python import cp_model

from app.models.block import BlockOpportunity
from app.models.task import MaintenanceTask
from app.scheduling.common import PRIORITY_SCALE, SOLVE_TIME_BUDGET_SECONDS, UNSCHEDULED_PENALTY_DAYS, delay_days
from app.scheduling.compatibility import task_fits_block, tasks_can_share_block
from app.scheduling.config import DEFAULT_PRIORITY_WEIGHTS, PriorityWeights
from app.scheduling.prioritizer import score_task

# The largest possible per-task scheduling benefit is
# PRIORITY_SCALE * UNSCHEDULED_PENALTY_DAYS (priority=1.0, delay=0).
# GAMMA exceeds that so scheduling a task is always worth doing on its
# own merits, before beta/consolidation even enter the picture,
# matching Stage A's "always schedule if a compatible block exists."
GAMMA_PER_TASK = PRIORITY_SCALE * UNSCHEDULED_PENALTY_DAYS  # 30,000
# Comfortably below GAMMA (so opening one block for several tasks never
# costs more than the scheduling reward they bring), but large enough
# relative to typical priority*delay terms to give real consolidation
# pressure: opening N blocks instead of 1 for the same tasks costs
# (N-1)*BETA extra for zero extra benefit.
BETA_PER_BLOCK = GAMMA_PER_TASK // 4  # 7,500


@dataclass
class StageBResult:
    section: str
    assignments: dict[str, str | None]  # task_id -> block_id, or None if unscheduled
    blocks_opened: list[str]
    objective_value: int
    solver_status: str


def solve_stage_b(
    tasks: list[MaintenanceTask],
    blocks: list[BlockOpportunity],
    reference_date: date,
    weights: PriorityWeights = DEFAULT_PRIORITY_WEIGHTS,
    beta: int = BETA_PER_BLOCK,
    gamma: int = GAMMA_PER_TASK,
) -> StageBResult:
    """tasks and blocks must already be filtered to a single section."""
    sections = {t.section for t in tasks} | {b.section for b in blocks}
    if len(sections) > 1:
        raise ValueError(f"Stage B is single-section only, got: {sorted(sections)}")
    section = next(iter(sections), "")

    model = cp_model.CpModel()

    priority_by_task = {t.task_id: score_task(t, blocks, weights).score for t in tasks}
    tasks_by_id = {t.task_id: t for t in tasks}

    x: dict[tuple[str, str], cp_model.IntVar] = {}
    compatible_blocks_by_task: dict[str, list[BlockOpportunity]] = {t.task_id: [] for t in tasks}
    tasks_by_block: dict[str, list[MaintenanceTask]] = {b.block_id: [] for b in blocks}

    for task in tasks:
        for block in blocks:
            if task_fits_block(task, block):
                var = model.NewBoolVar(f"x_{task.task_id}_{block.block_id}")
                x[(task.task_id, block.block_id)] = var
                compatible_blocks_by_task[task.task_id].append(block)
                tasks_by_block[block.block_id].append(task)

    y: dict[str, cp_model.IntVar] = {b.block_id: model.NewBoolVar(f"y_{b.block_id}") for b in blocks}

    # Each task assigned to at most one block.
    for task in tasks:
        task_vars = [x[(task.task_id, b.block_id)] for b in compatible_blocks_by_task[task.task_id]]
        if task_vars:
            model.Add(sum(task_vars) <= 1)

    # Capacity: assigned tasks' durations must fit the block (spec section 6).
    for block in blocks:
        block_tasks = tasks_by_block[block.block_id]
        if block_tasks:
            model.Add(
                sum(t.est_duration_min * x[(t.task_id, block.block_id)] for t in block_tasks)
                <= block.duration_min
            )

    # y_b tracks whether block b is opened at all; the objective penalizes
    # y_b=1, so the solver only sets it when some task actually uses the block.
    for block in blocks:
        for task in tasks_by_block[block.block_id]:
            model.Add(y[block.block_id] >= x[(task.task_id, block.block_id)])

    # Stage B compatibility set (spec section 5): two tasks may only share
    # a block if they're allowed to (same section, overlapping km range).
    for block in blocks:
        block_tasks = tasks_by_block[block.block_id]
        for i in range(len(block_tasks)):
            for j in range(i + 1, len(block_tasks)):
                a, b_task = block_tasks[i], block_tasks[j]
                if not tasks_can_share_block(a, b_task):
                    model.Add(x[(a.task_id, block.block_id)] + x[(b_task.task_id, block.block_id)] <= 1)

    # Dependency order (same logic as Stage A): a same-section dependency
    # must be scheduled at or before its dependent, and the dependent can
    # only be scheduled if the dependency is too.
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

    # Objective (maximize form of the spec's minimize formula): scheduling
    # benefit (priority-weighted, earlier is better) + gamma per task
    # scheduled ("Used_b" summed across blocks), minus beta per block opened.
    objective_terms = []
    for (task_id, block_id), var in x.items():
        block = next(b for b in blocks if b.block_id == block_id)
        delay = delay_days(block, reference_date)
        priority_int = round(priority_by_task[task_id] * PRIORITY_SCALE)
        benefit = priority_int * (UNSCHEDULED_PENALTY_DAYS - delay) + gamma
        objective_terms.append(benefit * var)
    for block in blocks:
        objective_terms.append(-beta * y[block.block_id])
    if objective_terms:
        model.Maximize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVE_TIME_BUDGET_SECONDS
    status = solver.Solve(model)

    assignments: dict[str, str | None] = {t.task_id: None for t in tasks}
    blocks_opened: list[str] = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for (task_id, block_id), var in x.items():
            if solver.Value(var) == 1:
                assignments[task_id] = block_id
        blocks_opened = [b.block_id for b in blocks if solver.Value(y[b.block_id]) == 1]

    return StageBResult(
        section=section,
        assignments=assignments,
        blocks_opened=blocks_opened,
        objective_value=int(solver.ObjectiveValue()) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else 0,
        solver_status=solver.StatusName(status),
    )
