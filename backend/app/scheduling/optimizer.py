"""Assigns ranked maintenance tasks to available corridor block windows.

TODO: start with a greedy assignment (highest priority task -> earliest
compatible window, respecting corridor/section conflicts across
departments) and evaluate a constraint solver (e.g. OR-tools) later if
greedy proves insufficient.
"""

from app.models.maintenance_task import MaintenanceTask
from app.models.corridor import BlockWindow
from app.models.block_plan import ScheduledBlock


def assign_blocks(
    ranked_tasks: list[MaintenanceTask],
    available_windows: list[BlockWindow],
) -> list[ScheduledBlock]:
    raise NotImplementedError
