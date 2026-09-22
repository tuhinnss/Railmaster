"""Safety rule validator (spec section 6): the six rules, run as a
standalone check against a solver's *output* rather than only as solver
constraints, so a solver bug can never silently produce an unsafe plan.

Stage-agnostic. In Stage A (one task per block, no merging) the sharing
rules -- power isolation and compatibility -- are vacuously satisfied;
they become load-bearing once Stage B introduces merging. Block-type
match, capacity, and dependency order matter from Stage A onward.
No-double-booking isn't checked here: `assignments` is `task_id -> one
block_id`, so the data structure itself makes double-booking unrepresentable.

Power isolation is scoped to blocks whose block_type_possible is exactly
POWER (isolated power, traffic still running): no non-power task should
ride along there. A TRAFFIC_AND_POWER block stops both traffic and power,
so mixing POWER- and TRAFFIC-requiring tasks there is safe and expected --
it's exactly the worked example's correct outcome (spec section 5), not a
violation. task_fits_block already prevents a non-power task from ever
being individually assigned to a pure-POWER block, so this check is
defense-in-depth against a solver bug, not something normal output
should ever trigger.
"""

from dataclasses import dataclass

from app.models.block import BlockOpportunity
from app.models.enums import BlockType
from app.models.task import MaintenanceTask
from app.scheduling.compatibility import block_type_compatible, ranges_overlap, requires_power


@dataclass
class SafetyViolation:
    rule: str
    message: str
    block_id: str | None
    task_ids: list[str]


def validate_plan(
    tasks: list[MaintenanceTask],
    blocks: list[BlockOpportunity],
    assignments: dict[str, str | None],
) -> list[SafetyViolation]:
    tasks_by_id = {t.task_id: t for t in tasks}
    blocks_by_id = {b.block_id: b for b in blocks}
    violations: list[SafetyViolation] = []

    tasks_by_block: dict[str, list[MaintenanceTask]] = {}
    for task_id, block_id in assignments.items():
        if block_id is None:
            continue
        tasks_by_block.setdefault(block_id, []).append(tasks_by_id[task_id])

    for block_id, block_tasks in tasks_by_block.items():
        block = blocks_by_id.get(block_id)
        if block is None:
            violations.append(
                SafetyViolation(
                    rule="block_type_match",
                    message=f"Assignment references unknown block {block_id}",
                    block_id=block_id,
                    task_ids=[t.task_id for t in block_tasks],
                )
            )
            continue

        for task in block_tasks:
            if not block_type_compatible(task.block_type_required, block.block_type_possible):
                violations.append(
                    SafetyViolation(
                        rule="block_type_match",
                        message=(
                            f"{task.task_id} requires {task.block_type_required.value} but "
                            f"{block_id} only offers {block.block_type_possible.value}"
                        ),
                        block_id=block_id,
                        task_ids=[task.task_id],
                    )
                )

        total_duration = sum(t.est_duration_min for t in block_tasks)
        if total_duration > block.duration_min:
            violations.append(
                SafetyViolation(
                    rule="capacity",
                    message=(
                        f"{block_id} tasks need {total_duration} min but block only "
                        f"offers {block.duration_min} min"
                    ),
                    block_id=block_id,
                    task_ids=[t.task_id for t in block_tasks],
                )
            )

        if len(block_tasks) > 1:
            if block.block_type_possible == BlockType.POWER:
                non_power_tasks = [t for t in block_tasks if not requires_power(t)]
                if non_power_tasks:
                    violations.append(
                        SafetyViolation(
                            rule="power_isolation",
                            message=(
                                f"{block_id} is a pure power-isolation block but hosts "
                                f"non-power task(s) {[t.task_id for t in non_power_tasks]}"
                            ),
                            block_id=block_id,
                            task_ids=[t.task_id for t in non_power_tasks],
                        )
                    )

            for i in range(len(block_tasks)):
                for j in range(i + 1, len(block_tasks)):
                    a, b = block_tasks[i], block_tasks[j]
                    if not ranges_overlap(a.km_range, b.km_range):
                        violations.append(
                            SafetyViolation(
                                rule="compatibility",
                                message=(
                                    f"{a.task_id} (km {a.km_range}) and {b.task_id} "
                                    f"(km {b.km_range}) share {block_id} without "
                                    "overlapping km ranges"
                                ),
                                block_id=block_id,
                                task_ids=[a.task_id, b.task_id],
                            )
                        )

    for task in tasks:
        task_block_id = assignments.get(task.task_id)
        if task_block_id is None:
            continue
        for dep_id in task.depends_on:
            if dep_id not in tasks_by_id:
                continue
            dep_block_id = assignments.get(dep_id)
            if dep_block_id is None:
                violations.append(
                    SafetyViolation(
                        rule="dependency_order",
                        message=f"{task.task_id} is scheduled but its dependency {dep_id} is not",
                        block_id=task_block_id,
                        task_ids=[task.task_id, dep_id],
                    )
                )
                continue
            task_block = blocks_by_id[task_block_id]
            dep_block = blocks_by_id[dep_block_id]
            if dep_block.start_time > task_block.start_time:
                violations.append(
                    SafetyViolation(
                        rule="dependency_order",
                        message=(
                            f"{dep_id} is scheduled after its dependent {task.task_id} "
                            f"({dep_block.start_time} > {task_block.start_time})"
                        ),
                        block_id=task_block_id,
                        task_ids=[task.task_id, dep_id],
                    )
                )

    return violations
