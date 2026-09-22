"""Fake-but-realistic data generators standing in for TMS/SMMS/TDMS/COA
until real integrations exist.

TODO: flesh out with randomized/seeded generation (sections, severities,
overdue spread, corridor windows around a plausible timetable, etc).
"""

from app.models.enums import Department
from app.models.maintenance_task import MaintenanceTask
from app.models.corridor import BlockWindow, TrainTimetableEntry, GoodsForecast


def generate_tasks(department: Department, source_system: str) -> list[MaintenanceTask]:
    raise NotImplementedError


def generate_block_windows() -> list[BlockWindow]:
    raise NotImplementedError


def generate_timetable() -> list[TrainTimetableEntry]:
    raise NotImplementedError


def generate_goods_forecast() -> list[GoodsForecast]:
    raise NotImplementedError
