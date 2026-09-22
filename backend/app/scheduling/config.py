"""Tunable scheduling parameters, kept out of the scoring code so they can
be overridden live (e.g. from a dashboard "what if criticality mattered
more" control) without touching prioritizer.py."""

from pydantic import BaseModel


class PriorityWeights(BaseModel):
    criticality: float = 0.5
    urgency: float = 0.3
    availability_impact: float = 0.2


DEFAULT_PRIORITY_WEIGHTS = PriorityWeights()
