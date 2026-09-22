"""Shared enums across domain models. Values match the JSON schema in the
build spec exactly (section 2), not Python-conventional constant names."""

from enum import Enum


class Department(str, Enum):
    ENGINEERING = "Engineering"
    TRD = "TRD"
    SNT = "S&T"


class SeverityCode(str, Enum):
    A = "A"  # safety-critical
    B = "B"
    C = "C"


class BlockType(str, Enum):
    TRAFFIC = "traffic"
    POWER = "power"
    TRAFFIC_AND_POWER = "traffic_and_power"


class Horizon(str, Enum):
    WEEKLY = "WEEKLY"
    # MONTHLY is future work per spec section 1 — weekly loop only for now.
