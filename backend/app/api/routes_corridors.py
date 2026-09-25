"""Exposes corridor block availability -- the Corridors dashboard page's
backing data. Sourced from the synthetic generator for this build (real
COA integration is out of scope, see docs/architecture.md).
"""

from fastapi import APIRouter, HTTPException, Query

from app.data_access import load_blocks
from app.datagen.reference_data import NTES_INTEGRATED_SECTIONS
from app.ntes_bridge import fetch_live_trains, fetch_train_paths

router = APIRouter(prefix="/corridors", tags=["corridors"])


@router.get("/")
def list_corridors(section: str | None = Query(default=None)):
    blocks = load_blocks()
    if section is not None:
        blocks = [b for b in blocks if b.section == section]
    return sorted(
        [
            {
                "block_id": b.block_id,
                "section": b.section,
                "start_time": b.start_time,
                "end_time": b.end_time,
                "duration_min": b.duration_min,
                "block_type_possible": b.block_type_possible,
                "expected_train_impact": b.expected_train_impact,
                "goods_traffic_load": b.goods_traffic_load,
                "data_source": b.data_source,
            }
            for b in blocks
        ],
        key=lambda b: (b["section"], b["start_time"]),
    )


@router.get("/{section}/trains")
def get_corridor_trains(section: str):
    """Train movements at both ends of an NTES-integrated section, proxied
    from ntes-adapter."""
    _require_integrated(section)
    live = fetch_live_trains(section)
    if live is None:
        raise HTTPException(status_code=503, detail="ntes-adapter is unreachable")
    return live


@router.get("/{section}/train-paths")
def get_corridor_train_paths(section: str):
    """Paired train traversals of an NTES-integrated section, proxied from
    ntes-adapter, for the time-distance chart. Carries the adapter's
    provider field through untouched so the page can label mock data."""
    _require_integrated(section)
    paths = fetch_train_paths(section)
    if paths is None:
        raise HTTPException(status_code=503, detail="ntes-adapter is unreachable")
    return paths


def _require_integrated(section: str) -> None:
    """Only the integrated sections have any real data source at all; the
    rest are synthetic and have no trains to show."""
    if section not in NTES_INTEGRATED_SECTIONS:
        raise HTTPException(
            status_code=404,
            detail=f"{section} has no NTES data source (integrated: {NTES_INTEGRATED_SECTIONS})",
        )
