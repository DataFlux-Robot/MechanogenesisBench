from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from mechanogenesis_engine.compiler import load_world
from mechanogenesis_engine.errors import ExecutionError, IRValidationError
from mechanogenesis_engine.fixture_search import FixtureGoal
from mechanogenesis_engine.gtheta import (
    GThetaRuntime,
    ReferenceResearchProposer,
    ResearchRequest,
)
from mechanogenesis_engine.sovereign import (
    REQUIRED_ASSUMPTIONS,
    SOVEREIGN_SEMANTICS_ID,
    SovereignCertificate,
    find_promotion_checker,
    find_sovereign_checker,
    promotion_envelope,
    verify_promotion_with_lean,
    verify_with_lean,
)
from mechanogenesis_bench.canonical import digest


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks/conformance/generated_metrology_fixture"


def certificate_mapping() -> dict[str, object]:
    world = load_world(TASK / "public/mechanism_world.json")
    goal = FixtureGoal.from_mapping(
        json.loads((TASK / "public/fixture_goal.json").read_text(encoding="utf-8"))
    )
    request = ResearchRequest(
        mission=(TASK / "guidance/G5.md").read_text(encoding="utf-8"),
        world=world,
        goal=goal,
        max_executions=32,
    )
    contract = json.loads(
        (TASK / "public/evaluator_contract.json").read_text(encoding="utf-8")
    )
    value = (
        GThetaRuntime(ReferenceResearchProposer())
        .run_fixture(request, evaluator_contract=contract)
        .mrs_objects["compiler_certificate"]
    )
    assert isinstance(value, dict)
    return value


def test_execution_emits_a_sovereign_lean_certificate(tmp_path: Path) -> None:
    raw = certificate_mapping()
    certificate = SovereignCertificate.from_mapping(raw)
    assert certificate.semantics_id == SOVEREIGN_SEMANTICS_ID
    assert {item.assumption_id for item in certificate.assumptions} >= (
        REQUIRED_ASSUMPTIONS
    )
    assert certificate.sequence_after == (
        certificate.sequence_before + len(certificate.receipts)
    )
    path = tmp_path / "certificate.json"
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    checker = find_sovereign_checker(ROOT)
    assert checker is not None
    verify_with_lean(path, checker)


def test_python_and_lean_reject_broken_material_closure(tmp_path: Path) -> None:
    raw = deepcopy(certificate_mapping())
    raw["receipts"][0]["balances"][0]["outputQ"] += 1
    with pytest.raises(IRValidationError, match="material closure"):
        SovereignCertificate.from_mapping(raw)
    path = tmp_path / "broken-certificate.json"
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    checker = find_sovereign_checker(ROOT)
    assert checker is not None
    with pytest.raises(ExecutionError, match="Lean sovereign checker rejected"):
        verify_with_lean(path, checker)


def test_certificate_cannot_hide_a_missing_model_assumption() -> None:
    raw = deepcopy(certificate_mapping())
    raw["assumptions"] = [
        item
        for item in raw["assumptions"]
        if item["assumptionId"] != "reference_model_fidelity"
    ]
    with pytest.raises(IRValidationError, match="omits a required"):
        SovereignCertificate.from_mapping(raw)


def test_certificate_cannot_claim_more_attempts_than_support() -> None:
    raw = deepcopy(certificate_mapping())
    raw["attemptedCandidates"] = raw["candidateSupportSize"] + 1
    with pytest.raises(IRValidationError, match="attempts exceed"):
        SovereignCertificate.from_mapping(raw)


def test_lean_accepts_a_world_bound_strict_promotion() -> None:
    certificate = SovereignCertificate.from_mapping(certificate_mapping())
    envelope = promotion_envelope(
        certificate,
        artifact_hash=digest({"artifact": "fixture"}),
        parent_error_upper=1000,
        child_error_upper=700,
        required_improvement=100,
        net_value=1,
        robustness_passed=True,
    )
    checker = find_promotion_checker(ROOT)
    assert checker is not None
    verify_promotion_with_lean(envelope, checker)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("childWorldHash", digest({"wrong": "world"})),
        ("childErrorUpper", 950),
        ("robustnessPassed", False),
    ],
)
def test_lean_rejects_unbound_or_unjustified_promotion(
    field: str, value: object
) -> None:
    certificate = SovereignCertificate.from_mapping(certificate_mapping())
    envelope = promotion_envelope(
        certificate,
        artifact_hash=digest({"artifact": "fixture"}),
        parent_error_upper=1000,
        child_error_upper=700,
        required_improvement=100,
        net_value=1,
        robustness_passed=True,
    )
    envelope["decision"][field] = value
    checker = find_promotion_checker(ROOT)
    assert checker is not None
    with pytest.raises(ExecutionError, match="promotion checker rejected"):
        verify_promotion_with_lean(envelope, checker)
