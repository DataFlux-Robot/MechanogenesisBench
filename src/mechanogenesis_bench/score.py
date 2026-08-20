from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean

from .submission import EvaluationReport, Submission
from .task import TaskPackage
from .verify import VerificationReport


@dataclass(frozen=True)
class ScoreCard:
    """A vector score: dimensions are never hidden in a scalar leaderboard."""

    eligible: bool
    disqualifications: tuple[str, ...]
    promotions: int
    capability_gain: float | None
    robustness_pass_rate: float | None
    autonomy_fraction: float | None
    promotions_per_hour: float | None
    promotions_per_dollar: float | None
    mean_rrc_time_rate_delta: float | None
    mean_rrc_budget_rate_delta: float | None
    certified_evidence_tier: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "eligible": self.eligible,
            "disqualifications": list(self.disqualifications),
            "promotions": self.promotions,
            "capability_gain": self.capability_gain,
            "robustness_pass_rate": self.robustness_pass_rate,
            "autonomy_fraction": self.autonomy_fraction,
            "promotions_per_hour": self.promotions_per_hour,
            "promotions_per_dollar": self.promotions_per_dollar,
            "mean_rrc_time_rate_delta": self.mean_rrc_time_rate_delta,
            "mean_rrc_budget_rate_delta": self.mean_rrc_budget_rate_delta,
            "certified_evidence_tier": self.certified_evidence_tier,
        }


def score_run(
    task: TaskPackage,
    submission: Submission,
    evaluation: EvaluationReport,
    verification: VerificationReport,
) -> ScoreCard:
    if not verification.valid:
        return ScoreCard(
            eligible=False,
            disqualifications=verification.reasons,
            promotions=verification.promotions,
            capability_gain=None,
            robustness_pass_rate=None,
            autonomy_fraction=None,
            promotions_per_hour=None,
            promotions_per_dollar=None,
            mean_rrc_time_rate_delta=None,
            mean_rrc_budget_rate_delta=None,
            certified_evidence_tier=None,
        )

    accepted = [decision for decision in evaluation.decisions if decision.accepted]
    gains = [decision.after_lower - decision.before_upper for decision in accepted]
    resources = verification.effective_resource_use
    human_limit = task.manifest.budget.human_intervention_s
    if human_limit == 0:
        autonomy = 1.0 if resources.human_intervention_s == 0 else 0.0
    else:
        autonomy = max(0.0, 1.0 - resources.human_intervention_s / human_limit)

    return ScoreCard(
        eligible=True,
        disqualifications=(),
        promotions=verification.promotions,
        capability_gain=fmean(gains) if gains else None,
        robustness_pass_rate=(
            fmean(item.robustness_pass_rate for item in accepted) if accepted else None
        ),
        autonomy_fraction=autonomy,
        promotions_per_hour=(
            verification.promotions * 3600.0 / resources.wall_time_s
            if resources.wall_time_s > 0
            else None
        ),
        promotions_per_dollar=(
            verification.promotions / resources.monetary_cost_usd
            if resources.monetary_cost_usd > 0
            else None
        ),
        mean_rrc_time_rate_delta=(
            fmean(item.rrc_time_rate_delta for item in accepted) if accepted else None
        ),
        mean_rrc_budget_rate_delta=(
            fmean(item.rrc_budget_rate_delta for item in accepted) if accepted else None
        ),
        certified_evidence_tier=(
            verification.certified_evidence_tier.value
            if verification.certified_evidence_tier is not None
            else None
        ),
    )
