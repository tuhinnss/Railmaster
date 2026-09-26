from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.operations import (
    add_report,
    clear_decision,
    control_disruptions,
    list_decisions,
    list_reports,
    record_decision,
    reported_tasks,
    withdraw_report,
)
from app.planning import plan_all, plan_current, run_what_if
from app.schemas.operations import BlockDecisionRequest, DefectReportRequest
from app.schemas.plan import CancelBlock, CurtailBlock, MoveBlock
from tests.test_planning import REFERENCE_DATE, small_world

NOW = datetime(2026, 9, 7, 14, 30)
WEEK = (date(2026, 9, 8), date(2026, 9, 14))  # small_world's blocks fall on the 8th and 9th


def report_request(**overrides) -> DefectReportRequest:
    fields = dict(
        section="GHY-LMG",
        department="Engineering",
        defect_type="joint_wear",
        km_from=60.0,
        km_to=60.4,
        severity_code="B",
        est_duration_min=60,
        block_type_required="traffic",
    )
    fields.update(overrides)
    return DefectReportRequest(**fields)


# --- Store -------------------------------------------------------------------


def test_reports_persist_and_ids_are_never_reused():
    first = add_report(report_request(), NOW)
    second = add_report(report_request(department="TRD", defect_type="feeder_fault", block_type_required="power"), NOW)
    assert (first.report_id, second.report_id) == ("ENG-RPT-01", "TRD-RPT-02")
    assert [r.report_id for r in list_reports()] == ["ENG-RPT-01", "TRD-RPT-02"]

    assert withdraw_report("TRD-RPT-02")
    assert not withdraw_report("TRD-RPT-02")
    # The withdrawn id is not handed out again.
    assert add_report(report_request(), NOW).report_id == "ENG-RPT-03"


@pytest.mark.parametrize(
    "overrides",
    [
        {"km_from": 170.0, "km_to": 190.0},  # runs past the section end
        {"section": "NOPE-NOPE"},
        {"defect_type": "   "},  # says nothing about what was found
    ],
)
def test_unplannable_reports_are_rejected(overrides):
    with pytest.raises(ValueError):
        add_report(report_request(**overrides), NOW)
    assert list_reports() == []


def test_the_defect_is_free_text_kept_as_typed():
    report = add_report(report_request(department="TRD", defect_type="  Dropper   snapped near OHE mast 61/4 "), NOW)
    assert report.defect_type == "Dropper snapped near OHE mast 61/4"


def test_reported_defects_become_labelled_tasks_with_severity_due_dates():
    add_report(report_request(severity_code="A"), NOW)
    add_report(report_request(severity_code="C"), NOW)
    a, c = reported_tasks(list_reports(), date(2026, 9, 10))
    assert a.data_source == c.data_source == "reported"
    assert a.date_raised == date(2026, 9, 7)
    assert a.days_overdue == 3  # severity A is due the day it is found
    assert c.days_overdue == 0  # severity C has 30 days


def test_a_new_decision_replaces_the_old_one_and_counts_from_the_planned_start():
    _, blocks = small_world()
    block = blocks[0]
    record_decision(block, BlockDecisionRequest(decision="granted_late", minutes_lost=30), NOW, WEEK)
    record_decision(block, BlockDecisionRequest(decision="granted_late", minutes_lost=45), NOW, WEEK)
    [decision] = list_decisions()
    assert decision.minutes_lost == 45
    assert decision.planned_start == block.start_time
    assert control_disruptions(list_decisions()) == [
        CurtailBlock(kind="curtail_block", block_id=block.block_id, minutes_lost=45)
    ]

    record_decision(block, BlockDecisionRequest(decision="granted", minutes_lost=45), NOW, WEEK)
    assert list_decisions()[0].minutes_lost == 0  # only a late grant keeps minutes
    assert control_disruptions(list_decisions()) == []  # a plain grant changes nothing
    assert clear_decision(block.block_id)
    assert list_decisions() == []


def test_a_late_grant_must_leave_some_block():
    _, blocks = small_world()
    with pytest.raises(ValueError):
        record_decision(blocks[1], BlockDecisionRequest(decision="granted_late", minutes_lost=90), NOW, WEEK)
    with pytest.raises(ValueError):
        record_decision(blocks[1], BlockDecisionRequest(decision="granted_late", minutes_lost=0), NOW, WEEK)


