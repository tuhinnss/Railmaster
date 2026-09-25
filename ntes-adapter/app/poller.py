"""Background polling: refreshes live station data on an interval,
derives section occupancy, records poll coverage, and recomputes cached
frequency predictions. Retries with exponential backoff per-station on
failure and never lets a fetch failure propagate out of a poll cycle --
the API keeps serving the last good cached data (staleness is derived
from fetched_at vs. now at read time, see main.py) instead of crashing.
"""

import logging
import threading
import time
from datetime import date, datetime

from app.config import (
    CORRIDORS,
    FREQUENCY_LOOKBACK_NIGHTS,
    NIGHT_WINDOWS,
    POLL_INTERVAL_SECONDS,
    POLL_MAX_BACKOFF_SECONDS,
)
from app.frequency import compute_predicted_windows
from app.occupancy import derive_corridor_occupancy
from app.providers.base import RailwayDataProvider
from app.store import Store

logger = logging.getLogger("ntes_adapter.poller")


class Poller:
    def __init__(
        self,
        provider: RailwayDataProvider,
        store: Store,
        interval_seconds: int = POLL_INTERVAL_SECONDS,
        max_backoff_seconds: int = POLL_MAX_BACKOFF_SECONDS,
    ):
        self._provider = provider
        self._store = store
        self._interval_seconds = interval_seconds
        self._max_backoff_seconds = max_backoff_seconds
        self._consecutive_failures: dict[str, int] = {}
        self._next_wait_seconds = interval_seconds

    def poll_once(self) -> None:
        next_wait = self._interval_seconds
        for corridor in CORRIDORS:
            next_wait = max(next_wait, self._poll_corridor(corridor))
        self._recompute_predictions()
        self._next_wait_seconds = next_wait

    def _poll_corridor(self, corridor) -> int:
        board_a, backoff_a = self._safe_fetch(corridor.corridor_id, corridor.station_a)
        board_b, backoff_b = self._safe_fetch(corridor.corridor_id, corridor.station_b)

        # Boards are always cached for /live, but only a live provider's
        # boards count as observed nights -- see RailwayDataProvider.
        if board_a is not None and board_b is not None and self._provider.records_observations:
            self._store.append_poll_success(corridor.corridor_id, datetime.now())
            intervals = derive_corridor_occupancy(corridor.corridor_id, board_a, board_b)
            self._store.append_occupancy(intervals)

        return max(backoff_a, backoff_b)

    def _safe_fetch(self, corridor_id: str, station_code: str):
        try:
            board = self._provider.get_live_station(station_code)
        except Exception as exc:  # noqa: BLE001 -- intentionally broad: never crash the poll loop
            failures = self._consecutive_failures.get(station_code, 0) + 1
            self._consecutive_failures[station_code] = failures
            backoff = min(self._interval_seconds * (2 ** (failures - 1)), self._max_backoff_seconds)
            logger.warning(
                "NTES fetch failed for %s (corridor %s), attempt %d, backing off %ds: %s",
                station_code,
                corridor_id,
                failures,
                backoff,
                exc,
            )
            return None, backoff
        else:
            self._consecutive_failures[station_code] = 0
            self._store.set_live_board(station_code, board)
            return board, self._interval_seconds

    def _recompute_predictions(self) -> None:
        today = date.today()
        for corridor in CORRIDORS:
            intervals = self._store.get_occupancy(corridor.corridor_id)
            poll_timestamps = self._store.get_poll_timestamps(corridor.corridor_id)
            predictions = compute_predicted_windows(
                corridor.corridor_id,
                NIGHT_WINDOWS,
                intervals,
                poll_timestamps,
                FREQUENCY_LOOKBACK_NIGHTS,
                today,
            )
            self._store.set_predictions(corridor.corridor_id, predictions)

    def run_forever(self, stop_event: threading.Event | None = None) -> None:
        """Blocking loop; call from a background thread. stop_event lets
        callers (and tests) stop it cleanly instead of killing the thread."""
        while stop_event is None or not stop_event.is_set():
            try:
                self.poll_once()
            except Exception:  # noqa: BLE001 -- a poll cycle must never kill the loop
                logger.exception("Unexpected error in poll cycle -- continuing")
            wait = self._next_wait_seconds
            if stop_event is not None:
                stop_event.wait(wait)
            else:
                time.sleep(wait)
