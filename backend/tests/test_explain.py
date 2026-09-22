from datetime import date, datetime

from app.models.block import BlockOpportunity
from app.models.task import MaintenanceTask
from app.scheduling.explain import explain_plan
from app.scheduling.stage_a import solve_stage_a
from app.scheduling.stage_b import solve_stage_b

REFERENCE_DATE = date(2026, 9, 7)


def make_task(**overrides) -> MaintenanceTask:
    defaults = dict(
        task_id="ENG-2026-00001",
        department="Engineering",
        asset_id="TRK-SEC-001-KM0100",
        section="NDLS-GZB",
        km_range=(10.0, 10.5),
        defect_type="rail_fracture_risk",
        severity_code="B",
        date_raised=date(2026, 8, 1),
        due_date=date(2026, 9, 1),
        days_overdue=0,
        est_duration_min=120,
        crew_required=4,
        block_type_required="traffic",
        depends_on=[],
    )
    defaults.update(overrides)
    return MaintenanceTask(**defaults)


def make_block(**overrides) -> BlockOpportunity:
    defaults = dict(
        block_id="BLK-NDLS-GZB-0001",
        section="NDLS-GZB",
        start_time=datetime(2026, 9, 8, 1, 0),
        end_time=datetime(2026, 9, 8, 4, 0),
        duration_min=180,
        block_type_possible="traffic",
        expected_train_impact=0.3,
        goods_traffic_load=0.2,
    )
    defaults.update(overrides)
    return BlockOpportunity(**defaults)


def test_scheduled_task_reason_names_dominant_component():
    task = make_task(severity_code="C", days_overdue=0)  # low criticality/urgency
    block = make_block(expected_train_impact=0.9)  # availability impact dominates
    result = solve_stage_a([task], [block], REFERENCE_DATE)
    explanations = explain_plan([task], [block], result.assignments, result.compatible_blocks_by_task)
    exp = explanations[0]
    assert exp.scheduled is True
    assert "Scheduled into" in exp.reason
    assert "impact on train operations" in exp.reason


def test_scheduled_task_reason_names_safety_override():
    task = make_task(severity_code="A", days_overdue=10)
    block = make_block()
    result = solve_stage_a([task], [block], REFERENCE_DATE)
    explanations = explain_plan([task], [block], result.assignments, result.compatible_blocks_by_task)
    assert "safety-critical override" in explanations[0].reason


def test_merged_tasks_list_each_other_in_reason():
    eng = make_task(task_id="eng", block_type_required="traffic", est_duration_min=180, km_range=(100.0, 100.3))
    trd = make_task(task_id="trd", block_type_required="power", est_duration_min=120, km_range=(100.1, 100.4))
    snt = make_task(task_id="snt", block_type_required="traffic", est_duration_min=90, km_range=(100.2, 100.5))
    combined = make_block(block_id="combined", block_type_possible="traffic_and_power", duration_min=400)

    result = solve_stage_b([eng, trd, snt], [combined], REFERENCE_DATE)
    explanations = {
        e.task_id: e for e in explain_plan([eng, trd, snt], [combined], result.assignments, result.compatible_blocks_by_task)
    }

    assert "trd" in explanations["eng"].reason and "snt" in explanations["eng"].reason
    assert "eng" in explanations["trd"].reason and "snt" in explanations["trd"].reason
    assert "shares this block with" in explanations["eng"].reason.lower()


def test_unscheduled_task_no_compatible_block():
    task = make_task(block_type_required="power")
    block = make_block(block_type_possible="traffic")
    result = solve_stage_a([task], [block], REFERENCE_DATE)
    explanations = explain_plan([task], [block], result.assignments, result.compatible_blocks_by_task)
    assert explanations[0].scheduled is False
    assert "no block this week offers" in explanations[0].reason


def test_unscheduled_task_dependency_unmet():
    dep = make_task(task_id="dep", block_type_required="power")  # can never be scheduled
    dependent = make_task(task_id="dependent", block_type_required="traffic", depends_on=["dep"])
    block = make_block(block_type_possible="traffic")
    result = solve_stage_a([dep, dependent], [block], REFERENCE_DATE)
    explanations = {
        e.task_id: e for e in explain_plan([dep, dependent], [block], result.assignments, result.compatible_blocks_by_task)
    }
    assert "depends on dep" in explanations["dependent"].reason


def test_unscheduled_task_lost_to_higher_priority_competitor():
    high = make_task(task_id="high", severity_code="A", days_overdue=20)
    low = make_task(task_id="low", severity_code="C", days_overdue=0)
    block = make_block()  # only one block, only one task can win it
    result = solve_stage_a([high, low], [block], REFERENCE_DATE)
    explanations = {
        e.task_id: e for e in explain_plan([high, low], [block], result.assignments, result.compatible_blocks_by_task)
    }
    assert explanations["low"].scheduled is False
    assert "claimed by higher-priority tasks" in explanations["low"].reason
    assert "high" in explanations["low"].reason


def test_every_task_gets_a_nonempty_reason_on_generated_data():
    import random

    from app.datagen.generate import generate_blocks, generate_tasks, next_monday
    from app.datagen.reference_data import SECTIONS

    rng = random.Random(1)
    all_tasks = generate_tasks(SECTIONS, 45, rng, REFERENCE_DATE)
    week_start = next_monday(REFERENCE_DATE)
    all_blocks = generate_blocks(SECTIONS, 20, rng, week_start)

    for section_name, _, _ in SECTIONS:
        tasks = [t for t in all_tasks if t.section == section_name]
        blocks = [b for b in all_blocks if b.section == section_name]
        result = solve_stage_b(tasks, blocks, REFERENCE_DATE)
        explanations = explain_plan(tasks, blocks, result.assignments, result.compatible_blocks_by_task)
        assert len(explanations) == len(tasks)
        for exp in explanations:
            assert exp.reason.strip() != ""
            assert exp.scheduled == (result.assignments[exp.task_id] is not None)
