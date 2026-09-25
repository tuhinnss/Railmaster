"""Generates and exposes the weekly block plan: prioritizer -> Stage B
CP-SAT scheduler -> safety validator -> explainability, run per section
and combined (see app/planning.py). Also runs Stage A per section purely
for the blocks-used comparison (the "blocks saved" number), and answers
what-if questions by replanning disrupted copies of the same data.
"""

from datetime import date, datetime

from fastapi import APIRouter, HTTPException

from app.data_access import load_blocks, load_tasks
from app.models.enums import Horizon
from app.planning import UnsafePlanError, plan_all, plan_fingerprint, run_what_if
from app.schemas.plan import PlanResponse, WhatIfRequest, WhatIfResponse

router = APIRouter(prefix="/plans", tags=["plans"])


def _require_weekly(horizon: Horizon) -> None:
    if horizon != Horizon.WEEKLY:
        raise HTTPException(status_code=400, detail="Only the WEEKLY horizon is supported in this build")


@router.get("/{horizon}", response_model=PlanResponse)
def get_plan(horizon: Horizon):
    _require_weekly(horizon)
    today = date.today()

    try:
        runs = plan_all(load_tasks(), load_blocks(), today)
    except UnsafePlanError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    sections = [run.result for run in runs.values()]
    return PlanResponse(
        horizon=horizon,
        start_date=today,
        generated_at=datetime.now(),
        fingerprint=plan_fingerprint(today, sections),
        sections=sections,
    )


@router.post("/{horizon}/what-if", response_model=WhatIfResponse)
def what_if(horizon: Horizon, request: WhatIfRequest):
    """Replans the sections a set of disruptions touches and reports the
    before/after difference. Nothing is persisted: the fixture data every
    other endpoint reads is unchanged afterwards. An unsafe replan is a
    500, exactly as for the weekly plan."""
    _require_weekly(horizon)

    try:
        return run_what_if(load_tasks(), load_blocks(), request.disruptions, date.today())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UnsafePlanError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
