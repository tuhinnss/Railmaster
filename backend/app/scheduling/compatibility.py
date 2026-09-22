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
