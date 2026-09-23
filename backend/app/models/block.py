"""Block opportunity. Field names and types match build spec section 2
exactly — the one shape every corridor-availability source (synthetic
today, COA later) converts into."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.enums import BlockType


class BlockOpportunity(BaseModel):
    block_id: str
    section: str
    start_time: datetime
    end_time: datetime
    duration_min: int
    block_type_possible: BlockType
    expected_train_impact: float
    goods_traffic_load: float
    # Not part of the original spec section 2 shape -- provenance metadata
    # set by app/ntes_bridge.py, not by the generator. "synthetic" unless
    # a real ntes-adapter prediction actually overwrote expected_train_impact.
    data_source: Literal["synthetic", "ntes_live"] = "synthetic"
