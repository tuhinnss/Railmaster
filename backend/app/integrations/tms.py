"""Track Management System adapter (Engineering dept). Mocked for now."""

from app.integrations.base import MaintenanceSourceAdapter
from app.models.maintenance_task import MaintenanceTask
from app.models.enums import Department
from app.mock_data import generators


class TMSAdapter(MaintenanceSourceAdapter):
    def fetch_open_tasks(self) -> list[MaintenanceTask]:
        return generators.generate_tasks(department=Department.ENGINEERING, source_system="TMS")
