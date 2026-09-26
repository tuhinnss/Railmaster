"""Backs the Report Defect and control office pages: field defect reports,
control decisions on planned blocks, and blocks added for work that didn't
fit. All are persisted (see app/operations.py) and flow into GET /plans on
the next request."""

from datetime import date, datetime

from fastapi import APIRouter, HTTPException

from app.data_access import load_blocks, load_tasks
from app.operations import (
    add_block,
    add_report,
    added_opportunities,
    clear_decision,
    list_added_blocks,
    list_decisions,
    list_reports,
    record_decision,
    remove_added_block,
    reported_tasks,
    withdraw_report,
)
from app.schemas.operations import (
    AddBlockRequest,
    AddedBlock,
    BlockDecision,
    BlockDecisionRequest,
    DefectReport,
    DefectReportRequest,
)

router = APIRouter(prefix="/operations", tags=["operations"])


def _plan_days(blocks) -> tuple[date, date]:
    """First and last day of the plan week: the days the generated blocks
    fall on. A moved or added block must start inside it."""
    days = [b.start_time.date() for b in blocks]
    return min(days), max(days)


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
    # The block as generated (or added), not as currently curtailed or
    # moved: a new decision replaces the old one rather than stacking on it.
    # NTES enrichment only touches expected_train_impact, which a decision
    # doesn't use.
    blocks = load_blocks(enrich_with_ntes=False)
    candidates = blocks + added_opportunities(list_added_blocks())
    block = next((b for b in candidates if b.block_id == block_id), None)
    if block is None:
        raise HTTPException(status_code=404, detail=f"No block {block_id!r}")
    try:
        return record_decision(block, request, datetime.now(), _plan_days(blocks))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/decisions/{block_id}", status_code=204)
def delete_decision(block_id: str):
    if not clear_decision(block_id):
        raise HTTPException(status_code=404, detail=f"No decision on {block_id!r}")


@router.get("/added-blocks", response_model=list[AddedBlock])
def get_added_blocks():
    return list_added_blocks()


@router.post("/added-blocks", response_model=AddedBlock, status_code=201)
def post_added_block(request: AddBlockRequest):
    tasks = load_tasks() + reported_tasks(list_reports(), date.today())
    task = next((t for t in tasks if t.task_id == request.task_id), None)
    if task is None:
        raise HTTPException(status_code=404, detail=f"No task {request.task_id!r}")
    try:
        return add_block(task, request, datetime.now(), _plan_days(load_blocks(enrich_with_ntes=False)))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/added-blocks/{block_id}", status_code=204)
def delete_added_block(block_id: str):
    if not remove_added_block(block_id):
        raise HTTPException(status_code=404, detail=f"No added block {block_id!r}")
