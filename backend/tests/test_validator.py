from datetime import date, datetime

from app.models.block import BlockOpportunity
from app.models.task import MaintenanceTask
from app.scheduling.validator import summarize_checks, validate_plan


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


def test_valid_single_task_plan_has_no_violations():
    task = make_task()
    block = make_block()
    violations = validate_plan([task], [block], {task.task_id: block.block_id})
    assert violations == []


def test_unscheduled_task_has_no_violations():
    task = make_task()
    violations = validate_plan([task], [], {task.task_id: None})
    assert violations == []


def test_block_type_mismatch_flagged():
    task = make_task(block_type_required="power")
    block = make_block(block_type_possible="traffic")
    violations = validate_plan([task], [block], {task.task_id: block.block_id})
    assert any(v.rule == "block_type_match" for v in violations)


def test_capacity_overrun_flagged():
    t1 = make_task(task_id="t1", est_duration_min=150, km_range=(10.0, 10.5))
    t2 = make_task(task_id="t2", est_duration_min=150, km_range=(10.2, 10.6))
    block = make_block(duration_min=180)
    violations = validate_plan([t1, t2], [block], {"t1": block.block_id, "t2": block.block_id})
    assert any(v.rule == "capacity" for v in violations)


def test_traffic_and_power_block_allows_mixed_task_types():
    """The worked example scenario (spec section 5): a TRAFFIC-requiring
    task, a POWER-requiring task, and another TRAFFIC-requiring task all
    sharing one TRAFFIC_AND_POWER block. That block stops both traffic and
    isolates power, so this mix is safe and must NOT be flagged -- it's
    the exact outcome Stage B is supposed to produce."""
    power_task = make_task(task_id="power", block_type_required="power", km_range=(10.0, 10.5))
    traffic_task = make_task(task_id="traffic", block_type_required="traffic", km_range=(10.1, 10.4))
    block = make_block(block_type_possible="traffic_and_power", duration_min=300)
    violations = validate_plan(
        [power_task, traffic_task], [block],
        {"power": block.block_id, "traffic": block.block_id},
    )
    assert violations == []


def test_power_isolation_violation_for_non_power_task_in_pure_power_block():
    """Defense in depth: task_fits_block would never let a TRAFFIC-only
    task be individually assigned to a pure POWER block in real solver
    output, but the validator should independently catch it if a solver
    bug (or a hand-built assignment) ever produced this."""
    power_task = make_task(task_id="power", block_type_required="power", km_range=(10.0, 10.5))
    traffic_task = make_task(task_id="traffic", block_type_required="traffic", km_range=(10.1, 10.4))
    block = make_block(block_type_possible="power", duration_min=300)
    violations = validate_plan(
        [power_task, traffic_task], [block],
        {"power": block.block_id, "traffic": block.block_id},
    )
    assert any(v.rule == "power_isolation" for v in violations)


def test_power_isolation_allows_two_power_tasks_sharing():
    t1 = make_task(task_id="p1", block_type_required="power", km_range=(10.0, 10.5), est_duration_min=90)
    t2 = make_task(task_id="p2", block_type_required="power", km_range=(10.2, 10.6), est_duration_min=90)
    block = make_block(block_type_possible="power", duration_min=200)
    violations = validate_plan([t1, t2], [block], {"p1": block.block_id, "p2": block.block_id})
    assert not any(v.rule == "power_isolation" for v in violations)


def test_compatibility_violation_for_non_overlapping_km_ranges():
    t1 = make_task(task_id="t1", km_range=(10.0, 10.5), est_duration_min=60)
    t2 = make_task(task_id="t2", km_range=(50.0, 50.5), est_duration_min=60)
    block = make_block(duration_min=200)
    violations = validate_plan([t1, t2], [block], {"t1": block.block_id, "t2": block.block_id})
    assert any(v.rule == "compatibility" for v in violations)


def test_dependency_order_violation_when_dependency_scheduled_after():
    dep = make_task(task_id="dep", section="GHY-LMG")
    task = make_task(task_id="dependent", section="GHY-LMG", depends_on=["dep"])
    early_block = make_block(block_id="early", start_time=datetime(2026, 9, 8, 1, 0))
    late_block = make_block(block_id="late", start_time=datetime(2026, 9, 9, 1, 0))
    violations = validate_plan(
        [dep, task], [early_block, late_block],
        {"dependent": early_block.block_id, "dep": late_block.block_id},
    )
    assert any(v.rule == "dependency_order" for v in violations)


def test_dependency_order_violation_when_dependency_unscheduled():
    dep = make_task(task_id="dep")
    task = make_task(task_id="dependent", depends_on=["dep"])
    block = make_block()
    violations = validate_plan([dep, task], [block], {"dependent": block.block_id, "dep": None})
    assert any(v.rule == "dependency_order" for v in violations)


def test_dependency_order_satisfied_when_dependency_scheduled_earlier():
    dep = make_task(task_id="dep")
    task = make_task(task_id="dependent", depends_on=["dep"])
    early_block = make_block(block_id="early", start_time=datetime(2026, 9, 8, 1, 0))
    late_block = make_block(block_id="late", start_time=datetime(2026, 9, 9, 1, 0))
    violations = validate_plan(
        [dep, task], [early_block, late_block],
        {"dependent": late_block.block_id, "dep": early_block.block_id},
    )
    assert violations == []


def test_summary_reports_what_each_rule_examined():
    a = make_task(task_id="ENG-2026-00001", km_range=(10.0, 10.5), est_duration_min=60)
    b = make_task(task_id="ENG-2026-00002", km_range=(10.2, 10.8), est_duration_min=60)
    block = make_block(duration_min=180)
    assignments = {a.task_id: block.block_id, b.task_id: block.block_id}
    checks = {c.rule: c for c in summarize_checks([a, b], [block], assignments, [])}

    assert set(checks) == {
        "block_type_match", "capacity", "power_isolation",
        "compatibility", "dependency_order", "no_double_booking",
    }
    assert checks["block_type_match"].items_checked == 2
    assert checks["capacity"].items_checked == 1
    assert checks["compatibility"].items_checked == 1  # one pair shares the block
    assert checks["power_isolation"].items_checked == 0  # no POWER block used: vacuous
    assert checks["no_double_booking"].method == "structural"
    assert all(c.violations == 0 for c in checks.values())


def test_summary_counts_violations_per_rule():
    task = make_task(est_duration_min=240)
    block = make_block(duration_min=180)
    assignments = {task.task_id: block.block_id}
    violations = validate_plan([task], [block], assignments)
    checks = {c.rule: c for c in summarize_checks([task], [block], assignments, violations)}
    assert checks["capacity"].violations == 1
