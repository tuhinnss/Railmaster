"""FastAPI service exposing configured corridors, live NTES-derived
status (with a staleness flag), and cached historical frequency
predictions.

Provider is chosen by NTES_ADAPTER_PROVIDER (default "mock"):
  mock     -- canned, deterministic. Default everywhere, including tests.
  fixture  -- replays the real NTES responses captured during
              investigation (real trains, today's date -- see
              fixture_provider.py). No network access.
  ntes     -- best-effort live scrape. Read the README's investigation
              section before using this for anything real.

Run: uvicorn app.main:app --reload
"""

import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException

from app.config import CORRIDORS, STALE_THRESHOLD_SECONDS
from app.models import LiveCorridorStatus, PredictedWindow
from app.poller import Poller
from app.providers.fixture_provider import CapturedFixtureProvider
from app.providers.mock_provider import MockProvider
from app.providers.ntes_provider import NTESProvider
from app.store import Store

logging.basicConfig(level=logging.INFO)

DATA_DIR = Path(os.environ.get("NTES_ADAPTER_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
PROVIDER_NAME = os.environ.get("NTES_ADAPTER_PROVIDER", "mock").lower()
POLL_INTERVAL_SECONDS = int(os.environ.get("NTES_ADAPTER_POLL_INTERVAL", "60"))

_PROVIDERS = {
    "mock": MockProvider,
    "fixture": CapturedFixtureProvider,
    "ntes": NTESProvider,
}
if PROVIDER_NAME not in _PROVIDERS:
    raise ValueError(f"NTES_ADAPTER_PROVIDER must be one of {sorted(_PROVIDERS)}, got {PROVIDER_NAME!r}")

store = Store(data_dir=DATA_DIR)
provider = _PROVIDERS[PROVIDER_NAME]()
poller = Poller(provider, store, interval_seconds=POLL_INTERVAL_SECONDS)
_stop_event = threading.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    thread = threading.Thread(target=poller.run_forever, args=(_stop_event,), daemon=True)
    thread.start()
    yield
    _stop_event.set()
    thread.join(timeout=5)


app = FastAPI(title="Rail Master NTES Adapter", lifespan=lifespan)


def _find_corridor(corridor_id: str):
    for c in CORRIDORS:
        if c.corridor_id == corridor_id:
            return c
    return None


def _freshness(cfg) -> tuple[datetime | None, bool]:
    """(older of the two stations' last successful fetch, stale?). A
    corridor is only as fresh as its staler end."""
    fetch_a = store.get_last_successful_fetch(cfg.station_a)
    fetch_b = store.get_last_successful_fetch(cfg.station_b)

    if fetch_a and fetch_b:
        last_successful_fetch = min(fetch_a, fetch_b)
    else:
        last_successful_fetch = fetch_a or fetch_b

    stale = (
        last_successful_fetch is None
        or (datetime.now() - last_successful_fetch).total_seconds() > STALE_THRESHOLD_SECONDS
    )
    return last_successful_fetch, stale


@app.get("/api/v1/corridors")
def list_corridors():
    return [
        {
            "corridor": c.corridor_id,
            "station_a": c.station_a,
            "station_a_name": c.station_a_name,
            "station_b": c.station_b,
            "station_b_name": c.station_b_name,
        }
        for c in CORRIDORS
    ]


@app.get("/api/v1/corridors/{corridor}/live", response_model=LiveCorridorStatus)
def get_live(corridor: str):
    cfg = _find_corridor(corridor)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"Unknown corridor {corridor!r}")

    board_a = store.get_live_board(cfg.station_a)
    board_b = store.get_live_board(cfg.station_b)
    last_successful_fetch, stale = _freshness(cfg)

    return LiveCorridorStatus(
        corridor=corridor,
        station_a=board_a,
        station_b=board_b,
        stale=stale,
        last_successful_fetch=last_successful_fetch,
        provider=provider.name,
    )


@app.get("/api/v1/corridors/{corridor}/predicted-windows", response_model=list[PredictedWindow])
def get_predicted_windows(corridor: str):
    cfg = _find_corridor(corridor)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"Unknown corridor {corridor!r}")
    return store.get_predictions(corridor)