def test_a_reschedule_moves_the_block_and_can_change_its_length():
    _, blocks = small_world()
    block = blocks[0]
    decision = record_decision(
        block,
        BlockDecisionRequest(decision="rescheduled", new_start=datetime(2026, 9, 11, 23, 0), duration_min=240),
        NOW,
        WEEK,
    )
    assert decision.planned_start == block.start_time
    assert (decision.new_start, decision.new_end) == (datetime(2026, 9, 11, 23, 0), datetime(2026, 9, 12, 3, 0))
    assert control_disruptions(list_decisions()) == [
        MoveBlock(kind="move_block", block_id=block.block_id, new_start=datetime(2026, 9, 11, 23, 0), duration_min=240)
    ]


@pytest.mark.parametrize(
    "request_fields",
    [
        {"decision": "rescheduled"},  # no new time
        {"decision": "rescheduled", "new_start": datetime(2026, 9, 20, 1, 0)},  # outside the plan week
        {"decision": "rescheduled", "new_start": datetime(2026, 9, 8, 1, 0)},  # where it already is
    ],
)
def test_impossible_reschedules_are_rejected(request_fields):
    _, blocks = small_world()
    with pytest.raises(ValueError):
        record_decision(blocks[0], BlockDecisionRequest(**request_fields), NOW, WEEK)
    assert list_decisions() == []


# --- The plan as it stands ---------------------------------------------------


def test_with_nothing_reported_or_decided_the_plan_is_the_fixture_plan():
    tasks, blocks = small_world()
    current = plan_current(tasks, blocks, [], [], REFERENCE_DATE)
    fixture = plan_all(tasks, blocks, REFERENCE_DATE)
    assert current.runs["GHY-LMG"].assignments == fixture["GHY-LMG"].assignments


def test_a_reported_defect_is_planned_and_labelled():
    tasks, blocks = small_world()
    add_report(report_request(km_from=10.2, km_to=10.4, est_duration_min=30), NOW)
    current = plan_current(tasks, blocks, reported_tasks(list_reports(), REFERENCE_DATE), [], REFERENCE_DATE)
    summary = {t.task_id: t for t in current.runs["GHY-LMG"].result.tasks}
    assert summary["ENG-RPT-01"].data_source == "reported"
    assert summary["ENG-2026-00001"].data_source == "synthetic"
    assert summary["ENG-RPT-01"].scheduled


def test_a_cancelled_block_leaves_the_plan_and_only_its_work_moves():
    tasks, blocks = small_world()
    fixture = plan_all(tasks, blocks, REFERENCE_DATE)["GHY-LMG"].assignments
    cancelled = next(b for b in set(fixture.values()) if b is not None)

    current = plan_current(
        tasks, blocks, [], [CancelBlock(kind="cancel_block", block_id=cancelled)], REFERENCE_DATE
    )
    after = current.runs["GHY-LMG"].assignments
    assert cancelled not in after.values()
    assert all(b.block_id != cancelled for b in current.blocks)
    for task_id, block_id in fixture.items():
        if block_id != cancelled:
            assert after[task_id] == block_id


def test_a_moved_block_is_planned_at_its_new_time_and_drops_any_real_data_claim():
    tasks, blocks = small_world()
    blocks[0].data_source = "ntes_live"
    move = MoveBlock(kind="move_block", block_id="BLK-GHY-LMG-0001", new_start=datetime(2026, 9, 10, 23, 0))
    current = plan_current(tasks, blocks, [], [move], REFERENCE_DATE)
    moved = next(b for b in current.blocks if b.block_id == "BLK-GHY-LMG-0001")
    assert moved.start_time == datetime(2026, 9, 10, 23, 0)
    assert moved.duration_min == 180 and moved.end_time == datetime(2026, 9, 11, 2, 0)
    assert moved.data_source == "synthetic"  # the NTES figure was for the old slot
    assert blocks[0].start_time != moved.start_time  # the loaded data is untouched
    planned = {b.block_id: b for b in current.runs["GHY-LMG"].result.blocks}
    assert planned["BLK-GHY-LMG-0001"].start_time == datetime(2026, 9, 10, 23, 0)


def test_a_decision_on_a_block_that_no_longer_exists_is_skipped():
    tasks, blocks = small_world()
    current = plan_current(tasks, blocks, [], [CancelBlock(kind="cancel_block", block_id="BLK-GONE")], REFERENCE_DATE)
    assert len(current.blocks) == 2


