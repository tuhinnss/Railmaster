"""Loads tasks/blocks for the API layer from data/synthetic/, generating
it with the default seed on first use if it isn't there yet. Reading
fresh from disk per request (rather than holding scheduler state in
memory) keeps each request's view consistent with whatever's on disk,
which matters once a demo wants to regenerate data mid-session.
"""

import json
import random
from datetime import date
from pathlib import Path

from app.datagen.generate import DEFAULT_OUT_DIR, generate_blocks, generate_tasks, next_monday, write_outputs
from app.datagen.reference_data import SECTIONS
from app.models.block import BlockOpportunity
from app.models.task import MaintenanceTask

DEFAULT_SEED = 1
DEFAULT_NUM_TASKS = 45
DEFAULT_BLOCKS_PER_SECTION = 20


def _ensure_data_exists(out_dir: Path = DEFAULT_OUT_DIR) -> None:
    tasks_path = out_dir / "tasks.json"
    blocks_path = out_dir / "blocks.json"
    if tasks_path.exists() and blocks_path.exists():
        return

    rng = random.Random(DEFAULT_SEED)
    reference_date = date.today()
    tasks = generate_tasks(SECTIONS, DEFAULT_NUM_TASKS, rng, reference_date)
    blocks = generate_blocks(SECTIONS, DEFAULT_BLOCKS_PER_SECTION, rng, next_monday(reference_date))
    write_outputs(tasks, blocks, out_dir)


def load_tasks(out_dir: Path = DEFAULT_OUT_DIR) -> list[MaintenanceTask]:
    _ensure_data_exists(out_dir)
    raw = json.loads((out_dir / "tasks.json").read_text())
    return [MaintenanceTask(**t) for t in raw]


def load_blocks(out_dir: Path = DEFAULT_OUT_DIR) -> list[BlockOpportunity]:
    _ensure_data_exists(out_dir)
    raw = json.loads((out_dir / "blocks.json").read_text())
    return [BlockOpportunity(**b) for b in raw]
