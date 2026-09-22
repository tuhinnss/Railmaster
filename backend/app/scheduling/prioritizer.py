"""Rule-based priority score (spec section 4). No ML — there's no real
failure history to train on yet, so this is a hand-written, tunable
formula: Priority = w1*Criticality + w2*Urgency + w3*AvailabilityImpact.

AvailabilityImpact is defined as the expected_train_impact of the task's
highest-impact compatible block opportunity: the spec calls this "the
best available block for this task," which is ambiguous between
lowest-disruption and highest-relevance. We take the max, on the
reasoning that a task whose only viable windows are high-impact ones is
the task most worth locking in a good outcome for early — a task with
only low-impact options is comparatively low-stakes wherever it lands.
This is a documented assumption, not a spec-mandated one; the weight is
tunable and this component can be swapped if that reading turns out
wrong for the judges.
"""

from dataclasses import dataclass

from app.models.block import BlockOpportunity
from app.models.enums import SeverityCode
from app.models.task import MaintenanceTask
from app.scheduling.compatibility import compatible_blocks
from app.scheduling.config import DEFAULT_PRIORITY_WEIGHTS, PriorityWeights

CRITICALITY_BY_SEVERITY = {
    SeverityCode.A: 1.0,
    SeverityCode.B: 0.6,
    SeverityCode.C: 0.3,
}


@dataclass
class PriorityBreakdown:
    task_id: str
    criticality: float
    urgency: float
    availability_impact: float
    weighted_criticality: float
    weighted_urgency: float
    weighted_availability_impact: float
    score: float
    safety_override: bool

    @property
    def dominant_component(self) -> str:
        """Which component drove the score — for explainability (section 7)."""
        contributions = {
            "criticality": self.weighted_criticality,
            "urgency": self.weighted_urgency,
            "availability_impact": self.weighted_availability_impact,
        }
        return max(contributions, key=contributions.get)


def score_task(
    task: MaintenanceTask,
    blocks: list[BlockOpportunity],
    weights: PriorityWeights = DEFAULT_PRIORITY_WEIGHTS,
) -> PriorityBreakdown:
    criticality = CRITICALITY_BY_SEVERITY[task.severity_code]
    urgency = min(task.days_overdue / 30, 1.0)

    candidates = compatible_blocks(task, blocks)
    availability_impact = max((b.expected_train_impact for b in candidates), default=0.0)

    weighted_criticality = weights.criticality * criticality
    weighted_urgency = weights.urgency * urgency
    weighted_availability_impact = weights.availability_impact * availability_impact
    score = weighted_criticality + weighted_urgency + weighted_availability_impact

    # Safety-critical override: any A-severity task that's overdue outranks
    # every non-A task regardless of score (spec section 4).
    safety_override = task.severity_code == SeverityCode.A and task.days_overdue > 0

    return PriorityBreakdown(
        task_id=task.task_id,
        criticality=criticality,
        urgency=urgency,
        availability_impact=availability_impact,
        weighted_criticality=weighted_criticality,
        weighted_urgency=weighted_urgency,
        weighted_availability_impact=weighted_availability_impact,
        score=score,
        safety_override=safety_override,
    )


def rank_tasks(
    tasks: list[MaintenanceTask],
    blocks: list[BlockOpportunity],
    weights: PriorityWeights = DEFAULT_PRIORITY_WEIGHTS,
) -> list[PriorityBreakdown]:
    """Safety-override tasks first, then descending score."""
    breakdowns = [score_task(t, blocks, weights) for t in tasks]
    breakdowns.sort(key=lambda b: (not b.safety_override, -b.score))
    return breakdowns
