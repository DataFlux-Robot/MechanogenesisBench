"""Fail-closed S0 diagnostic evidence protocol.

Natural-language mechanism explanations remain untrusted.  This module checks
the smaller protocol claim needed by MechanogenesisBench: matched guidance
arms, content-addressed artifact evidence, and a prediction frozen before the
evaluator reveals hidden physical outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any, Mapping

from .canonical import digest, file_digest
from .errors import SchemaError


SCHEMA_VERSION = "0.1"
SEMANTICS_ID = "Mechanogenesis.DiagnosticEvidence.v0.1"

ACCESS_LEVELS = {"endpoint_only", "artifact_aware"}
DIAGNOSTIC_STAGES = {
    "mission_framing",
    "world_access",
    "mrs_design",
    "canonical_construction",
    "physical_experiment",
    "causal_evaluation",
    "recursive_update",
    "cross_stage",
}
ROOT_MECHANISMS = {
    "evidence_grounding",
    "separability_access",
    "search_adaptation",
    "causal_attribution",
    "resource_robustness",
}


def _exact(raw: Mapping[str, Any], expected: set[str], field: str) -> None:
    if set(raw) != expected:
        raise SchemaError(
            f"{field} fields mismatch; missing={sorted(expected - set(raw))}, "
            f"extra={sorted(set(raw) - expected)}"
        )


def _text(value: Any, field: str, *, limit: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise SchemaError(f"{field} must be non-empty text of at most {limit} chars")
    return value


def _identifier(value: Any, field: str) -> str:
    text = _text(value, field, limit=64)
    if not text.replace("_", "").replace("-", "").isalnum():
        raise SchemaError(f"{field} must be a bounded identifier")
    return text


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


def _nat(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SchemaError(f"{field} must be a nonnegative integer")
    return value


@dataclass(frozen=True)
class DiagnosticAnchor:
    anchor_id: str
    artifact_path: str
    json_pointer: str
    artifact_hash: str
    value_hash: str
    verifier_hash: str
    grounded: bool
    independent_check: bool

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "DiagnosticAnchor":
        _exact(
            raw,
            {
                "anchorId",
                "artifactPath",
                "jsonPointer",
                "artifactHash",
                "valueHash",
                "verifierHash",
                "grounded",
                "independentCheck",
            },
            field,
        )
        return cls(
            anchor_id=_identifier(raw["anchorId"], f"{field}.anchorId"),
            artifact_path=_text(
                raw["artifactPath"], f"{field}.artifactPath", limit=512
            ),
            json_pointer=_text(
                raw["jsonPointer"], f"{field}.jsonPointer", limit=512
            ),
            artifact_hash=_digest(raw["artifactHash"], f"{field}.artifactHash"),
            value_hash=_digest(raw["valueHash"], f"{field}.valueHash"),
            verifier_hash=_digest(raw["verifierHash"], f"{field}.verifierHash"),
            grounded=_boolean(raw["grounded"], f"{field}.grounded"),
            independent_check=_boolean(
                raw["independentCheck"], f"{field}.independentCheck"
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "anchorId": self.anchor_id,
            "artifactPath": self.artifact_path,
            "jsonPointer": self.json_pointer,
            "artifactHash": self.artifact_hash,
            "valueHash": self.value_hash,
            "verifierHash": self.verifier_hash,
            "grounded": self.grounded,
            "independentCheck": self.independent_check,
        }


@dataclass(frozen=True)
class DiagnosticArmReceipt:
    arm_id: str
    guidance_hash: str
    request_hash: str
    response_hash: str

    @classmethod
    def from_mapping(
        cls, raw: Mapping[str, Any], field: str
    ) -> "DiagnosticArmReceipt":
        _exact(
            raw,
            {"armId", "guidanceHash", "requestHash", "responseHash"},
            field,
        )
        return cls(
            arm_id=_identifier(raw["armId"], f"{field}.armId"),
            guidance_hash=_digest(raw["guidanceHash"], f"{field}.guidanceHash"),
            request_hash=_digest(raw["requestHash"], f"{field}.requestHash"),
            response_hash=_digest(raw["responseHash"], f"{field}.responseHash"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "armId": self.arm_id,
            "guidanceHash": self.guidance_hash,
            "requestHash": self.request_hash,
            "responseHash": self.response_hash,
        }


@dataclass(frozen=True)
class DiagnosticCertificate:
    schema_version: str
    semantics_id: str
    task_hash: str
    parent_generator_hash: str
    harness_hash: str
    evaluator_hash: str
    budget_hash: str
    evidence_package_hash: str
    prediction_hash: str
    outcome_reveal_hash: str
    access_level: str
    predicted_best_arm: str
    diagnostic_stage: str
    root_mechanism: str
    prediction_frozen_at: int
    outcome_revealed_at: int
    arms: tuple[DiagnosticArmReceipt, ...]
    anchors: tuple[DiagnosticAnchor, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "DiagnosticCertificate":
        expected = {
            "schemaVersion",
            "semanticsId",
            "taskHash",
            "parentGeneratorHash",
            "harnessHash",
            "evaluatorHash",
            "budgetHash",
            "evidencePackageHash",
            "predictionHash",
            "outcomeRevealHash",
            "accessLevel",
            "predictedBestArm",
            "diagnosticStage",
            "rootMechanism",
            "predictionFrozenAt",
            "outcomeRevealedAt",
            "arms",
            "anchors",
        }
        _exact(raw, expected, "diagnostic_certificate")
        if raw["schemaVersion"] != SCHEMA_VERSION:
            raise SchemaError("unsupported diagnostic schemaVersion")
        if raw["semanticsId"] != SEMANTICS_ID:
            raise SchemaError("unsupported diagnostic semanticsId")
        access = _text(raw["accessLevel"], "diagnostic_certificate.accessLevel")
        if access not in ACCESS_LEVELS:
            raise SchemaError("unsupported diagnostic accessLevel")
        stage = _text(raw["diagnosticStage"], "diagnostic_certificate.diagnosticStage")
        if stage not in DIAGNOSTIC_STAGES:
            raise SchemaError("unsupported diagnosticStage")
        mechanism = _text(raw["rootMechanism"], "diagnostic_certificate.rootMechanism")
        if mechanism not in ROOT_MECHANISMS:
            raise SchemaError("unsupported rootMechanism")
        arms_raw = raw["arms"]
        anchors_raw = raw["anchors"]
        if not isinstance(arms_raw, list):
            raise SchemaError("diagnostic_certificate.arms must be a list")
        if not isinstance(anchors_raw, list):
            raise SchemaError("diagnostic_certificate.anchors must be a list")
        return cls(
            schema_version=SCHEMA_VERSION,
            semantics_id=SEMANTICS_ID,
            task_hash=_digest(raw["taskHash"], "diagnostic_certificate.taskHash"),
            parent_generator_hash=_digest(
                raw["parentGeneratorHash"],
                "diagnostic_certificate.parentGeneratorHash",
            ),
            harness_hash=_digest(raw["harnessHash"], "diagnostic_certificate.harnessHash"),
            evaluator_hash=_digest(
                raw["evaluatorHash"], "diagnostic_certificate.evaluatorHash"
            ),
            budget_hash=_digest(raw["budgetHash"], "diagnostic_certificate.budgetHash"),
            evidence_package_hash=_digest(
                raw["evidencePackageHash"],
                "diagnostic_certificate.evidencePackageHash",
            ),
            prediction_hash=_digest(
                raw["predictionHash"], "diagnostic_certificate.predictionHash"
            ),
            outcome_reveal_hash=_digest(
                raw["outcomeRevealHash"],
                "diagnostic_certificate.outcomeRevealHash",
            ),
            access_level=access,
            predicted_best_arm=_identifier(
                raw["predictedBestArm"],
                "diagnostic_certificate.predictedBestArm",
            ),
            diagnostic_stage=stage,
            root_mechanism=mechanism,
            prediction_frozen_at=_nat(
                raw["predictionFrozenAt"],
                "diagnostic_certificate.predictionFrozenAt",
            ),
            outcome_revealed_at=_nat(
                raw["outcomeRevealedAt"],
                "diagnostic_certificate.outcomeRevealedAt",
            ),
            arms=tuple(
                DiagnosticArmReceipt.from_mapping(item, f"diagnostic_certificate.arms[{i}]")
                if isinstance(item, dict)
                else _raise_mapping(f"diagnostic_certificate.arms[{i}]")
                for i, item in enumerate(arms_raw)
            ),
            anchors=tuple(
                DiagnosticAnchor.from_mapping(
                    item, f"diagnostic_certificate.anchors[{i}]"
                )
                if isinstance(item, dict)
                else _raise_mapping(f"diagnostic_certificate.anchors[{i}]")
                for i, item in enumerate(anchors_raw)
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": self.schema_version,
            "semanticsId": self.semantics_id,
            "taskHash": self.task_hash,
            "parentGeneratorHash": self.parent_generator_hash,
            "harnessHash": self.harness_hash,
            "evaluatorHash": self.evaluator_hash,
            "budgetHash": self.budget_hash,
            "evidencePackageHash": self.evidence_package_hash,
            "predictionHash": self.prediction_hash,
            "outcomeRevealHash": self.outcome_reveal_hash,
            "accessLevel": self.access_level,
            "predictedBestArm": self.predicted_best_arm,
            "diagnosticStage": self.diagnostic_stage,
            "rootMechanism": self.root_mechanism,
            "predictionFrozenAt": self.prediction_frozen_at,
            "outcomeRevealedAt": self.outcome_revealed_at,
            "arms": [arm.to_dict() for arm in self.arms],
            "anchors": [anchor.to_dict() for anchor in self.anchors],
        }


def _raise_mapping(field: str):
    raise SchemaError(f"{field} must be an object")


def resolve_json_pointer(document: Any, pointer: str) -> Any:
    """Resolve the strict RFC 6901 subset used by diagnostic anchors."""

    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise SchemaError("diagnostic anchor JSON pointer must start with '/'")
    value = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            if not token.isdigit():
                raise SchemaError("diagnostic anchor list pointer must be numeric")
            index = int(token)
            if index >= len(value):
                raise SchemaError("diagnostic anchor list pointer is out of range")
            value = value[index]
        elif isinstance(value, dict):
            if token not in value:
                raise SchemaError("diagnostic anchor object pointer is absent")
            value = value[token]
        else:
            raise SchemaError("diagnostic anchor traverses a scalar value")
    return value


def verify_anchor_binding(
    anchor: DiagnosticAnchor,
    run_root: Path,
    *,
    expected_verifier_hash: str,
) -> tuple[str, ...]:
    """Replay an anchor against the immutable evidence package."""

    reasons: list[str] = []
    root = run_root.resolve()
    candidate = (root / anchor.artifact_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return ("anchor artifact path escapes the evidence package",)
    if not candidate.is_file():
        return ("anchor artifact file is absent",)
    if file_digest(candidate) != anchor.artifact_hash:
        reasons.append("anchor artifact hash mismatch")
    try:
        document = json.loads(candidate.read_text(encoding="utf-8"))
        value = resolve_json_pointer(document, anchor.json_pointer)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, SchemaError) as error:
        reasons.append(f"anchor JSON binding failed: {error}")
    else:
        if digest(value) != anchor.value_hash:
            reasons.append("anchor value hash mismatch")
    if anchor.verifier_hash != expected_verifier_hash:
        reasons.append("anchor verifier hash mismatch")
    return tuple(reasons)


class DiagnosticStatus(str, Enum):
    ACCEPTED = "diagnostic_admissible"
    REJECTED = "rejected"


@dataclass(frozen=True)
class DiagnosticReport:
    status: DiagnosticStatus
    reasons: tuple[str, ...]
    arm_count: int
    anchor_count: int

    @property
    def accepted(self) -> bool:
        return self.status is DiagnosticStatus.ACCEPTED


def verify_diagnostic_certificate(
    certificate: DiagnosticCertificate,
    *,
    run_root: Path | None = None,
    expected_verifier_hash: str | None = None,
) -> DiagnosticReport:
    reasons: list[str] = []
    arm_ids = [arm.arm_id for arm in certificate.arms]
    guidance_hashes = [arm.guidance_hash for arm in certificate.arms]
    anchor_ids = [anchor.anchor_id for anchor in certificate.anchors]
    if len(certificate.arms) < 2:
        reasons.append("at least two matched guidance arms are required")
    if len(set(arm_ids)) != len(arm_ids):
        reasons.append("arm identifiers must be unique")
    if len(set(guidance_hashes)) != len(guidance_hashes):
        reasons.append("guidance hashes must be unique")
    if certificate.predicted_best_arm not in arm_ids:
        reasons.append("predictedBestArm is not a registered arm")
    if certificate.prediction_frozen_at >= certificate.outcome_revealed_at:
        reasons.append("prediction must be frozen before hidden outcome reveal")
    if not certificate.anchors:
        reasons.append("at least one evidence anchor is required")
    if len(set(anchor_ids)) != len(anchor_ids):
        reasons.append("anchor identifiers must be unique")
    for index, anchor in enumerate(certificate.anchors):
        if not anchor.grounded:
            reasons.append(f"anchor {index} is not grounded")
        if not anchor.independent_check:
            reasons.append(f"anchor {index} lacks an independent check")
        if run_root is not None:
            if expected_verifier_hash is None:
                reasons.append("expected verifier hash is required for anchor replay")
            else:
                reasons.extend(
                    f"anchor {index}: {reason}"
                    for reason in verify_anchor_binding(
                        anchor,
                        run_root,
                        expected_verifier_hash=expected_verifier_hash,
                    )
                )
    status = DiagnosticStatus.REJECTED if reasons else DiagnosticStatus.ACCEPTED
    return DiagnosticReport(status, tuple(reasons), len(arm_ids), len(anchor_ids))
