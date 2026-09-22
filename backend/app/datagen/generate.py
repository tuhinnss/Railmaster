"""Synthetic data generator (build spec section 3).

Produces data/synthetic/tasks.json and data/synthetic/blocks.json: 30-60
tasks split across departments/severities, and 15-25 block opportunities
per section per week, with a deliberate overlapping-block fixture per
section that proves the Stage B merge scheduler has something to merge.

Run: python -m app.datagen.generate [--seed 42] [--num-tasks 45] ...
"""

import argparse
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from app.models.block import BlockOpportunity
from app.models.enums import BlockType, Department, SeverityCode
from app.models.task import MaintenanceTask
from app.datagen.reference_data import (
    BLOCK_OPPORTUNITY_TYPE_WEIGHTS,
    BLOCK_TYPE_WEIGHTS_BY_DEPT,
    DEFECT_TYPES,
    DEPARTMENT_TASK_ID_PREFIX,
    EST_DURATION_CHOICES_MIN,
    SECTIONS,
    SEVERITY_WEIGHTS,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "synthetic"

ASSET_PREFIX = {
    Department.ENGINEERING: "TRK",
    Department.TRD: "OHE",
    Department.SNT: "SIG",
}

OVERDUE_FRACTION = 0.15


def weighted_choice(rng: random.Random, weights: dict):
    keys = list(weights.keys())
    weights_list = list(weights.values())
    return rng.choices(keys, weights=weights_list, k=1)[0]


def next_monday(reference_date: date) -> date:
    return reference_date + timedelta(days=(7 - reference_date.weekday()) % 7)


def generate_tasks(
    sections: list[tuple[str, float, float]],
    num_tasks: int,
    rng: random.Random,
    reference_date: date,
) -> list[MaintenanceTask]:
    departments = [Department.ENGINEERING, Department.TRD, Department.SNT]
    counts = [num_tasks // 3] * 3
    for i in range(num_tasks - sum(counts)):
        counts[i] += 1

    tasks: list[MaintenanceTask] = []
    section_task_ids: dict[str, list[str]] = {name: [] for name, _, _ in sections}

    for department, count in zip(departments, counts):
        start_num = rng.randint(1000, 8000)
        for i in range(count):
            section_name, km_start, km_end = rng.choice(sections)
            width = rng.uniform(0.2, 1.5)
            width = min(width, km_end - km_start - 0.05)
            task_km_start = rng.uniform(km_start, km_end - width)
            task_km_end = task_km_start + width
            km_marker = (task_km_start + task_km_end) / 2

            severity_code = SeverityCode(weighted_choice(rng, SEVERITY_WEIGHTS))

            if rng.random() < OVERDUE_FRACTION:
                days_overdue = rng.randint(1, 45)
                due_date = reference_date - timedelta(days=days_overdue)
            else:
                days_overdue = 0
                due_date = reference_date + timedelta(days=rng.randint(1, 60))
            date_raised = due_date - timedelta(days=rng.randint(14, 45))

            duration_choices = (
                [d for d in EST_DURATION_CHOICES_MIN if d >= 120]
                if severity_code == SeverityCode.A
                else EST_DURATION_CHOICES_MIN
            )

            task_num = start_num + i
            task_id = f"{DEPARTMENT_TASK_ID_PREFIX[department]}-{reference_date.year}-{task_num:05d}"
            asset_id = f"{ASSET_PREFIX[department]}-SEC-{task_num % 900:03d}-KM{int(round(km_marker * 10)):04d}"

            task = MaintenanceTask(
                task_id=task_id,
                department=department,
                asset_id=asset_id,
                section=section_name,
                km_range=(round(task_km_start, 2), round(task_km_end, 2)),
                defect_type=rng.choice(DEFECT_TYPES[department]),
                severity_code=severity_code,
                date_raised=date_raised,
                due_date=due_date,
                days_overdue=days_overdue,
                est_duration_min=rng.choice(duration_choices),
                crew_required=rng.randint(2, 8),
                block_type_required=weighted_choice(rng, BLOCK_TYPE_WEIGHTS_BY_DEPT[department]),
                depends_on=[],
            )
            tasks.append(task)
            section_task_ids[section_name].append(task_id)

    # Second pass: ~10% of tasks depend on an earlier task in the same section.
    for i, task in enumerate(tasks):
        if rng.random() < 0.10:
            candidates = [
                t.task_id
                for t in tasks[:i]
                if t.section == task.section and t.task_id != task.task_id
            ]
            if candidates:
                task.depends_on = [rng.choice(candidates)]

    return tasks


def _random_block_time(day: date, rng: random.Random) -> tuple[datetime, int]:
    """A start time in a night traffic block window, plus a duration in minutes."""
    if rng.random() < 0.7:
        start_hour, start_minute = rng.randint(0, 3), rng.choice([0, 15, 30, 45])
    else:
        start_hour, start_minute = 22, rng.choice([0, 30])
    start = datetime(day.year, day.month, day.day, start_hour, start_minute)
    duration_min = rng.choice([90, 120, 150, 180, 210, 240, 300])
    return start, duration_min


def generate_blocks(
    sections: list[tuple[str, float, float]],
    blocks_per_section: int,
    rng: random.Random,
    week_start: date,
) -> list[BlockOpportunity]:
    blocks: list[BlockOpportunity] = []

    for section_name, _, _ in sections:
        seq = 1
        section_blocks: list[BlockOpportunity] = []

        def make_block(start: datetime, duration_min: int, block_type: BlockType) -> BlockOpportunity:
            nonlocal seq
            block = BlockOpportunity(
                block_id=f"BLK-{section_name}-{seq:04d}",
                section=section_name,
                start_time=start,
                end_time=start + timedelta(minutes=duration_min),
                duration_min=duration_min,
                block_type_possible=block_type,
                expected_train_impact=round(rng.uniform(0.05, 0.6), 2),
                goods_traffic_load=round(rng.uniform(0.05, 0.5), 2),
            )
            seq += 1
            return block

        # Deliberate overlap fixture: 2 nights where two departments would
        # traditionally have requested separate, overlapping blocks.
        overlap_nights = rng.sample(range(7), k=min(2, blocks_per_section // 4 or 1))
        for day_offset in overlap_nights:
            day = week_start + timedelta(days=day_offset)
            base_start = datetime(day.year, day.month, day.day, 1, 0)
            section_blocks.append(make_block(base_start, 180, BlockType.TRAFFIC))
            section_blocks.append(make_block(base_start + timedelta(minutes=30), 120, BlockType.POWER))

        remaining = blocks_per_section - len(section_blocks)
        for _ in range(max(remaining, 0)):
            day = week_start + timedelta(days=rng.randint(0, 6))
            start, duration_min = _random_block_time(day, rng)
            block_type = weighted_choice(rng, BLOCK_OPPORTUNITY_TYPE_WEIGHTS)
            section_blocks.append(make_block(start, duration_min, block_type))

        blocks.extend(section_blocks)

    return blocks


def _json_default(obj):
    return json.loads(obj.model_dump_json()) if hasattr(obj, "model_dump_json") else str(obj)


def write_outputs(tasks: list[MaintenanceTask], blocks: list[BlockOpportunity], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "tasks.json").write_text(
        json.dumps([json.loads(t.model_dump_json()) for t in tasks], indent=2)
    )
    (out_dir / "blocks.json").write_text(
        json.dumps([json.loads(b.model_dump_json()) for b in blocks], indent=2)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic tasks/blocks fixture data.")
    parser.add_argument("--seed", type=int, default=4)
    parser.add_argument("--num-tasks", type=int, default=45)
    parser.add_argument("--blocks-per-section", type=int, default=20)
    parser.add_argument(
        "--reference-date",
        type=str,
        default=None,
        help="ISO date (YYYY-MM-DD) treated as 'today' for due-date/overdue math. Defaults to today.",
    )
    parser.add_argument("--out-dir", type=str, default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    rng = random.Random(args.seed)
    reference_date = (
        date.fromisoformat(args.reference_date) if args.reference_date else date.today()
    )
    week_start = next_monday(reference_date)

    tasks = generate_tasks(SECTIONS, args.num_tasks, rng, reference_date)
    blocks = generate_blocks(SECTIONS, args.blocks_per_section, rng, week_start)

    out_dir = Path(args.out_dir)
    write_outputs(tasks, blocks, out_dir)

    print(f"Wrote {len(tasks)} tasks and {len(blocks)} blocks to {out_dir}")


if __name__ == "__main__":
    main()
