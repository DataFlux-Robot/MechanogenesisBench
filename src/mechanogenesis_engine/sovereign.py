from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import json
import tempfile
from typing import Any, Mapping

from mechanogenesis_bench.canonical import digest

from .errors import ExecutionError, IRValidationError
from .interpreter import ExecutionResult
from .ir import MechanismProgram, WorldSpec, program_to_dict, world_to_dict


SOVEREIGN_SCHEMA_VERSION = "0.1"
SOVEREIGN_SEMANTICS_ID = "Mechanogenesis.SovereignKernel.v0.1"
SOVEREIGN_BACKEND_ID = "python_reference_interpreter_v0.4"
REQUIRED_ASSUMPTIONS = {
    "fixed_point_arithmetic",
    "hash_identity",
    "reference_model_fidelity",
}
KNOWN_ASSUMPTION_KINDS = {
    "physical_model",
    "calibration",
    "environment",
    "cryptographic_identity",
    "numerical_approximation",
}


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise IRValidationError(f"{field} must be an object")
    return value


def _exact(raw: Mapping[str, Any], expected: set[str], field: str) -> None:
    if set(raw) != expected:
        raise IRValidationError(
            f"{field} fields mismatch; missing={sorted(expected - set(raw))}, "
            f"extra={sorted(set(raw) - expected)}"
        )


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise IRValidationError(f"{field} must be non-empty text")
    return value


