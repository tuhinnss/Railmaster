"""The only user input the app keeps: defects reported from the field and the
control office's decisions on planned blocks.

Everything else is read-only fixture data, and what-if scenarios are never
saved. These two are different on purpose -- a report or a cancelled block
is something that happened, so it has to survive a refresh and show up on
every page. They are applied on top of the fixture data by
planning.plan_current, through the same machinery what-if uses.

Stored as JSON under data/operations/ (gitignored, like data/synthetic/).
RAILMASTER_OPS_DIR overrides the location; the tests use it so they never
touch the real directory.

A reported defect is user-entered prototype input, not a record from a real
defect-management system, so it is planned as a task with
data_source="reported" and every page can tell it apart from the synthetic
backlog.
"""

import json
import os
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from app.datagen.generate import REPO_ROOT
from app.datagen.reference_data import DEPARTMENT_TASK_ID_PREFIX
from app.models.block import BlockOpportunity
from app.models.enums import SeverityCode
from app.models.task import MaintenanceTask
from app.planning import check_km_range
from app.schemas.operations import BlockDecision, BlockDecisionRequest, DefectReport, DefectReportRequest
from app.schemas.plan import CancelBlock, CurtailBlock, MoveBlock

DEFAULT_OPS_DIR = REPO_ROOT / "data" / "operations"
REPORTS_FILE = "reported_defects.json"
DECISIONS_FILE = "block_decisions.json"

# Prototype assumption, not an Indian Railways rule: how long a reported
# defect may wait before it counts as overdue. Severity A is due the day it
# is found, as a what-if urgent defect is, so it gets top criticality at
# once and the safety override from the next day on.
DUE_DAYS_BY_SEVERITY = {SeverityCode.A: 0, SeverityCode.B: 7, SeverityCode.C: 30}

# Also a prototype assumption: the reporter scores a defect 1-10 and the
# band the score falls in is its severity, (lowest score, band) from the top.
# Only the band reaches the plan, so a 9 and a 10 are planned alike; the
# score is kept on the report as the reporter gave it.
SEVERITY_BANDS = ((8, SeverityCode.A), (4, SeverityCode.B), (1, SeverityCode.C))

# FastAPI runs sync endpoints on a thread pool; every read-modify-write of
# the files goes through this so two quick clicks can't lose one.
_lock = threading.Lock()


def ops_dir() -> Path:
    return Path(os.environ.get("RAILMASTER_OPS_DIR", DEFAULT_OPS_DIR))


def _read(name: str, default):
    path = ops_dir() / name
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write(name: str, data) -> None:
    directory = ops_dir()
    directory.mkdir(parents=True, exist_ok=True)
    tmp = directory / f"{name}.tmp"
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(directory / name)  # whole file or nothing, never half-written


# --- Field reports -----------------------------------------------------------


def severity_from_score(score: int) -> SeverityCode:
    return next(band for lowest, band in SEVERITY_BANDS if score >= lowest)


def list_reports() -> list[DefectReport]:
    return [DefectReport(**r) for r in _read(REPORTS_FILE, {"reports": []})["reports"]]


def add_report(request: DefectReportRequest, now: datetime) -> DefectReport:
    """Raises ValueError for a report that can't be planned (km outside the
    section) or doesn't say what was found."""
    check_km_range(request.section, request.km_from, request.km_to)
    defect_type = " ".join(request.defect_type.split())
    if not defect_type:
        raise ValueError("Say what the defect is")

    with _lock:
        data = _read(REPORTS_FILE, {"next_seq": 1, "reports": []})
        # A counter rather than len(reports), so a withdrawn report's id is
        # never handed to a different defect.
        seq = data["next_seq"]
        report = DefectReport(
            **request.model_dump(exclude={"defect_type"}),
            defect_type=defect_type,
            severity_code=severity_from_score(request.severity_score),
            report_id=f"{DEPARTMENT_TASK_ID_PREFIX[request.department]}-RPT-{seq:02d}",
            reported_at=now,
        )
        data["reports"].append(report.model_dump(mode="json"))
        data["next_seq"] = seq + 1
        _write(REPORTS_FILE, data)
    return report


def withdraw_report(report_id: str) -> bool:
    with _lock:
        data = _read(REPORTS_FILE, {"next_seq": 1, "reports": []})
        kept = [r for r in data["reports"] if r["report_id"] != report_id]
        if len(kept) == len(data["reports"]):
            return False
        data["reports"] = kept
        _write(REPORTS_FILE, data)
    return True


