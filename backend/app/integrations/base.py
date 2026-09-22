"""Common adapter interface for maintenance-data source systems.

Each of TMS, SMMS, TDMS implements this so the scheduler doesn't care
which department/system a task came from. Real connectors (DB/API calls
to the actual systems) can later replace the mock implementations in
app/mock_data/ without changing callers.
"""

from abc import ABC, abstractmethod

from app.models.maintenance_task import MaintenanceTask


class MaintenanceSourceAdapter(ABC):
    @abstractmethod
    def fetch_open_tasks(self) -> list[MaintenanceTask]:
        """Return all open/overdue maintenance tasks from this system."""
        raise NotImplementedError