def _nat(value: Any, field: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise IRValidationError(f"{field} must be an integer")
    if value < (1 if positive else 0):
        qualifier = "positive" if positive else "nonnegative"
        raise IRValidationError(f"{field} must be {qualifier}")
    return value


def _digest(value: Any, field: str) -> str:
    text = _text(value, field)
    if len(text) != 71 or not text.startswith("sha256:"):
        raise IRValidationError(f"{field} must be a sha256 digest")
    try:
        int(text[7:], 16)
    except ValueError as error:
        raise IRValidationError(f"{field} contains non-hex digest data") from error
    return text


@dataclass(frozen=True)
class SovereignAssumption:
    assumption_id: str
    kind: str
    statement_hash: str
    scope_hash: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "SovereignAssumption":
        _exact(raw, {"assumptionId", "kind", "statementHash", "scopeHash"}, field)
        kind = _text(raw["kind"], f"{field}.kind")
        if kind not in KNOWN_ASSUMPTION_KINDS:
            raise IRValidationError(f"{field}.kind is not sovereign-kernel defined")
        return cls(
            assumption_id=_text(raw["assumptionId"], f"{field}.assumptionId"),
            kind=kind,
            statement_hash=_digest(raw["statementHash"], f"{field}.statementHash"),
            scope_hash=_digest(raw["scopeHash"], f"{field}.scopeHash"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "assumptionId": self.assumption_id,
            "kind": self.kind,
            "statementHash": self.statement_hash,
            "scopeHash": self.scope_hash,
        }


@dataclass(frozen=True)
class SovereignBalance:
    material: str
    input_q: int
    reserve_draw_q: int
    output_q: int
    waste_q: int

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "SovereignBalance":
        _exact(raw, {"material", "inputQ", "reserveDrawQ", "outputQ", "wasteQ"}, field)
        return cls(
            material=_text(raw["material"], f"{field}.material"),
            input_q=_nat(raw["inputQ"], f"{field}.inputQ"),
            reserve_draw_q=_nat(raw["reserveDrawQ"], f"{field}.reserveDrawQ"),
            output_q=_nat(raw["outputQ"], f"{field}.outputQ"),
            waste_q=_nat(raw["wasteQ"], f"{field}.wasteQ"),
        )

    @property
    def closed(self) -> bool:
        return self.input_q + self.reserve_draw_q == self.output_q + self.waste_q

    def to_dict(self) -> dict[str, object]:
        return {
            "material": self.material,
            "inputQ": self.input_q,
            "reserveDrawQ": self.reserve_draw_q,
            "outputQ": self.output_q,
            "wasteQ": self.waste_q,
        }


@dataclass(frozen=True)
class SovereignReceipt:
    index: int
    operation_hash: str
    parent_world_hash: str
    child_world_hash: str
    balances: tuple[SovereignBalance, ...]
    duration_us: int
    energy_mj: int

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "SovereignReceipt":
        _exact(
            raw,
            {
                "index",
                "operationHash",
                "parentWorldHash",
                "childWorldHash",
                "balances",
                "durationUs",
                "energyMj",
            },
            field,
        )
        balances_raw = raw["balances"]
        if not isinstance(balances_raw, list) or not balances_raw:
            raise IRValidationError(f"{field}.balances must be non-empty")
        return cls(
            index=_nat(raw["index"], f"{field}.index"),
            operation_hash=_digest(raw["operationHash"], f"{field}.operationHash"),
            parent_world_hash=_digest(
                raw["parentWorldHash"], f"{field}.parentWorldHash"
            ),
            child_world_hash=_digest(raw["childWorldHash"], f"{field}.childWorldHash"),
            balances=tuple(
                SovereignBalance.from_mapping(
                    _mapping(item, f"{field}.balances[{index}]"),
                    f"{field}.balances[{index}]",
                )
                for index, item in enumerate(balances_raw)
            ),
            duration_us=_nat(raw["durationUs"], f"{field}.durationUs"),
            energy_mj=_nat(raw["energyMj"], f"{field}.energyMj"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "operationHash": self.operation_hash,
            "parentWorldHash": self.parent_world_hash,
            "childWorldHash": self.child_world_hash,
            "balances": [item.to_dict() for item in self.balances],
            "durationUs": self.duration_us,
            "energyMj": self.energy_mj,
        }


@dataclass(frozen=True)
class SovereignCertificate:
    schema_version: str
    semantics_id: str
    backend_id: str
    trust_class: str
    evidence_tier: str
    strategy_hash: str
    candidate_support_size: int
    attempted_candidates: int
    world_spec_hash: str
    parent_world_hash: str
    program_hash: str
    sequence_before: int
    child_world_hash: str
    sequence_after: int
    total_duration_us: int
    total_energy_mj: int
    assumptions: tuple[SovereignAssumption, ...]
    receipts: tuple[SovereignReceipt, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "SovereignCertificate":
        _exact(
            raw,
            {
                "schemaVersion",
                "semanticsId",
                "backendId",
                "trustClass",
                "evidenceTier",
                "strategyHash",
                "candidateSupportSize",
                "attemptedCandidates",
                "input",
                "output",
                "assumptions",
                "receipts",
            },
            "sovereign_certificate",
        )
        input_raw = _mapping(raw["input"], "sovereign_certificate.input")
        output_raw = _mapping(raw["output"], "sovereign_certificate.output")
        _exact(
            input_raw,
            {"worldSpecHash", "parentWorldHash", "programHash", "sequenceBefore"},
            "sovereign_certificate.input",
        )
        _exact(
            output_raw,
            {"childWorldHash", "sequenceAfter", "totalDurationUs", "totalEnergyMj"},
            "sovereign_certificate.output",
        )
        assumptions_raw = raw["assumptions"]
        receipts_raw = raw["receipts"]
        if not isinstance(assumptions_raw, list) or not assumptions_raw:
            raise IRValidationError(
                "sovereign_certificate.assumptions must be non-empty"
            )
        if not isinstance(receipts_raw, list) or not receipts_raw:
            raise IRValidationError("sovereign_certificate.receipts must be non-empty")
        certificate = cls(
            schema_version=_text(raw["schemaVersion"], "schemaVersion"),
            semantics_id=_text(raw["semanticsId"], "semanticsId"),
            backend_id=_text(raw["backendId"], "backendId"),
            trust_class=_text(raw["trustClass"], "trustClass"),
            evidence_tier=_text(raw["evidenceTier"], "evidenceTier"),
            strategy_hash=_digest(raw["strategyHash"], "strategyHash"),
            candidate_support_size=_nat(
                raw["candidateSupportSize"], "candidateSupportSize", positive=True
            ),
            attempted_candidates=_nat(
                raw["attemptedCandidates"], "attemptedCandidates", positive=True
            ),
            world_spec_hash=_digest(input_raw["worldSpecHash"], "input.worldSpecHash"),
            parent_world_hash=_digest(
                input_raw["parentWorldHash"], "input.parentWorldHash"
            ),
            program_hash=_digest(input_raw["programHash"], "input.programHash"),
            sequence_before=_nat(input_raw["sequenceBefore"], "input.sequenceBefore"),
            child_world_hash=_digest(
                output_raw["childWorldHash"], "output.childWorldHash"
            ),
            sequence_after=_nat(output_raw["sequenceAfter"], "output.sequenceAfter"),
            total_duration_us=_nat(
                output_raw["totalDurationUs"], "output.totalDurationUs"
            ),
            total_energy_mj=_nat(output_raw["totalEnergyMj"], "output.totalEnergyMj"),
            assumptions=tuple(
                SovereignAssumption.from_mapping(
                    _mapping(item, f"assumptions[{index}]"),
                    f"assumptions[{index}]",
                )
                for index, item in enumerate(assumptions_raw)
            ),
            receipts=tuple(
                SovereignReceipt.from_mapping(
                    _mapping(item, f"receipts[{index}]"), f"receipts[{index}]"
                )
                for index, item in enumerate(receipts_raw)
            ),
        )
        certificate.verify()
        return certificate

    def verify(self) -> None:
        if self.schema_version != SOVEREIGN_SCHEMA_VERSION:
            raise IRValidationError("unsupported sovereign certificate version")
        if self.semantics_id != SOVEREIGN_SEMANTICS_ID:
            raise IRValidationError("certificate does not target the sovereign kernel")
        if self.trust_class != "certificate_checked":
            raise IRValidationError("reference backend must be certificate_checked")
        if self.evidence_tier != "conformance":
            raise IRValidationError("reference backend cannot claim above conformance")
        if self.attempted_candidates > self.candidate_support_size:
            raise IRValidationError("attempts exceed generated strategy support")
        ids = [item.assumption_id for item in self.assumptions]
        if len(ids) != len(set(ids)):
            raise IRValidationError("assumption ledger contains duplicate ids")
        if not REQUIRED_ASSUMPTIONS <= set(ids):
            raise IRValidationError(
                "assumption ledger omits a required sovereign assumption"
            )
        previous = self.parent_world_hash
        for expected, receipt in enumerate(self.receipts):
            if receipt.index != expected:
                raise IRValidationError(
                    "sovereign receipts are not consecutively indexed"
                )
            if receipt.parent_world_hash != previous:
                raise IRValidationError("sovereign receipt lineage is broken")
            if not all(balance.closed for balance in receipt.balances):
                raise IRValidationError("sovereign receipt violates material closure")
            previous = receipt.child_world_hash
        if previous != self.child_world_hash:
            raise IRValidationError(
                "sovereign receipt chain does not reach child world"
            )
        if self.sequence_after != self.sequence_before + len(self.receipts):
            raise IRValidationError("sovereign world sequence does not match receipts")
        if self.total_duration_us != sum(item.duration_us for item in self.receipts):
            raise IRValidationError("sovereign duration total does not match receipts")
        if self.total_energy_mj != sum(item.energy_mj for item in self.receipts):
            raise IRValidationError("sovereign energy total does not match receipts")

    def to_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": self.schema_version,
            "semanticsId": self.semantics_id,
            "backendId": self.backend_id,
            "trustClass": self.trust_class,
            "evidenceTier": self.evidence_tier,
            "strategyHash": self.strategy_hash,
            "candidateSupportSize": self.candidate_support_size,
            "attemptedCandidates": self.attempted_candidates,
            "input": {
                "worldSpecHash": self.world_spec_hash,
                "parentWorldHash": self.parent_world_hash,
                "programHash": self.program_hash,
                "sequenceBefore": self.sequence_before,
            },
            "output": {
                "childWorldHash": self.child_world_hash,
                "sequenceAfter": self.sequence_after,
                "totalDurationUs": self.total_duration_us,
                "totalEnergyMj": self.total_energy_mj,
            },
            "assumptions": [item.to_dict() for item in self.assumptions],
            "receipts": [item.to_dict() for item in self.receipts],
        }


def certificate_from_execution(
    world: WorldSpec,
    program: MechanismProgram,
    execution: ExecutionResult,
    *,
    strategy_hash: str,
    candidate_support_size: int,
    attempted_candidates: int,
) -> SovereignCertificate:
    world_spec_hash = digest(world_to_dict(world))
    program_hash = digest(program_to_dict(program))
    if program_hash != execution.process_hash:
        raise ExecutionError("execution process hash does not bind the program")
    final_sequence = execution.final_state.get("sequence")
    if isinstance(final_sequence, bool) or not isinstance(final_sequence, int):
        raise ExecutionError("execution final state has no sovereign sequence")
    sequence_before = final_sequence - len(execution.receipts)
    if sequence_before < 0:
        raise ExecutionError("execution sequence precedes zero")
    assumptions = (
        SovereignAssumption(
            assumption_id="fixed_point_arithmetic",
            kind="numerical_approximation",
            statement_hash=digest(
                {
                    "statement": "canonical physical quantities use declared integer quanta"
                }
            ),
            scope_hash=world_spec_hash,
        ),
        SovereignAssumption(
            assumption_id="hash_identity",
            kind="cryptographic_identity",
            statement_hash=digest(
                {"statement": "sha256 digests identify canonical serialized content"}
            ),
            scope_hash=program_hash,
        ),
        SovereignAssumption(
            assumption_id="reference_model_fidelity",
            kind="physical_model",
            statement_hash=digest(
                {
                    "statement": (
                        "axis-aligned geometry, additive error budgets and declared "
                        "machine bounds are adequate for this conformance claim"
                    )
                }
            ),
            scope_hash=world_spec_hash,
        ),
    )
    receipts = tuple(
        SovereignReceipt(
            index=item.index,
            operation_hash=item.operation_hash,
            parent_world_hash=item.parent_world_hash,
            child_world_hash=item.child_world_hash,
            balances=tuple(
                SovereignBalance(
                    material=balance.material,
                    input_q=balance.input_q,
                    reserve_draw_q=balance.reserve_draw_q,
                    output_q=balance.output_q,
                    waste_q=balance.waste_q,
                )
                for balance in item.balances
            ),
            duration_us=item.duration_us,
            energy_mj=item.energy_mj,
        )
        for item in execution.receipts
    )
    certificate = SovereignCertificate(
        schema_version=SOVEREIGN_SCHEMA_VERSION,
        semantics_id=SOVEREIGN_SEMANTICS_ID,
        backend_id=SOVEREIGN_BACKEND_ID,
        trust_class="certificate_checked",
        evidence_tier="conformance",
        strategy_hash=_digest(strategy_hash, "strategy_hash"),
        candidate_support_size=_nat(
            candidate_support_size, "candidate_support_size", positive=True
        ),
        attempted_candidates=_nat(
            attempted_candidates, "attempted_candidates", positive=True
        ),
        world_spec_hash=world_spec_hash,
        parent_world_hash=execution.parent_world_hash,
        program_hash=program_hash,
        sequence_before=sequence_before,
        child_world_hash=execution.child_world_hash,
        sequence_after=final_sequence,
        total_duration_us=execution.total_duration_us,
        total_energy_mj=execution.total_energy_mj,
        assumptions=assumptions,
        receipts=receipts,
    )
    certificate.verify()
    return certificate


def find_sovereign_checker(repository_root: Path | None = None) -> Path | None:
    configured = shutil.which("sovereignCheck")
    if configured:
        return Path(configured)
    if repository_root is not None:
        candidate = repository_root / ".lake/build/bin/sovereignCheck"
        if candidate.is_file():
            return candidate
    return None


def find_promotion_checker(repository_root: Path | None = None) -> Path | None:
    configured = shutil.which("promotionCheck")
    if configured:
        return Path(configured)
    if repository_root is not None:
        candidate = repository_root / ".lake/build/bin/promotionCheck"
        if candidate.is_file():
            return candidate
    return None


def promotion_envelope(
    certificate: SovereignCertificate,
    *,
    artifact_hash: str,
    parent_error_upper: int,
    child_error_upper: int,
    required_improvement: int,
    net_value: int,
    robustness_passed: bool,
) -> dict[str, object]:
    """Bind an evaluator claim to the exact certified physical transition."""
    return {
        "certificate": certificate.to_dict(),
        "decision": {
            "schemaVersion": SOVEREIGN_SCHEMA_VERSION,
            "semanticsId": SOVEREIGN_SEMANTICS_ID,
            "artifactHash": _digest(artifact_hash, "artifact_hash"),
            "parentWorldHash": certificate.parent_world_hash,
            "childWorldHash": certificate.child_world_hash,
            "parentErrorUpper": _nat(parent_error_upper, "parent_error_upper"),
            "childErrorUpper": _nat(child_error_upper, "child_error_upper"),
            "requiredImprovement": _nat(
                required_improvement, "required_improvement", positive=True
            ),
            "netValue": _nat(net_value, "net_value", positive=True),
            "robustnessPassed": bool(robustness_passed),
            "evidenceTier": certificate.evidence_tier,
        },
    }


def verify_with_lean(certificate_path: Path, checker: Path) -> None:
    try:
        result = subprocess.run(
            [str(checker), str(certificate_path)],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        raise ExecutionError(
            f"cannot execute Lean sovereign checker: {error}"
        ) from error
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise ExecutionError(f"Lean sovereign checker rejected certificate: {message}")


def verify_promotion_with_lean(envelope: Mapping[str, Any], checker: Path) -> None:
    """Require the Lean kernel to accept an evaluator's bound promotion."""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json"
        ) as handle:
            json.dump(envelope, handle, indent=2, sort_keys=True)
            handle.flush()
            result = subprocess.run(
                [str(checker), handle.name],
                text=True,
                capture_output=True,
                check=False,
            )
    except OSError as error:
        raise ExecutionError(
            f"cannot execute Lean promotion checker: {error}"
        ) from error
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise ExecutionError(f"Lean promotion checker rejected decision: {message}")