def test_what_if_starts_from_the_current_plan():
    tasks, blocks = small_world()
    current = plan_current(
        tasks, blocks, [], [CurtailBlock(kind="curtail_block", block_id="BLK-GHY-LMG-0001", minutes_lost=30)], REFERENCE_DATE
    )
    result = run_what_if(
        current.tasks,
        current.blocks,
        [CancelBlock(kind="cancel_block", block_id="BLK-GHY-LMG-0002")],
        REFERENCE_DATE,
        baseline_runs=current.runs,
    )
    assert result.sections[0].before == current.runs["GHY-LMG"].result


# --- API ---------------------------------------------------------------------

client = TestClient(app)


def _plan_tasks():
    body = client.get("/api/plans/WEEKLY").json()
    return {t["task_id"]: t for s in body["sections"] for t in s["tasks"]}, body


def test_report_endpoint_round_trip():
    payload = report_request(section="NDLS-GZB", km_from=5.0, km_to=5.2).model_dump(mode="json")
    created = client.post("/api/operations/reports", json=payload)
    assert created.status_code == 201
    report_id = created.json()["report_id"]

    tasks, _ = _plan_tasks()
    assert tasks[report_id]["data_source"] == "reported"
    assert tasks[report_id]["section"] == "NDLS-GZB"

    assert client.delete(f"/api/operations/reports/{report_id}").status_code == 204
    assert client.delete(f"/api/operations/reports/{report_id}").status_code == 404
    tasks, _ = _plan_tasks()
    assert report_id not in tasks


def test_report_endpoint_rejects_a_bad_range_with_a_reason():
    payload = report_request(km_from=5.0, km_to=4.0).model_dump(mode="json")
    response = client.post("/api/operations/reports", json=payload)
    assert response.status_code == 422
    assert "km" in response.json()["detail"]


def test_cancelling_a_planned_block_through_the_api_and_undoing_it():
    _, body = _plan_tasks()
    section = body["sections"][0]
    block_id = section["blocks"][0]["block_id"]

    response = client.put(f"/api/operations/decisions/{block_id}", json={"decision": "cancelled"})
    assert response.status_code == 200
    _, after = _plan_tasks()
    assert block_id not in {b["block_id"] for s in after["sections"] for b in s["blocks"]}
    assert after["fingerprint"] != body["fingerprint"]

    assert client.delete(f"/api/operations/decisions/{block_id}").status_code == 204
    _, undone = _plan_tasks()
    assert undone["fingerprint"] == body["fingerprint"]


def test_rescheduling_through_the_api_and_undoing_it():
    _, body = _plan_tasks()
    block = body["sections"][0]["blocks"][0]
    start = datetime.fromisoformat(block["start_time"])
    new_start = start.replace(hour=23, minute=0) if start.hour != 23 else start.replace(hour=22, minute=0)

    response = client.put(
        f"/api/operations/decisions/{block['block_id']}",
        json={"decision": "rescheduled", "new_start": new_start.isoformat()},
    )
    assert response.status_code == 200
    _, after = _plan_tasks()
    moved = [b for s in after["sections"] for b in s["blocks"] if b["block_id"] == block["block_id"]]
    # Still in use and at its new time, or dropped because nothing fits there.
    assert all(datetime.fromisoformat(b["start_time"]) == new_start for b in moved)
    assert after["fingerprint"] != body["fingerprint"]

    far = client.put(
        f"/api/operations/decisions/{block['block_id']}",
        json={"decision": "rescheduled", "new_start": "2030-01-01T23:00:00"},
    )
    assert far.status_code == 422
    assert "outside" in far.json()["detail"]

    assert client.delete(f"/api/operations/decisions/{block['block_id']}").status_code == 204
    _, undone = _plan_tasks()
    assert undone["fingerprint"] == body["fingerprint"]


def test_decision_endpoint_validates_input():
    assert client.put("/api/operations/decisions/BLK-NOPE", json={"decision": "granted"}).status_code == 404
    _, body = _plan_tasks()
    block = body["sections"][0]["blocks"][0]
    too_late = client.put(
        f"/api/operations/decisions/{block['block_id']}",
        json={"decision": "granted_late", "minutes_lost": block["duration_min"]},
    )
    assert too_late.status_code == 422
    assert client.delete("/api/operations/decisions/BLK-NOPE").status_code == 404
