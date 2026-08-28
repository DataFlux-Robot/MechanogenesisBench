"""Fail-closed Evidence--Action Closure protocol.

The protocol does not decide whether evidence is physically true.  Grounding,
criticality, contradiction and independence are evaluator-owned findings.  It
decides whether a promotion request is structurally compatible with those
findings: every critical contradiction must lead to a tested action change or
withdrawal of the contradicted claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .errors import SchemaError


SCHEMA_VERSION = "0.1"
SEMANTICS_ID = "Mechanogenesis.EvidenceActionClosure.v0.1"


def _exact(raw: Mapping[str, Any], expected: set[str], field: str) -> None:
    if set(raw) != expected:
        raise SchemaError(
            f"{field} fields mismatch; missing={sorted(expected - set(raw))}, "
            f"extra={sorted(set(raw) - expected)}"
        )


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith(
        "sha256:"
    ):
        raise SchemaError(f"{field} must be a sha256 digest")
    try:
        int(value[7:], 16)
    except ValueError as error:
        raise SchemaError(f"{field} contains non-hex digest data") from error
    return value


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise SchemaError(f"{field} must be Boolean")
    return value


@dataclass(frozen=True)
class EvidenceActionReceipt:
    evidence_hash: str
    source_hash: str
    claim_hash: str
    prior_action_hash: str
    resulting_action_hash: str
    verifier_hash: str
    critical: bool
    contradicts_claim: bool
    grounded: bool
    independent_check: bool
    revision_declared: bool
    retested: bool
    claim_withdrawn: bool

    @classmethod
    def from_mapping(
        cls, raw: Mapping[str, Any], field: str = "receipt"
    ) -> "EvidenceActionReceipt":
        expected = {
            "evidenceHash",
            "sourceHash",
            "claimHash",
            "priorActionHash",
            "resultingActionHash",
            "verifierHash",
            "critical",
            "contradictsClaim",
            "grounded",
            "independentCheck",
            "revisionDeclared",
            "retested",
            "claimWithdrawn",
        }
        _exact(raw, expected, field)
        return cls(
            evidence_hash=_digest(raw["evidenceHash"], f"{field}.evidenceHash"),
            source_hash=_digest(raw["sourceHash"], f"{field}.sourceHash"),
            claim_hash=_digest(raw["claimHash"], f"{field}.claimHash"),
            prior_action_hash=_digest(
                raw["priorActionHash"], f"{field}.priorActionHash"
            ),
            resulting_action_hash=_digest(
                raw["resultingActionHash"], f"{field}.resultingActionHash"
            ),
            verifier_hash=_digest(raw["verifierHash"], f"{field}.verifierHash"),
            critical=_boolean(raw["critical"], f"{field}.critical"),
            contradicts_claim=_boolean(
                raw["contradictsClaim"], f"{field}.contradictsClaim"
            ),
            grounded=_boolean(raw["grounded"], f"{field}.grounded"),
            independent_check=_boolean(
                raw["independentCheck"], f"{field}.independentCheck"
            ),
            revision_declared=_boolean(
                raw["revisionDeclared"], f"{field}.revisionDeclared"
            ),
            retested=_boolean(raw["retested"], f"{field}.retested"),
            claim_withdrawn=_boolean(
                raw["claimWithdrawn"], f"{field}.claimWithdrawn"
            ),
        )

    def resolved_for(self, final_claim_hash: str) -> bool:
        revised = (
            self.revision_declared
            and self.prior_action_hash != self.resulting_action_hash
            and self.retested
        )
        withdrawn = self.claim_withdrawn and self.claim_hash != final_claim_hash
        return revised or withdrawn

    def to_dict(self) -> dict[str, object]:
        return {
            "evidenceHash": self.evidence_hash,
            "sourceHash": self.source_hash,
            "claimHash": self.claim_hash,
            "priorActionHash": self.prior_action_hash,
            "resultingActionHash": self.resulting_action_hash,
            "verifierHash": self.verifier_hash,
            "critical": self.critical,
            "contradictsClaim": self.contradicts_claim,
            "grounded": self.grounded,
            "independentCheck": self.independent_check,
            "revisionDeclared": self.revision_declared,
            "retested": self.retested,
            "claimWithdrawn": self.claim_withdrawn,
        }


@dataclass(frozen=True)
class EvidenceActionCertificate:
    schema_version: str
    semantics_id: str
    trajectory_hash: str
    final_claim_hash: str
    evaluator_hash: str
    promotion_requested: bool
    receipts: tuple[EvidenceActionReceipt, ...]

    @classmethod
    def from_mapping(
        cls, raw: Mapping[str, Any]
    ) -> "EvidenceActionCertificate":
        expected = {
            "schemaVersion",
            "semanticsId",
            "trajectoryHash",
            "finalClaimHash",
            "evaluatorHash",
            "promotionRequested",
            "receipts",
        }
        _exact(raw, expected, "evidence_action_certificate")
        if raw["schemaVersion"] != SCHEMA_VERSION:
            raise SchemaError("unsupported evidence-action schemaVersion")
        if raw["semanticsId"] != SEMANTICS_ID:
            raise SchemaError("unsupported evidence-action semanticsId")
        receipts_raw = raw["receipts"]
        if not isinstance(receipts_raw, list):
            raise SchemaError("evidence_action_certificate.receipts must be a list")
        return cls(
            schema_version=SCHEMA_VERSION,
            semantics_id=SEMANTICS_ID,
            trajectory_hash=_digest(
                raw["trajectoryHash"], "evidence_action_certificate.trajectoryHash"
            ),
            final_claim_hash=_digest(
                raw["finalClaimHash"], "evidence_action_certificate.finalClaimHash"
            ),
            evaluator_hash=_digest(
                raw["evaluatorHash"], "evidence_action_certificate.evaluatorHash"
            ),
            promotion_requested=_boolean(
                raw["promotionRequested"],
                "evidence_action_certificate.promotionRequested",
            ),
            receipts=tuple(
                EvidenceActionReceipt.from_mapping(
                    item
                    if isinstance(item, dict)
                    else (_raise_receipt_mapping(index)),
                    f"evidence_action_certificate.receipts[{index}]",
                )
                for index, item in enumerate(receipts_raw)
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": self.schema_version,
            "semanticsId": self.semantics_id,
            "trajectoryHash": self.trajectory_hash,
            "finalClaimHash": self.final_claim_hash,
            "evaluatorHash": self.evaluator_hash,
            "promotionRequested": self.promotion_requested,
            "receipts": [receipt.to_dict() for receipt in self.receipts],
        }


def _raise_receipt_mapping(index: int):
    raise SchemaError(
        f"evidence_action_certificate.receipts[{index}] must be an object"
    )


class EvidenceActionStatus(str, Enum):
    REJECTED = "rejected"
    WITHHELD = "promotion_withheld"
    ACCEPTED = "promotion_admissible"


@dataclass(frozen=True)
class EvidenceActionReport:
    status: EvidenceActionStatus
    reasons: tuple[str, ...]
    critical_receipts: int
    critical_contradictions: int
    resolved_contradictions: int

    @property
    def accepted(self) -> bool:
        return self.status is EvidenceActionStatus.ACCEPTED


def verify_evidence_action_closure(
    certificate: EvidenceActionCertificate,
) -> EvidenceActionReport:
    """Apply the same finite protocol encoded by the Lean checker."""

    protocol_errors: list[str] = []
    unresolved: list[str] = []
    critical = [item for item in certificate.receipts if item.critical]
    contradictions = [item for item in critical if item.contradicts_claim]
    resolved = [
        item
        for item in contradictions
        if item.resolved_for(certificate.final_claim_hash)
    ]

    if not certificate.receipts:
        protocol_errors.append("at least one evidence receipt is required")
    if not critical:
        protocol_errors.append(
            "at least one evaluator-designated critical receipt is required"
        )
    for index, receipt in enumerate(certificate.receipts):
        if receipt.critical and not receipt.grounded:
            protocol_errors.append(f"critical receipt {index} is not grounded")
        if receipt.critical and not receipt.independent_check:
            protocol_errors.append(
                f"critical receipt {index} lacks an independent check"
            )
        if receipt in contradictions and receipt not in resolved:
            unresolved.append(
                f"critical contradiction {index} changed neither a retested "
                "action nor the final claim"
            )

    if protocol_errors or (certificate.promotion_requested and unresolved):
        return EvidenceActionReport(
            EvidenceActionStatus.REJECTED,
            tuple(protocol_errors + unresolved),
            len(critical),
            len(contradictions),
            len(resolved),
        )
    if not certificate.promotion_requested:
        return EvidenceActionReport(
            EvidenceActionStatus.WITHHELD,
            tuple(unresolved) or ("promotion was not requested",),
            len(critical),
            len(contradictions),
            len(resolved),
        )
    return EvidenceActionReport(
        EvidenceActionStatus.ACCEPTED,
        (),
        len(critical),
        len(contradictions),
        len(resolved),
    )
