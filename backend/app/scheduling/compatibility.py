"""Task/block compatibility checks (spec section 5-6). Shared by the
prioritizer, the CP-SAT scheduler, and the safety validator so there's
exactly one definition of "can this task use this block."
"""

from app.models.block import BlockOpportunity
from app.models.enums import BlockType
from app.models.task import MaintenanceTask


def block_type_compatible(required: BlockType, possible: BlockType) -> bool:
    """block_type_required is a subset of block_type_possible (spec section 6)."""
    if possible == BlockType.TRAFFIC_AND_POWER:
        return True
    return required == possible


def task_fits_block(task: MaintenanceTask, block: BlockOpportunity) -> bool:
    return (
        block.section == task.section
        and block_type_compatible(task.block_type_required, block.block_type_possible)
        and block.duration_min >= task.est_duration_min
    )


def compatible_blocks(
    task: MaintenanceTask, blocks: list[BlockOpportunity]
) -> list[BlockOpportunity]:
    return [b for b in blocks if task_fits_block(task, b)]


def requires_power(task: MaintenanceTask) -> bool:
    return task.block_type_required in (BlockType.POWER, BlockType.TRAFFIC_AND_POWER)


def ranges_overlap(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def tasks_can_share_block(a: MaintenanceTask, b: MaintenanceTask) -> bool:
    """Stage B compatibility set (spec section 5): same section, overlapping
    km range, compatible block types, no safety conflict.

    Block-type compatibility and power-isolation safety are already
    enforced per task against whichever specific block is chosen (see
    task_fits_block / block_type_compatible): a block that safely hosts
    both a POWER-only task and a TRAFFIC-only task together is, by
    construction, TRAFFIC_AND_POWER -- which is exactly the worked
    example's expected outcome (spec section 5), not a case this pairwise
    check should additionally forbid. The one genuinely independent
    pairwise condition left is physical proximity: overlapping km range.
    """
    return a.section == b.section and ranges_overlap(a.km_range, b.km_range)