def reported_tasks(reports: list[DefectReport], reference_date: date) -> list[MaintenanceTask]:
    tasks = []
    for r in reports:
        raised = r.reported_at.date()
        due = raised + timedelta(days=DUE_DAYS_BY_SEVERITY[r.severity_code])
        tasks.append(
            MaintenanceTask(
                task_id=r.report_id,
                department=r.department,
                asset_id="REPORTED",
                section=r.section,
                km_range=(r.km_from, r.km_to),
                defect_type=r.defect_type,
                severity_code=r.severity_code,
                date_raised=raised,
                due_date=due,
                days_overdue=max(0, (reference_date - due).days),
                est_duration_min=r.est_duration_min,
                crew_required=0,  # crew is not enforced anywhere (known gap)
                block_type_required=r.block_type_required,
                data_source="reported",
            )
        )
    return tasks


# --- Control decisions -------------------------------------------------------


def list_decisions() -> list[BlockDecision]:
    return [BlockDecision(**d) for d in _read(DECISIONS_FILE, [])]


def record_decision(
    block: BlockOpportunity,
    request: BlockDecisionRequest,
    now: datetime,
    plan_days: tuple[date, date],
) -> BlockDecision:
    """Replaces any earlier decision on the same block. `block` must be the
    block as generated, so "granted late" always counts from the planned
    start. A reschedule must start on a day of the plan week (`plan_days`,
    first and last): the plan covers that week and nothing outside it.
    Raises ValueError for a decision that can't apply."""
    new_start = new_end = None
    if request.decision == "granted_late":
        if request.minutes_lost <= 0:
            raise ValueError("A late grant needs the minutes lost")
        if request.minutes_lost >= block.duration_min:
            raise ValueError(
                f"{block.block_id} is only {block.duration_min} min long; losing "
                f"{request.minutes_lost} min leaves nothing -- cancel it instead"
            )
    elif request.decision == "rescheduled":
        if request.new_start is None:
            raise ValueError("A reschedule needs the new start time")
        first, last = plan_days
        if not first <= request.new_start.date() <= last:
            raise ValueError(
                f"The plan covers {first:%a %d %b} to {last:%a %d %b}; "
                f"{request.new_start:%a %d %b} is outside it"
            )
        duration = request.duration_min or block.duration_min
        if request.new_start == block.start_time and duration == block.duration_min:
            raise ValueError(f"{block.block_id} is already planned for then")
        new_start, new_end = request.new_start, request.new_start + timedelta(minutes=duration)
    decision = BlockDecision(
        block_id=block.block_id,
        section=block.section,
        planned_start=block.start_time,
        planned_end=block.end_time,
        decision=request.decision,
        minutes_lost=request.minutes_lost if request.decision == "granted_late" else 0,
        decided_at=now,
        new_start=new_start,
        new_end=new_end,
    )
    with _lock:
        data = [d for d in _read(DECISIONS_FILE, []) if d["block_id"] != block.block_id]
        data.append(decision.model_dump(mode="json"))
        _write(DECISIONS_FILE, data)
    return decision


def clear_decision(block_id: str) -> bool:
    with _lock:
        data = _read(DECISIONS_FILE, [])
        kept = [d for d in data if d["block_id"] != block_id]
        if len(kept) == len(data):
            return False
        _write(DECISIONS_FILE, kept)
    return True


def control_disruptions(decisions: list[BlockDecision]) -> list[CancelBlock | CurtailBlock | MoveBlock]:
    """What the decisions mean for the plan. A plain grant changes nothing:
    it records that the block is going ahead, but does not lock the work
    in it (a later report or cancellation can still move that work)."""
    out: list[CancelBlock | CurtailBlock | MoveBlock] = []
    for d in decisions:
        if d.decision == "cancelled":
            out.append(CancelBlock(kind="cancel_block", block_id=d.block_id))
        elif d.decision == "granted_late":
            out.append(CurtailBlock(kind="curtail_block", block_id=d.block_id, minutes_lost=d.minutes_lost))
        elif d.decision == "rescheduled" and d.new_start and d.new_end:
            out.append(
                MoveBlock(
                    kind="move_block",
                    block_id=d.block_id,
                    new_start=d.new_start,
                    duration_min=int((d.new_end - d.new_start).total_seconds() // 60),
                )
            )
    return out
