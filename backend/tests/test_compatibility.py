from datetime import date, datetime

from app.models.block import BlockOpportunity
from app.models.enums import BlockType
from app.models.task import MaintenanceTask
from app.scheduling.compatibility import block_type_compatible, compatible_blocks


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


def test_block_type_compatible_exact_match():
    assert block_type_compatible(BlockType.TRAFFIC, BlockType.TRAFFIC)
    assert not block_type_compatible(BlockType.TRAFFIC, BlockType.POWER)


def test_block_type_compatible_traffic_and_power_covers_both():
    assert block_type_compatible(BlockType.TRAFFIC, BlockType.TRAFFIC_AND_POWER)
    assert block_type_compatible(BlockType.POWER, BlockType.TRAFFIC_AND_POWER)
    assert block_type_compatible(BlockType.TRAFFIC_AND_POWER, BlockType.TRAFFIC_AND_POWER)


def test_compatible_blocks_filters_by_section_type_and_duration():
    task = make_task(section="GHY-LMG", block_type_required="power", est_duration_min=150)
    blocks = [
        make_block(block_id="wrong-section", section="LMG-RNY", block_type_possible="power"),
        make_block(block_id="wrong-type", block_type_possible="traffic"),
        make_block(block_id="too-short", block_type_possible="power", duration_min=100),
        make_block(block_id="good", block_type_possible="power", duration_min=180),
        make_block(block_id="good-via-combined", block_type_possible="traffic_and_power", duration_min=180),
    ]
    result = {b.block_id for b in compatible_blocks(task, blocks)}
    assert result == {"good", "good-via-combined"}
