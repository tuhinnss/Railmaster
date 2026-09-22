from datetime import date, datetime

from app.models.block import BlockOpportunity
from app.models.task import MaintenanceTask
from app.scheduling.config import PriorityWeights
from app.scheduling.prioritizer import CRITICALITY_BY_SEVERITY, rank_tasks, score_task


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


def test_criticality_mapping():
    assert CRITICALITY_BY_SEVERITY["A"] == 1.0
    assert CRITICALITY_BY_SEVERITY["B"] == 0.6
    assert CRITICALITY_BY_SEVERITY["C"] == 0.3


def test_urgency_clips_at_30_days_overdue():
    task = make_task(severity_code="B", days_overdue=90)
    breakdown = score_task(task, blocks=[])
    assert breakdown.urgency == 1.0


def test_urgency_scales_linearly_before_clip():
    task = make_task(severity_code="B", days_overdue=15)
    breakdown = score_task(task, blocks=[])
    assert breakdown.urgency == 0.5


def test_availability_impact_uses_best_compatible_block_only():
    task = make_task(section="NDLS-GZB", block_type_required="traffic")
    blocks = [
        make_block(block_id="incompatible", block_type_possible="power", expected_train_impact=0.9),
        make_block(block_id="compatible-low", block_type_possible="traffic", expected_train_impact=0.2),
        make_block(block_id="compatible-high", block_type_possible="traffic", expected_train_impact=0.6),
    ]
    breakdown = score_task(task, blocks)
    assert breakdown.availability_impact == 0.6


def test_availability_impact_zero_with_no_compatible_blocks():
    task = make_task()
    breakdown = score_task(task, blocks=[])
    assert breakdown.availability_impact == 0.0


def test_score_is_weighted_sum():
    task = make_task(severity_code="B", days_overdue=15)
    blocks = [make_block(expected_train_impact=0.5)]
    weights = PriorityWeights(criticality=0.5, urgency=0.3, availability_impact=0.2)
    breakdown = score_task(task, blocks, weights)
    expected = 0.5 * 0.6 + 0.3 * 0.5 + 0.2 * 0.5
    assert abs(breakdown.score - expected) < 1e-9


def test_safety_override_flagged_for_overdue_severity_a():
    task = make_task(severity_code="A", days_overdue=5)
    breakdown = score_task(task, blocks=[])
    assert breakdown.safety_override is True


def test_safety_override_not_flagged_for_severity_a_not_overdue():
    task = make_task(severity_code="A", days_overdue=0)
    breakdown = score_task(task, blocks=[])
    assert breakdown.safety_override is False


def test_rank_tasks_puts_overdue_severity_a_first_regardless_of_score():
    low_score_critical = make_task(
        task_id="A-1", severity_code="A", days_overdue=1, section="NDLS-GZB"
    )
    high_score_non_critical = make_task(
        task_id="B-1", severity_code="B", days_overdue=90, section="NDLS-GZB"
    )
    ranked = rank_tasks([high_score_non_critical, low_score_critical], blocks=[])
    assert ranked[0].task_id == "A-1"
    assert ranked[0].safety_override is True


def test_rank_tasks_orders_remaining_by_descending_score():
    high = make_task(task_id="high", severity_code="B", days_overdue=30)
    low = make_task(task_id="low", severity_code="C", days_overdue=0)
    ranked = rank_tasks([low, high], blocks=[])
    assert [b.task_id for b in ranked] == ["high", "low"]


def test_dominant_component_reflects_largest_weighted_contribution():
    task = make_task(severity_code="A", days_overdue=0)  # no override, criticality-driven
    breakdown = score_task(task, blocks=[])
    assert breakdown.dominant_component == "criticality"
