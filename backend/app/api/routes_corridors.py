"""Exposes corridor block availability -- the Corridors dashboard page's
backing data. Sourced from the synthetic generator for this build (real
COA integration is out of scope, see docs/architecture.md).
"""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query

from app.data_access import load_blocks
from app.datagen.reference_data import NTES_INTEGRATED_SECTIONS
from app.ntes_bridge import fetch_live_trains, fetch_timetable
from app.planning import check_km_range
from app.schemas.timetable import QuietSlots, QuietSlotSummary, TimetableCheck, TrainPassSummary
from app.timetable import TrainPass, not_counted, quiet_slots, trains_through

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


NO_TIMETABLE = (
    "No booked timetable for this corridor yet -- ntes-adapter hasn't fetched one, has none "
    "captured, or isn't running. This time was not checked against trains."
)


def _summary(p: TrainPass) -> TrainPassSummary:
    return TrainPassSummary(**vars(p))


def _timetable_for(section: str, km_from: float, km_to: float) -> dict | None:
    _require_integrated(section)
    try:
        check_km_range(section, km_from, km_to)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return fetch_timetable(section)


@router.get("/{section}/timetable-check", response_model=TimetableCheck)
def timetable_check(
    section: str,
    km_from: float,
    km_to: float,
    start: datetime,
    duration_min: int = Query(gt=0, le=720),
):
    """Passenger trains booked over km_from-km_to while a block starting at
    `start` would run. A warning for the control office, never a veto --
    see app/timetable.py for what is estimated."""
    timetable = _timetable_for(section, km_from, km_to)
    if timetable is None:
        return TimetableCheck(section=section, available=False, reason=NO_TIMETABLE)
    passes, left_out = trains_through(
        timetable, section, km_from, km_to, start, start + timedelta(minutes=duration_min)
    )
    return TimetableCheck(
        section=section,
        available=True,
        fetched_at=timetable["fetched_at"],
        provider=timetable["provider"],
        not_counted=left_out,
        trains=[_summary(p) for p in passes],
    )


@router.get("/{section}/quiet-slots", response_model=QuietSlots)
def get_quiet_slots(
    section: str,
    km_from: float,
    km_to: float,
    day: date,
    duration_min: int = Query(gt=0, le=720),
    around: datetime | None = None,
):
    """The quietest start times on `day` for a block of this length at this
    km range -- fewest booked trains, nearest to `around` on a tie."""
    timetable = _timetable_for(section, km_from, km_to)
    if timetable is None:
        return QuietSlots(section=section, available=False, reason=NO_TIMETABLE)
    slots = quiet_slots(timetable, section, km_from, km_to, day, duration_min, around)
    return QuietSlots(
        section=section,
        available=True,
        fetched_at=timetable["fetched_at"],
        provider=timetable["provider"],
        not_counted=not_counted(timetable, section),
        slots=[
            QuietSlotSummary(start=slot.start, end=slot.end, trains=[_summary(p) for p in slot.trains])
            for slot in slots
        ],
    )


def _require_integrated(section: str) -> None:
    """Only the integrated sections have any real data source at all; the
    rest are synthetic and have no trains to show."""
    if section not in NTES_INTEGRATED_SECTIONS:
        raise HTTPException(
            status_code=404,
            detail=f"{section} has no NTES data source (integrated: {NTES_INTEGRATED_SECTIONS})",
        )
