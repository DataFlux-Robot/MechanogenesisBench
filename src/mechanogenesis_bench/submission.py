from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from .canonical import digest
from .errors import SchemaError
from .models import EvidenceTier, ResourceVector, require_mapping, require_number, require_text


MRS_FIELDS = (
    "language",
    "semantics",
    "compiler",
    "compiler_certificate",
    "theory_portfolio",
    "construction_program",
    "experiment_program",
    "evaluator_contract",
    "update_proposal",
)


def _require_digest(value: Any, field: str) -> str:
    text = require_text(value, field)
    if not text.startswith("sha256:") or len(text) != 71:
        raise SchemaError(f"{field} must be a sha256 content digest")
    try:
        int(text[7:], 16)
    except ValueError as error:
        raise SchemaError(f"{field} contains a non-hex digest") from error
    return text


@dataclass(frozen=True)
class MaterialBalance:
    material: str
    input_q: int
    reserve_draw_q: int
    output_q: int
    waste_q: int

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "MaterialBalance":
        values: dict[str, Any] = {"material": require_text(raw.get("material"), f"{field}.material")}
        for name in ("input_q", "reserve_draw_q", "output_q", "waste_q"):
            value = raw.get(name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise SchemaError(f"{field}.{name} must be a nonnegative integer")
            values[name] = value
        return cls(**values)

    @property
    def closes(self) -> bool:
        return self.input_q + self.reserve_draw_q == self.output_q + self.waste_q


@dataclass(frozen=True)
class ConstructionReceipt:
    operation_hash: str
    parent_world_hash: str
    child_world_hash: str
    balances: tuple[MaterialBalance, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "ConstructionReceipt":
        raw_balances = raw.get("balances")
        if not isinstance(raw_balances, list) or not raw_balances:
            raise SchemaError(f"{field}.balances must be a non-empty list")
        balances = tuple(
            MaterialBalance.from_mapping(require_mapping(item, f"{field}.balances[{index}]"), f"{field}.balances[{index}]")
            for index, item in enumerate(raw_balances)
        )
        if len({item.material for item in balances}) != len(balances):
            raise SchemaError(f"{field}.balances contains duplicate materials")
        return cls(
            operation_hash=_require_digest(raw.get("operation_hash"), f"{field}.operation_hash"),
            parent_world_hash=_require_digest(raw.get("parent_world_hash"), f"{field}.parent_world_hash"),
            child_world_hash=_require_digest(raw.get("child_world_hash"), f"{field}.child_world_hash"),
            balances=balances,
        )


@dataclass(frozen=True)
class GenerationSubmission:
    index: int
    parent_process_hash: str
    child_process_hash: str
    parent_world_hash: str
    child_world_hash: str
    mrs: dict[str, str]
    artifact: dict[str, Any]
    artifact_hash: str
    construction_receipts: tuple[ConstructionReceipt, ...]
    experiment_receipts: tuple[dict[str, Any], ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "GenerationSubmission":
        index = raw.get("index")
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise SchemaError(f"{field}.index must be a nonnegative integer")
        raw_mrs = require_mapping(raw.get("mrs"), f"{field}.mrs")
        if set(raw_mrs) != set(MRS_FIELDS):
            missing = sorted(set(MRS_FIELDS) - set(raw_mrs))
            extra = sorted(set(raw_mrs) - set(MRS_FIELDS))
            raise SchemaError(f"{field}.mrs fields mismatch; missing={missing}, extra={extra}")
        mrs = {name: _require_digest(raw_mrs[name], f"{field}.mrs.{name}") for name in MRS_FIELDS}
        artifact = dict(require_mapping(raw.get("artifact"), f"{field}.artifact"))
        artifact_hash = _require_digest(raw.get("artifact_hash"), f"{field}.artifact_hash")
        if artifact_hash != digest(artifact):
            raise SchemaError(f"{field}.artifact_hash does not bind the artifact")
        receipts_raw = raw.get("construction_receipts")
        if not isinstance(receipts_raw, list) or not receipts_raw:
            raise SchemaError(f"{field}.construction_receipts must be non-empty")
        receipts = tuple(
            ConstructionReceipt.from_mapping(require_mapping(item, f"{field}.construction_receipts[{i}]"), f"{field}.construction_receipts[{i}]")
            for i, item in enumerate(receipts_raw)
        )
        experiments = raw.get("experiment_receipts")
        if not isinstance(experiments, list) or not experiments:
            raise SchemaError(f"{field}.experiment_receipts must be non-empty")
        experiment_receipts = tuple(dict(require_mapping(item, f"{field}.experiment_receipts")) for item in experiments)
        return cls(
            index=index,
            parent_process_hash=_require_digest(raw.get("parent_process_hash"), f"{field}.parent_process_hash"),
            child_process_hash=_require_digest(raw.get("child_process_hash"), f"{field}.child_process_hash"),
            parent_world_hash=_require_digest(raw.get("parent_world_hash"), f"{field}.parent_world_hash"),
            child_world_hash=_require_digest(raw.get("child_world_hash"), f"{field}.child_world_hash"),
            mrs=mrs,
            artifact=artifact,
            artifact_hash=artifact_hash,
            construction_receipts=receipts,
            experiment_receipts=experiment_receipts,
        )


@dataclass(frozen=True)
class Submission:
    schema_version: str
    system_name: str
    system_version: str
    declared_evidence_tier: EvidenceTier
    resource_use: ResourceVector
    generations: tuple[GenerationSubmission, ...]

    @classmethod
    def load(cls, path: str | Path) -> "Submission":
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SchemaError(f"cannot load submission: {error}") from error
        root = require_mapping(raw, "submission")
        schema_version = require_text(root.get("schema_version"), "submission.schema_version")
        if schema_version != "0.1":
            raise SchemaError("unsupported submission schema version")
        try:
            tier = EvidenceTier(require_text(root.get("declared_evidence_tier"), "declared_evidence_tier"))
        except ValueError as error:
            raise SchemaError(str(error)) from error
        raw_generations = root.get("generations")
        if not isinstance(raw_generations, list) or not raw_generations:
            raise SchemaError("submission.generations must be non-empty")
        generations = tuple(
            GenerationSubmission.from_mapping(require_mapping(item, f"generations[{index}]"), f"generations[{index}]")
            for index, item in enumerate(raw_generations)
        )
        if tuple(item.index for item in generations) != tuple(range(len(generations))):
            raise SchemaError("generation indices must be contiguous from zero")
        object_store = Path(path).parent / "objects"
        for generation in generations:
            for name, object_digest in generation.mrs.items():
                object_path = object_store / f"{object_digest[7:]}.json"
                try:
                    value = json.loads(object_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as error:
                    raise SchemaError(
                        f"MRS object {name} is missing or malformed: {object_path}"
                    ) from error
                if digest(value) != object_digest:
                    raise SchemaError(f"MRS object {name} does not match its content digest")
        return cls(
            schema_version=schema_version,
            system_name=require_text(root.get("system_name"), "system_name"),
            system_version=require_text(root.get("system_version"), "system_version"),
            declared_evidence_tier=tier,
            resource_use=ResourceVector.from_mapping(require_mapping(root.get("resource_use"), "resource_use"), "resource_use"),
            generations=generations,
        )


@dataclass(frozen=True)
class GenerationDecision:
    index: int
    artifact_hash: str
    accepted: bool
    before_upper: float
    after_lower: float
    margin: float
    net_value: float
    robustness_pass_rate: float
    evidence_tier: EvidenceTier
    rrc_time_rate_delta: float
    rrc_budget_rate_delta: float

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "GenerationDecision":
        index = raw.get("index")
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise SchemaError(f"{field}.index must be a nonnegative integer")
        accepted = raw.get("accepted")
        if not isinstance(accepted, bool):
            raise SchemaError(f"{field}.accepted must be Boolean")
        try:
            tier = EvidenceTier(require_text(raw.get("evidence_tier"), f"{field}.evidence_tier"))
        except ValueError as error:
            raise SchemaError(str(error)) from error
        robustness = require_number(raw.get("robustness_pass_rate"), f"{field}.robustness_pass_rate", nonnegative=True)
        if robustness > 1:
            raise SchemaError(f"{field}.robustness_pass_rate must be <= 1")
        return cls(
            index=index,
            artifact_hash=_require_digest(raw.get("artifact_hash"), f"{field}.artifact_hash"),
            accepted=accepted,
            before_upper=require_number(raw.get("before_upper"), f"{field}.before_upper"),
            after_lower=require_number(raw.get("after_lower"), f"{field}.after_lower"),
            margin=require_number(raw.get("margin"), f"{field}.margin", nonnegative=True),
            net_value=require_number(raw.get("net_value"), f"{field}.net_value"),
            robustness_pass_rate=robustness,
            evidence_tier=tier,
            rrc_time_rate_delta=require_number(raw.get("rrc_time_rate_delta", 0.0), f"{field}.rrc_time_rate_delta"),
            rrc_budget_rate_delta=require_number(raw.get("rrc_budget_rate_delta", 0.0), f"{field}.rrc_budget_rate_delta"),
        )


@dataclass(frozen=True)
class EvaluationReport:
    schema_version: str
    task_id: str
    task_package_digest: str
    decisions: tuple[GenerationDecision, ...]
    evaluator_digest: str

    @classmethod
    def load(cls, path: str | Path) -> "EvaluationReport":
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SchemaError(f"cannot load evaluation report: {error}") from error
        root = require_mapping(raw, "evaluation")
        version = require_text(root.get("schema_version"), "evaluation.schema_version")
        if version != "0.1":
            raise SchemaError("unsupported evaluation schema version")
        raw_decisions = root.get("decisions")
        if not isinstance(raw_decisions, list):
            raise SchemaError("evaluation.decisions must be a list")
        decisions = tuple(
            GenerationDecision.from_mapping(require_mapping(item, f"decisions[{index}]"), f"decisions[{index}]")
            for index, item in enumerate(raw_decisions)
        )
        return cls(
            schema_version=version,
            task_id=require_text(root.get("task_id"), "evaluation.task_id"),
            task_package_digest=_require_digest(root.get("task_package_digest"), "evaluation.task_package_digest"),
            decisions=decisions,
            evaluator_digest=_require_digest(root.get("evaluator_digest"), "evaluation.evaluator_digest"),
        )
