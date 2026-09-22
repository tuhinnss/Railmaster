"""Generates and exposes weekly/monthly block plans.

TODO: pull tasks + windows from adapters, run prioritizer -> optimizer ->
horizon builder, return the resulting BlockPlan.
"""

from fastapi import APIRouter

from app.models.enums import Horizon

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/{horizon}")
def get_plan(horizon: Horizon):
    raise NotImplementedError
