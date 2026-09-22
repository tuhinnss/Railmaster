"""Exposes corridor block availability -- the Corridors dashboard page's
backing data. Sourced from the synthetic generator for this build (real
COA integration is out of scope, see docs/architecture.md).
"""

from fastapi import APIRouter, Query

from app.data_access import load_blocks

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
            }
            for b in blocks
        ],
        key=lambda b: (b["section"], b["start_time"]),
    )
