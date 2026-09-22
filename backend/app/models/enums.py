"""Shared enums across domain models."""

from enum import Enum


class Department(str, Enum):
    ENGINEERING = "ENGINEERING"
    SIGNAL_TELECOM = "SIGNAL_TELECOM"
    TRACTION_DISTRIBUTION = "TRACTION_DISTRIBUTION"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class TaskStatus(str, Enum):
    OPEN = "OPEN"
    SCHEDULED = "SCHEDULED"
    DONE = "DONE"
    OVERDUE = "OVERDUE"


class Horizon(str, Enum):
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
