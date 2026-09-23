"""Bridge to the ntes-adapter service (../ntes-adapter/): pulls real,
self-collected predicted-availability data for the handful of corridors
it actually covers and uses it to make those corridors' block
opportunities reflect real clearance likelihood instead of purely
synthetic expected_train_impact. Sections outside
NTES_INTEGRATED_SECTIONS keep the generator's numbers unchanged -- there
is no real data for them.

This is an optional enrichment layer, not a dependency: the adapter is a
separate process that may not be running, may not have accumulated any
history yet (a fresh instance reports observed_nights=0 -- see its
README), or may be unreachable. Any of those cases falls back to the
synthetic values untouched rather than failing the caller. The mapping
from "recurring HH:MM-HH:MM window's availability" to "this specific
block's expected_train_impact" is a real modeling choice, not a
measured quantity -- see apply_ntes_predictions' docstring.
"""

import logging
from datetime import time

import httpx

from app.config import NTES_ADAPTER_BASE_URL
from app.datagen.reference_data import NTES_INTEGRATED_SECTIONS
from app.models.block import BlockOpportunity

logger = logging.getLogger("railmaster.ntes_bridge")


def fetch_predicted_windows(corridor: str, base_url: str = NTES_ADAPTER_BASE_URL) -> list[dict]:
    """[] on any failure (adapter down, corridor unknown to it, no cached
    predictions yet) -- all of those are legitimate "no real data available
    right now" states, not errors worth surfacing to the scheduler."""
    try:
        resp = httpx.get(f"{base_url}/api/v1/corridors/{corridor}/predicted-windows", timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001 -- enrichment is best-effort by design
        logger.info("ntes-adapter unavailable for %s, using synthetic data: %s", corridor, exc)
        return []


def fetch_live_trains(corridor: str, base_url: str = NTES_ADAPTER_BASE_URL) -> dict | None:
    """Current train boards for both ends of a corridor, or None if the
    adapter has nothing to offer. Same best-effort contract as
    fetch_predicted_windows: an unreachable adapter is a normal state, not
    an error the dashboard should surface as a failure."""
    try:
        resp = httpx.get(f"{base_url}/api/v1/corridors/{corridor}/live", timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001 -- enrichment is best-effort by design
        logger.info("ntes-adapter live data unavailable for %s: %s", corridor, exc)
        return None


def _parse_window(window: str) -> tuple[time, time]:
    start_str, end_str = window.split("-")
    start_h, start_m = (int(x) for x in start_str.split(":"))
    end_h, end_m = (int(x) for x in end_str.split(":"))
    return time(start_h, start_m), time(end_h, end_m)


def _block_falls_in_window(block: BlockOpportunity, window: str) -> bool:
    block_start = block.start_time.time()
    window_start, window_end = _parse_window(window)
    if window_end <= window_start:  # crosses midnight
        return block_start >= window_start or block_start < window_end
    return window_start <= block_start < window_end


def apply_ntes_predictions(
    blocks: list[BlockOpportunity], base_url: str = NTES_ADAPTER_BASE_URL
) -> list[BlockOpportunity]:
    """For each NTES-integrated section, replace expected_train_impact
    with 1 - predicted_availability for blocks whose start time falls in
    a recurring window ntes-adapter has predictions for.

    This inversion is a modeling choice: "clear 92% of observed nights"
    becomes "0.08 expected impact," on the reasoning that a corridor
    that's reliably clear at that hour is reliably low-impact to block.
    It is not a measured relationship and hasn't been validated against
    real operational outcomes -- a reasonable starting point for a
    prototype, not a claim that this is the right conversion.
    """
    predictions_by_corridor = {
        corridor: fetch_predicted_windows(corridor, base_url) for corridor in NTES_INTEGRATED_SECTIONS
    }

    for block in blocks:
        predictions = predictions_by_corridor.get(block.section)
        if not predictions:
            continue
        for prediction in predictions:
            if _block_falls_in_window(block, prediction["window"]):
                block.expected_train_impact = round(1 - prediction["predicted_availability"], 3)
                block.data_source = "ntes_live"
                break

    return blocks
