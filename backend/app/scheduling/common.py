"""Shared constants and helpers between Stage A and Stage B (spec section
5). Kept out of either stage's module so Stage B doesn't have to reach
into Stage A's internals.

"Delay" isn't formally defined in the spec text beyond its use in the
objective. We take it as days from the reference date to a block's date:
a task scheduled sooner has lower delay.
"""

from datetime import date

from app.models.block import BlockOpportunity

PRIORITY_SCALE = 1000
# Must exceed the largest realistic delay_days for a weekly horizon (~7),
# so "scheduled anywhere in-horizon" always beats "unscheduled."
UNSCHEDULED_PENALTY_DAYS = 30
SOLVE_TIME_BUDGET_SECONDS = 5.0


def delay_days(block: BlockOpportunity, reference_date: date) -> int:
    return max(0, (block.start_time.date() - reference_date).days)
