"""Scores maintenance tasks so the optimizer knows what to schedule first.

TODO: define scoring model — likely a weighted combination of:
- severity (CRITICAL/MAJOR/MINOR)
- days overdue (due_date vs. today)
- asset-availability impact (e.g. single point of failure vs. redundant)
Start with a simple weighted-sum heuristic; ML-based ranking is a later
iteration once we have historical outcome data to learn from.
"""

from app.models.maintenance_task import MaintenanceTask


def score_task(task: MaintenanceTask) -> float:
    raise NotImplementedError


def rank_tasks(tasks: list[MaintenanceTask]) -> list[MaintenanceTask]:
    raise NotImplementedError
