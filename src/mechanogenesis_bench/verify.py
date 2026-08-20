from __future__ import annotations

from dataclasses import dataclass

from .models import EvidenceTier, ResourceVector, Track
from .submission import EvaluationReport, Submission
from .task import TaskPackage


@dataclass(frozen=True)
class VerificationReport:
    """Fail-closed result of binding a submission to a trusted evaluation."""

    valid: bool
    reasons: tuple[str, ...]
    promotions: int
    evaluated_generations: int
    effective_resource_use: ResourceVector
    certified_evidence_tier: EvidenceTier | None

    def to_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "reasons": list(self.reasons),
            "promotions": self.promotions,
            "evaluated_generations": self.evaluated_generations,
            "effective_resource_use": {
                name: getattr(self.effective_resource_use, name)
                for name in self.effective_resource_use.__dataclass_fields__
            },
            "certified_evidence_tier": (
                self.certified_evidence_tier.value
                if self.certified_evidence_tier is not None
                else None
            ),
        }


def _effective_resources(
    declared: ResourceVector, observed_wall_time_s: float | None
) -> ResourceVector:
    wall_time_s = declared.wall_time_s
    if observed_wall_time_s is not None:
        wall_time_s = max(wall_time_s, observed_wall_time_s)
    return ResourceVector(
        wall_time_s=wall_time_s,
        monetary_cost_usd=declared.monetary_cost_usd,
        tokens=declared.tokens,
        energy_j=declared.energy_j,
        material_kg=declared.material_kg,
        human_intervention_s=declared.human_intervention_s,
        attempts=declared.attempts,
    )


def verify_run(
    task: TaskPackage,
    submission: Submission,
    evaluation: EvaluationReport,
    *,
    observed_wall_time_s: float | None = None,
) -> VerificationReport:
    """Verify protocol claims without trusting submission-declared success.

    This function proves only that the run satisfies the benchmark protocol and
    the task evaluator's bounded claim. It does not infer real-world validity
    from conformance or simulation evidence.
    """

    reasons: list[str] = []
    manifest = task.manifest
    effective = _effective_resources(submission.resource_use, observed_wall_time_s)

    if evaluation.task_id != manifest.task_id:
        reasons.append("evaluation task_id does not match the task")
    if evaluation.task_package_digest != task.package_digest:
        reasons.append("evaluation is not bound to this task package")

    if evaluation.evaluator_digest != task.evaluator_digest:
        reasons.append("evaluation is not bound to the trusted private evaluator bundle")

    if len(submission.generations) > manifest.generations:
        reasons.append("submission exceeds the task generation limit")
    if len(evaluation.decisions) != len(submission.generations):
        reasons.append("evaluator decision count does not match submitted generations")
    if submission.declared_evidence_tier.rank > manifest.evidence_ceiling.rank:
        reasons.append("declared evidence tier exceeds the task evidence ceiling")
    if not effective.within(manifest.budget):
        reasons.append("resource use exceeds the task budget")

    decisions_by_index = {decision.index: decision for decision in evaluation.decisions}
    if len(decisions_by_index) != len(evaluation.decisions):
        reasons.append("evaluation contains duplicate generation decisions")

    expected_parent_process = task.world["baseline_process_hash"]
    expected_parent_world = task.world["baseline_world_hash"]
    promotions = 0
    accepted_tiers: list[EvidenceTier] = []

    for generation in submission.generations:
        prefix = f"generation {generation.index}"
        decision = decisions_by_index.get(generation.index)
        if decision is None:
            reasons.append(f"{prefix} has no evaluator decision")
            continue

        if generation.parent_process_hash != expected_parent_process:
            reasons.append(f"{prefix} is not descended from the last promoted process")
        if generation.parent_world_hash != expected_parent_world:
            reasons.append(f"{prefix} does not begin at the last promoted world state")
        if generation.child_process_hash == generation.parent_process_hash:
            reasons.append(f"{prefix} does not propose a distinct child process")
        if decision.artifact_hash != generation.artifact_hash:
            reasons.append(f"{prefix} evaluator decision targets a different artifact")
        if decision.evidence_tier.rank > manifest.evidence_ceiling.rank:
            reasons.append(f"{prefix} decision exceeds the task evidence ceiling")
        if decision.evidence_tier.rank > submission.declared_evidence_tier.rank:
            reasons.append(f"{prefix} decision exceeds the submitted evidence tier")

        receipt_parent = generation.construction_receipts[0].parent_world_hash
        if receipt_parent != generation.parent_world_hash:
            reasons.append(f"{prefix} construction lineage does not begin at its parent world")
        previous_world = receipt_parent
        for receipt_index, receipt in enumerate(generation.construction_receipts):
            receipt_prefix = f"{prefix} construction receipt {receipt_index}"
            if receipt.parent_world_hash != previous_world:
                reasons.append(f"{receipt_prefix} breaks world-state lineage")
            if receipt.parent_world_hash == receipt.child_world_hash:
                reasons.append(f"{receipt_prefix} records no state transition")
            for balance in receipt.balances:
                if not balance.closes:
                    reasons.append(
                        f"{receipt_prefix} violates exact material closure for {balance.material}"
                    )
            previous_world = receipt.child_world_hash
        if previous_world != generation.child_world_hash:
            reasons.append(f"{prefix} construction lineage does not end at its child world")

        promotion_predicate = (
            decision.margin > 0
            and decision.after_lower >= decision.before_upper + decision.margin
            and decision.net_value > 0
            and decision.robustness_pass_rate
            >= manifest.min_robustness_pass_rate
        )
        if decision.accepted != promotion_predicate:
            reasons.append(f"{prefix} accepted flag disagrees with the promotion predicate")

        if decision.accepted:
            promotions += 1
            accepted_tiers.append(decision.evidence_tier)
            expected_parent_process = generation.child_process_hash
            expected_parent_world = generation.child_world_hash
            if manifest.track is Track.RECURSIVE_LEARNER:
                if decision.rrc_time_rate_delta < 0 or decision.rrc_budget_rate_delta < 0:
                    reasons.append(f"{prefix} has negative Recursive Research Credit")
                if decision.rrc_time_rate_delta == 0 and decision.rrc_budget_rate_delta == 0:
                    reasons.append(
                        f"{prefix} has no measured recursive-research improvement"
                    )

    if promotions < manifest.min_promotions:
        reasons.append(
            f"only {promotions} promotions; task requires {manifest.min_promotions}"
        )

    certified_tier = None
    if accepted_tiers:
        certified_tier = min(accepted_tiers, key=lambda tier: tier.rank)

    return VerificationReport(
        valid=not reasons,
        reasons=tuple(reasons),
        promotions=promotions,
        evaluated_generations=len(evaluation.decisions),
        effective_resource_use=effective,
        certified_evidence_tier=certified_tier,
    )
