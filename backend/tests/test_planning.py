from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.planning import apply_disruptions, plan_all, plan_fingerprint, run_what_if
from app.schemas.plan import CancelBlock, CurtailBlock, UrgentDefect
from tests.test_stage_b import make_block, make_task

REFERENCE_DATE = date(2026, 9, 7)


def small_world():
    """Two tasks competing for a single 180-min traffic block plus a spare
    90-min block on GHY-LMG: enough for a disruption to visibly move work."""
    tasks = [
        make_task(task_id="ENG-2026-00001", km_range=(10.0, 10.5), est_duration_min=120, severity_code="B"),
        make_task(task_id="ENG-2026-00002", km_range=(40.0, 40.5), est_duration_min=60, severity_code="C"),
    ]
    blocks = [
        make_block(block_id="BLK-GHY-LMG-0001", duration_min=180),
        make_block(
            block_id="BLK-GHY-LMG-0002",
            start_time=datetime(2026, 9, 9, 1, 0),
            end_time=datetime(2026, 9, 9, 2, 30),
            duration_min=90,
        ),
    ]
    return tasks, blocks


def test_fingerprint_is_stable_and_tracks_the_plan():
    tasks, blocks = small_world()
    first = [r.result for r in plan_all(tasks, blocks, REFERENCE_DATE).values()]
    second = [r.result for r in plan_all(tasks, blocks, REFERENCE_DATE).values()]
    assert plan_fingerprint(REFERENCE_DATE, first) == plan_fingerprint(REFERENCE_DATE, second)

    fewer_blocks = [r.result for r in plan_all(tasks, blocks[:1], REFERENCE_DATE).values()]
    assert plan_fingerprint(REFERENCE_DATE, fewer_blocks) != plan_fingerprint(REFERENCE_DATE, first)


def test_disruptions_never_mutate_the_loaded_data():
    tasks, blocks = small_world()
    original_start = blocks[0].start_time
    apply_disruptions(
        tasks,
        blocks,
        [
            CurtailBlock(kind="curtail_block", block_id="BLK-GHY-LMG-0001", minutes_lost=30),
            CancelBlock(kind="cancel_block", block_id="BLK-GHY-LMG-0002"),
        ],
        REFERENCE_DATE,
    )
    assert len(blocks) == 2
    assert blocks[0].start_time == original_start
    assert blocks[0].duration_min == 180


def test_curtailed_block_starts_later_and_ends_on_time():
    tasks, blocks = small_world()
    _, new_blocks, applied, affected, _ = apply_disruptions(
        tasks, blocks, [CurtailBlock(kind="curtail_block", block_id="BLK-GHY-LMG-0001", minutes_lost=60)], REFERENCE_DATE
    )
    curtailed = next(b for b in new_blocks if b.block_id == "BLK-GHY-LMG-0001")
    assert curtailed.duration_min == 120
    assert curtailed.start_time == datetime(2026, 9, 8, 2, 0)
    assert curtailed.end_time == blocks[0].end_time
    assert affected == {"GHY-LMG"}
    assert len(applied) == 1


def test_cancelling_a_block_reports_the_resulting_moves():
    tasks, blocks = small_world()
    result = run_what_if(
        tasks, blocks, [CancelBlock(kind="cancel_block", block_id="BLK-GHY-LMG-0001")], REFERENCE_DATE
    )
    after = {t.task_id: t.block_id for t in result.sections[0].after.tasks}
    assert "BLK-GHY-LMG-0001" not in after.values()
    # The 120-min task can't fit the remaining 90-min block, so it drops.
    changes = {c.task_id: c.change for c in result.changes}
    assert changes["ENG-2026-00001"] == "dropped"
    assert result.replan_seconds >= 0


def test_urgent_defect_is_injected_and_planned():
    tasks, blocks = small_world()
    result = run_what_if(
        tasks,
        blocks,
        [
            UrgentDefect(
                kind="urgent_defect",
                section="GHY-LMG",
                department="Engineering",
                defect_type="rail_fracture",
                km_from=12.0,
                km_to=12.3,
                est_duration_min=60,
                block_type_required="traffic",
            )
        ],
        REFERENCE_DATE,
    )
    new = [c for c in result.changes if c.change in ("new_scheduled", "new_unscheduled")]
    assert [c.task_id for c in new] == ["ENG-WHATIF-01"]
    assert result.sections[0].after.task_count == result.sections[0].before.task_count + 1


def test_changes_only_list_tasks_the_disruption_touched():
    """With the solver deterministic and the baseline preferred on ties,
    a disruption on one block must not reshuffle unrelated work."""
    tasks, blocks = small_world()
    result = run_what_if(
        tasks,
        blocks,
        [CurtailBlock(kind="curtail_block", block_id="BLK-GHY-LMG-0001", minutes_lost=30)],
        REFERENCE_DATE,
    )
    assert result.changes == []  # 150 min left still fits the 120-min task


@pytest.mark.parametrize(
    "disruption",
    [
        CancelBlock(kind="cancel_block", block_id="BLK-NOPE"),
        CurtailBlock(kind="curtail_block", block_id="BLK-GHY-LMG-0002", minutes_lost=90),
        UrgentDefect(
            kind="urgent_defect",
            section="GHY-LMG",
            department="TRD",
            defect_type="feeder_fault",
            km_from=170.0,
            km_to=190.0,  # runs past the section end
            est_duration_min=60,
            block_type_required="power",
        ),
    ],
)
def test_impossible_disruptions_are_rejected(disruption):
    tasks, blocks = small_world()
    with pytest.raises(ValueError):
        apply_disruptions(tasks, blocks, [disruption], REFERENCE_DATE)


client = TestClient(app)


def test_weekly_plan_carries_fingerprint_and_safety_report():
    body = client.get("/api/plans/WEEKLY").json()
    assert len(body["fingerprint"]) == 64
    for section in body["sections"]:
        assert len(section["safety_checks"]) == 6
        assert all(check["violations"] == 0 for check in section["safety_checks"])
        for block in section["blocks"]:
            assert block["used_min"] <= block["duration_min"]


def test_what_if_endpoint_validates_input():
    assert client.post("/api/plans/WEEKLY/what-if", json={"disruptions": []}).status_code == 422
    unknown = client.post(
        "/api/plans/WEEKLY/what-if", json={"disruptions": [{"kind": "cancel_block", "block_id": "BLK-NOPE"}]}
    )
    assert unknown.status_code == 422
    assert "BLK-NOPE" in unknown.json()["detail"]
