"""Exposes corridor block availability sourced from COA.

TODO: wire up COAAdapter and return block windows / timetable / goods
forecast.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/corridors", tags=["corridors"])


@router.get("/")
def list_corridors():
    raise NotImplementedError
