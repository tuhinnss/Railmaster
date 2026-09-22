from datetime import date, datetime

from app.models.block import BlockOpportunity
from app.models.task import MaintenanceTask
from app.scheduling.stage_a import solve_stage_a
from app.scheduling.stage_b import solve_stage_b
from app.scheduling.validator import validate_plan

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


def test_rejects_multi_section_input():
    task = make_task(section="NDLS-GZB")
    other_section_block = make_block(section="GZB-SRE")
    try:
        solve_stage_b([task], [other_section_block], REFERENCE_DATE)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_worked_example_merges_three_tasks_into_one_block():
    """Spec section 5's worked example: a 3h Engineering task needing a
    traffic block, a 2h TRD task needing a power block on the same
    feeding section, and a 1.5h S&T task needing a traffic block with no
    conflict between them, should all land in ONE combined block rather
    than three separate ones. (The spec's prose rounds the combined block
    to "~4h"; the three durations actually sum to 6.5h, so the fixture
    block here is sized to that literal sum -- the merge outcome is what
    this test checks, not the approximate figure.)"""
    eng = make_task(
        task_id="eng", department="Engineering", block_type_required="traffic",
        est_duration_min=180, km_range=(100.0, 100.3),
    )
    trd = make_task(
        task_id="trd", department="TRD", block_type_required="power",
        est_duration_min=120, km_range=(100.1, 100.4),
    )
    snt = make_task(
        task_id="snt", department="S&T", block_type_required="traffic",
        est_duration_min=90, km_range=(100.2, 100.5),
    )
    combined_block = make_block(block_id="combined", block_type_possible="traffic_and_power", duration_min=400)

    result = solve_stage_b([eng, trd, snt], [combined_block], REFERENCE_DATE)

    assert result.assignments["eng"] == "combined"
    assert result.assignments["trd"] == "combined"
    assert result.assignments["snt"] == "combined"
    assert result.blocks_opened == ["combined"]

    violations = validate_plan([eng, trd, snt], [combined_block], result.assignments)
    assert violations == []


def test_stage_b_prefers_merging_over_separate_blocks_when_both_feasible():
    """The real test of the beta/gamma consolidation incentive: given a
    choice between one combined block and three dedicated ones (equally
    early, equally capable of scheduling every task), Stage B must pick
    the combined block -- that's the 'blocks saved' mechanism."""
    eng = make_task(task_id="eng", block_type_required="traffic", est_duration_min=180, km_range=(100.0, 100.3))
    trd = make_task(task_id="trd", block_type_required="power", est_duration_min=120, km_range=(100.1, 100.4))
    snt = make_task(task_id="snt", block_type_required="traffic", est_duration_min=90, km_range=(100.2, 100.5))

    combined = make_block(block_id="combined", block_type_possible="traffic_and_power", duration_min=400)
    eng_only = make_block(block_id="eng_only", block_type_possible="traffic", duration_min=200)
    trd_only = make_block(block_id="trd_only", block_type_possible="power", duration_min=150)
    snt_only = make_block(block_id="snt_only", block_type_possible="traffic", duration_min=150)

    result = solve_stage_b([eng, trd, snt], [combined, eng_only, trd_only, snt_only], REFERENCE_DATE)

    assert set(result.blocks_opened) == {"combined"}
    assert result.assignments["eng"] == "combined"
    assert result.assignments["trd"] == "combined"
    assert result.assignments["snt"] == "combined"


def test_capacity_prevents_overpacking_a_single_block():
    t1 = make_task(task_id="t1", est_duration_min=150, km_range=(10.0, 10.5))
    t2 = make_task(task_id="t2", est_duration_min=150, km_range=(10.2, 10.6))
    block = make_block(duration_min=200)  # 150+150=300 > 200, can't both fit
    result = solve_stage_b([t1, t2], [block], REFERENCE_DATE)
    scheduled = [tid for tid, b in result.assignments.items() if b is not None]
    assert len(scheduled) <= 1
    violations = validate_plan([t1, t2], [block], result.assignments)
    assert violations == []


def test_non_overlapping_km_ranges_not_merged_even_if_capacity_allows():
    t1 = make_task(task_id="t1", km_range=(10.0, 10.5), est_duration_min=60)
    t2 = make_task(task_id="t2", km_range=(90.0, 90.5), est_duration_min=60)
    block = make_block(duration_min=200)  # plenty of capacity for both
    result = solve_stage_b([t1, t2], [block], REFERENCE_DATE)
    both_share_block = (
        result.assignments["t1"] is not None and result.assignments["t1"] == result.assignments["t2"]
    )
    assert not both_share_block
    violations = validate_plan([t1, t2], [block], result.assignments)
    assert violations == []


def test_dependency_order_respected_with_merging_available():
    dep = make_task(task_id="dep", est_duration_min=60, km_range=(10.0, 10.5))
    dependent = make_task(task_id="dependent", est_duration_min=60, km_range=(10.1, 10.4), depends_on=["dep"])
    early = make_block(block_id="early", start_time=datetime(2026, 9, 8, 1, 0), duration_min=200)
    late = make_block(block_id="late", start_time=datetime(2026, 9, 9, 1, 0), duration_min=200)
    result = solve_stage_b([dep, dependent], [early, late], REFERENCE_DATE)
    assert result.assignments["dep"] is not None
    assert result.assignments["dependent"] is not None
    dep_block = early if result.assignments["dep"] == "early" else late
    dependent_block = early if result.assignments["dependent"] == "early" else late
    assert dep_block.start_time <= dependent_block.start_time


def test_stage_b_schedules_at_least_as_many_tasks_and_opens_no_more_blocks_than_stage_a():
    """End-to-end comparison on real generated data: Stage B should never
    do worse than Stage A at getting tasks scheduled, and should use no
    more blocks to do it -- ideally fewer, which is the 'blocks saved'
    number for the demo."""
    import random

    from app.datagen.generate import generate_blocks, generate_tasks, next_monday
    from app.datagen.reference_data import SECTIONS

    rng = random.Random(1)
    all_tasks = generate_tasks(SECTIONS, 45, rng, REFERENCE_DATE)
    week_start = next_monday(REFERENCE_DATE)
    all_blocks = generate_blocks(SECTIONS, 20, rng, week_start)

    any_blocks_saved = False
    for section_name, _, _ in SECTIONS:
        tasks = [t for t in all_tasks if t.section == section_name]
        blocks = [b for b in all_blocks if b.section == section_name]

        result_a = solve_stage_a(tasks, blocks, REFERENCE_DATE)
        result_b = solve_stage_b(tasks, blocks, REFERENCE_DATE)

        scheduled_a = sum(1 for v in result_a.assignments.values() if v is not None)
        scheduled_b = sum(1 for v in result_b.assignments.values() if v is not None)
        blocks_used_a = len({v for v in result_a.assignments.values() if v is not None})

        assert scheduled_b >= scheduled_a, section_name
        assert len(result_b.blocks_opened) <= blocks_used_a, section_name
        if len(result_b.blocks_opened) < blocks_used_a:
            any_blocks_saved = True

        violations = validate_plan(tasks, blocks, result_b.assignments)
        assert violations == [], f"{section_name}: {violations}"

    assert any_blocks_saved, "expected merging to save at least one block somewhere in the dataset"
