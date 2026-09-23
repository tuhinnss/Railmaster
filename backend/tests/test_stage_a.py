from datetime import date, datetime

from app.models.block import BlockOpportunity
from app.models.task import MaintenanceTask
from app.scheduling.stage_a import solve_stage_a
from app.scheduling.validator import validate_plan

REFERENCE_DATE = date(2026, 9, 7)


def make_task(**overrides) -> MaintenanceTask:
    defaults = dict(
        task_id="ENG-2026-00001",
        department="Engineering",
        asset_id="TRK-SEC-001-KM0100",
        section="GHY-LMG",
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
        block_id="BLK-GHY-LMG-0001",
        section="GHY-LMG",
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
    task = make_task(section="GHY-LMG")
    other_section_block = make_block(section="LMG-RNY")
    try:
        solve_stage_a([task], [other_section_block], REFERENCE_DATE)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_schedules_single_task_to_only_compatible_block():
    task = make_task()
    block = make_block()
    result = solve_stage_a([task], [block], REFERENCE_DATE)
    assert result.assignments[task.task_id] == block.block_id
    assert result.solver_status in ("OPTIMAL", "FEASIBLE")


def test_prefers_earlier_block_when_multiple_compatible():
    task = make_task()
    early = make_block(block_id="early", start_time=datetime(2026, 9, 8, 1, 0))
    late = make_block(block_id="late", start_time=datetime(2026, 9, 12, 1, 0))
    result = solve_stage_a([task], [late, early], REFERENCE_DATE)
    assert result.assignments[task.task_id] == "early"


def test_leaves_task_unscheduled_when_no_compatible_block():
    task = make_task(block_type_required="power")
    block = make_block(block_type_possible="traffic")
    result = solve_stage_a([task], [block], REFERENCE_DATE)
    assert result.assignments[task.task_id] is None


def test_higher_priority_task_wins_scarce_block():
    high = make_task(task_id="high", severity_code="A", days_overdue=20)
    low = make_task(task_id="low", severity_code="C", days_overdue=0)
    block = make_block()  # only one block, only one can be scheduled
    result = solve_stage_a([high, low], [block], REFERENCE_DATE)
    assert result.assignments["high"] == block.block_id
    assert result.assignments["low"] is None


def test_stage_a_does_not_merge_tasks_into_one_block():
    """Contrast case for Stage B: even when a single block could fit all
    three tasks by duration, Stage A must not put more than one task in it."""
    eng = make_task(task_id="eng", block_type_required="traffic", est_duration_min=180)
    trd = make_task(task_id="trd", block_type_required="power", est_duration_min=120)
    snt = make_task(task_id="snt", block_type_required="traffic", est_duration_min=90)
    combined_block = make_block(block_id="combined", block_type_possible="traffic_and_power", duration_min=400)

    result = solve_stage_a([eng, trd, snt], [combined_block], REFERENCE_DATE)
    scheduled = [t for t, b in result.assignments.items() if b is not None]
    assert len(scheduled) <= 1


def test_dependency_respected_dep_scheduled_before_dependent():
    dep = make_task(task_id="dep", est_duration_min=60)
    dependent = make_task(task_id="dependent", est_duration_min=60, depends_on=["dep"])
    early = make_block(block_id="early", start_time=datetime(2026, 9, 8, 1, 0))
    late = make_block(block_id="late", start_time=datetime(2026, 9, 9, 1, 0))
    result = solve_stage_a([dep, dependent], [early, late], REFERENCE_DATE)
    assert result.assignments["dep"] is not None
    assert result.assignments["dependent"] is not None
    dep_block = early if result.assignments["dep"] == "early" else late
    dependent_block = early if result.assignments["dependent"] == "early" else late
    assert dep_block.start_time <= dependent_block.start_time


def test_dependent_unscheduled_when_dependency_has_no_compatible_block():
    dep = make_task(task_id="dep", block_type_required="power")
    dependent = make_task(task_id="dependent", block_type_required="traffic", depends_on=["dep"])
    block = make_block(block_type_possible="traffic")  # dep can never be scheduled here
    result = solve_stage_a([dep, dependent], [block], REFERENCE_DATE)
    assert result.assignments["dependent"] is None


def test_stage_a_output_never_violates_safety_rules_on_generated_data():
    """Generate fresh (not the checked-out data/synthetic/ files, which may
    not exist in a clean checkout) fixture data and confirm Stage A's
    output is always safety-clean, for every section."""
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
        result = solve_stage_a(tasks, blocks, REFERENCE_DATE)
        violations = validate_plan(tasks, blocks, result.assignments)
        assert violations == [], f"{section_name}: {violations}"
