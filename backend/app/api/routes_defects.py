"""Exposes maintenance tasks/defects aggregated from TMS, SMMS, TDMS.

TODO: wire up adapters and return a merged, ranked list.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/defects", tags=["defects"])


@router.get("/")
def list_defects():
    raise NotImplementedError
