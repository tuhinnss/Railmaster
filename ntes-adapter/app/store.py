"""Persistence: live-board cache (with staleness tracking), an
append-only section-occupancy log, a poll-coverage log (which nights we
actually had live data for, distinct from which nights were clear -- see
frequency.py), cached frequency predictions, and the latest booked
timetable per corridor.

Backed by JSON files so the prototype needs no database; kept behind a
small interface so swapping in a real one later doesn't touch callers.
Pass data_dir=None (the default in tests) for a pure in-memory store.
"""

import json
import threading
from datetime import datetime
from pathlib import Path

from app.models import CorridorTimetable, PredictedWindow, SectionOccupancyInterval, StationLiveBoard


class Store:
    def __init__(self, data_dir: Path | None = None):
        self._lock = threading.Lock()
        self._data_dir = data_dir
        self._live_boards: dict[str, StationLiveBoard] = {}
        self._occupancy_log: list[SectionOccupancyInterval] = []
        self._poll_coverage: dict[str, list[datetime]] = {}
        self._predictions: dict[str, list[PredictedWindow]] = {}
        self._timetables: dict[str, CorridorTimetable] = {}

        if self._data_dir is not None:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            self._load()

    # --- live cache ---
    def set_live_board(self, station_code: str, board: StationLiveBoard) -> None:
        with self._lock:
            self._live_boards[station_code] = board

    def get_live_board(self, station_code: str) -> StationLiveBoard | None:
        with self._lock:
            return self._live_boards.get(station_code)

    def get_last_successful_fetch(self, station_code: str) -> datetime | None:
        with self._lock:
            board = self._live_boards.get(station_code)
            return board.fetched_at if board else None

    # --- occupancy log ---
    def append_occupancy(self, intervals: list[SectionOccupancyInterval]) -> None:
        if not intervals:
            return
        with self._lock:
            self._occupancy_log.extend(intervals)
            self._persist_occupancy()

    def get_occupancy(self, corridor: str) -> list[SectionOccupancyInterval]:
        with self._lock:
            return [iv for iv in self._occupancy_log if iv.corridor == corridor]

    # --- poll coverage (which nights we actually had live data for) ---
    def append_poll_success(self, corridor: str, timestamp: datetime) -> None:
        with self._lock:
            self._poll_coverage.setdefault(corridor, []).append(timestamp)
            self._persist_coverage()

    def get_poll_timestamps(self, corridor: str) -> list[datetime]:
        with self._lock:
            return list(self._poll_coverage.get(corridor, []))

    # --- predictions cache ---
    def set_predictions(self, corridor: str, predictions: list[PredictedWindow]) -> None:
        with self._lock:
            self._predictions[corridor] = predictions
            self._persist_predictions()

    def get_predictions(self, corridor: str) -> list[PredictedWindow]:
        with self._lock:
            return list(self._predictions.get(corridor, []))

    # --- booked timetables (replaced whole on each successful fetch) ---
    def set_timetable(self, timetable: CorridorTimetable) -> None:
        with self._lock:
            self._timetables[timetable.corridor] = timetable
            self._persist_timetables()

    def get_timetable(self, corridor: str) -> CorridorTimetable | None:
        with self._lock:
            return self._timetables.get(corridor)

    # --- persistence (best-effort JSON files; skipped for in-memory stores) ---
    def _persist_occupancy(self) -> None:
        if self._data_dir is None:
            return
        path = self._data_dir / "occupancy_log.json"
        path.write_text(json.dumps([json.loads(iv.model_dump_json()) for iv in self._occupancy_log], indent=2))

    def _persist_coverage(self) -> None:
        if self._data_dir is None:
            return
        path = self._data_dir / "poll_coverage.json"
        data = {c: [ts.isoformat() for ts in timestamps] for c, timestamps in self._poll_coverage.items()}
        path.write_text(json.dumps(data, indent=2))

    def _persist_predictions(self) -> None:
        if self._data_dir is None:
            return
        path = self._data_dir / "predictions.json"
        data = {c: [json.loads(p.model_dump_json()) for p in preds] for c, preds in self._predictions.items()}
        path.write_text(json.dumps(data, indent=2))

    def _persist_timetables(self) -> None:
        if self._data_dir is None:
            return
        path = self._data_dir / "timetables.json"
        data = {c: json.loads(t.model_dump_json()) for c, t in self._timetables.items()}
        path.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        occ_path = self._data_dir / "occupancy_log.json"
        if occ_path.exists():
            self._occupancy_log = [SectionOccupancyInterval(**r) for r in json.loads(occ_path.read_text())]

        cov_path = self._data_dir / "poll_coverage.json"
        if cov_path.exists():
            raw = json.loads(cov_path.read_text())
            self._poll_coverage = {
                c: [datetime.fromisoformat(ts) for ts in timestamps] for c, timestamps in raw.items()
            }

        pred_path = self._data_dir / "predictions.json"
        if pred_path.exists():
            raw = json.loads(pred_path.read_text())
            self._predictions = {c: [PredictedWindow(**p) for p in preds] for c, preds in raw.items()}

        tt_path = self._data_dir / "timetables.json"
        if tt_path.exists():
            raw = json.loads(tt_path.read_text())
            self._timetables = {c: CorridorTimetable(**t) for c, t in raw.items()}
