"""Backs the Report Defect and Control Office pages: field defect reports
and control decisions on planned blocks. Both are persisted (see
app/operations.py) and flow into GET /plans on the next request."""

from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.data_access import load_blocks
from app.operations import (
    add_report,
    clear_decision,
    list_decisions,
    list_reports,
    record_decision,
    withdraw_report,
)
from app.schemas.operations import BlockDecision, BlockDecisionRequest, DefectReport, DefectReportRequest

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("/reports", response_model=list[DefectReport])
def get_reports():
    return list_reports()


@router.post("/reports", response_model=DefectReport, status_code=201)
def post_report(request: DefectReportRequest):
    try:
        return add_report(request, datetime.now())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/reports/{report_id}", status_code=204)
def delete_report(report_id: str):
    if not withdraw_report(report_id):
        raise HTTPException(status_code=404, detail=f"No report {report_id!r}")


@router.get("/decisions", response_model=list[BlockDecision])
def get_decisions():
    return list_decisions()


@router.put("/decisions/{block_id}", response_model=BlockDecision)
def put_decision(block_id: str, request: BlockDecisionRequest):
    # The block as generated, not as currently curtailed or moved: a new
    # decision replaces the old one rather than stacking on it. NTES
    # enrichment only touches expected_train_impact, which a decision
    # doesn't use.
    blocks = load_blocks(enrich_with_ntes=False)
    block = next((b for b in blocks if b.block_id == block_id), None)
    if block is None:
        raise HTTPException(status_code=404, detail=f"No block {block_id!r}")
    days = [b.start_time.date() for b in blocks]
    try:
        return record_decision(block, request, datetime.now(), (min(days), max(days)))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/decisions/{block_id}", status_code=204)
def delete_decision(block_id: str):
    if not clear_decision(block_id):
        raise HTTPException(status_code=404, detail=f"No decision on {block_id!r}")
