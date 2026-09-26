"""Provider abstraction: isolates the fragile part (scraping an
undocumented, unofficial NTES page) behind one interface. Everything
downstream -- occupancy derivation, frequency prediction, the API, and
every test -- runs against this interface and doesn't know or care
whether the data came from NTESProvider or MockProvider.
"""

from abc import ABC, abstractmethod

from app.config import Corridor
from app.models import CorridorTimetable, StationLiveBoard


class RailwayDataProvider(ABC):
    # Surfaced on the API so a consumer can tell real data from canned --
    # see LiveCorridorStatus.provider.
    name: str = "unknown"
    # Whether this provider's boards are observations of what happened
    # tonight, and so may enter the occupancy log and poll coverage that
    # predicted_availability is counted from. Only a live fetch qualifies.
    # A replayed capture re-dated to today, or canned mock trains, would
    # otherwise be logged as "observed tonight" on every poll -- found
    # 2026-09-25, when fixture-mode runs had been doing exactly that.
    records_observations: bool = False

    @abstractmethod
    def get_live_station(self, station_code: str, window_hours: int = 4) -> StationLiveBoard:
        """Current/near-term train movements at one station. Raises on
        failure (network error, unexpected response shape, etc.) -- callers
        (the poller) are responsible for catching, backing off, and falling
        back to cached data. See README for what "current" actually means
        for each provider (NTESProvider: NTES's own next-N-hours board;
        MockProvider: canned, deterministic)."""
        raise NotImplementedError

    def get_timetable(self, corridor: Corridor) -> CorridorTimetable | None:
        """The booked timetable both ways along a corridor, from NTES's
        "Trains between stations" query. None means this provider has no
        timetable for it (the default -- mock has none, rather than an
        invented one); a failed fetch raises, like get_live_station."""
        return None
