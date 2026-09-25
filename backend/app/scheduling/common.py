"""Shared constants and helpers between Stage A and Stage B (spec section
5). Kept out of either stage's module so Stage B doesn't have to reach
into Stage A's internals.

"Delay" isn't formally defined in the spec text beyond its use in the
objective. We take it as days from the reference date to a block's date:
a task scheduled sooner has lower delay.
"""

from datetime import date

from ortools.sat.python import cp_model

from app.models.block import BlockOpportunity

PRIORITY_SCALE = 1000
# Must exceed the largest realistic delay_days for a weekly horizon (~7),
# so "scheduled anywhere in-horizon" always beats "unscheduled."
UNSCHEDULED_PENALTY_DAYS = 30
SOLVE_TIME_BUDGET_SECONDS = 5.0


def new_solver() -> cp_model.CpSolver:
    """A CP-SAT solver configured to give the same answer for the same input.

    CP-SAT's default multi-worker search races several strategies and keeps
    whichever optimum it reaches first, so when two plans score identically
    it returns either one. Measured on the seed-1 data: GHY-LMG and NDLS-GZB
    each came back as two different (equally optimal) plans across 8 runs.
    That made the published plan change on a plain page refresh, which a
    plan fingerprint and a what-if before/after diff can't tolerate -- the
    diff would report "moved" tasks the disruption never caused. One worker
    with a fixed seed is deterministic, and at this problem size (<= ~25
    tasks per section) it still solves each section to optimality in
    under 40 ms.
    """
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVE_TIME_BUDGET_SECONDS
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 0
    return solver


def delay_days(block: BlockOpportunity, reference_date: date) -> int:
    return max(0, (block.start_time.date() - reference_date).days)
