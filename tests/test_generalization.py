from __future__ import annotations

from itertools import product
import json
from pathlib import Path

from mechanogenesis_bench.generalization import (
    AcquisitionCandidate,
    CandidateTargetBelief,
    CalibratedCandidateTargetBelief,
    EngineeringEvidenceReceipt,
    FactorizedCase,
    GENERALIZATION_AXES,
    GeneralizationGate,
    TrainingObjectiveTerms,
    build_shortcut_destruction_curriculum,
    evaluate_generalization,
    grounded_separating_choices,
    lean_guided_training_objective,
    registered_shortcut_projections,
    residual_shortcuts,
    select_disagreement_experiment,
    select_certified_disagreement_experiment,
    select_grounded_separating_experiment,
)
from mechanogenesis_bench.cli import main
from mechanogenesis_bench.factor_world_model import (
    fit_factorized_target_world_model,
)


def _case(bits: tuple[int, ...], split: str) -> FactorizedCase:
    token = "".join(str(bit) for bit in bits)
    return FactorizedCase(
        case_id=f"case-{token}-{split}",
        split=split,
        factors={
            axis: f"v{bit}" for axis, bit in zip(GENERALIZATION_AXES, bits, strict=True)
        },
        target_signature=f"parity-{sum(bits) % 2}",
        execution_cost=1 + sum(bits),
    )


def _engineering(case_count: int, *, physical: bool = True) -> EngineeringEvidenceReceipt:
    return EngineeringEvidenceReceipt(
        evaluated_cases=case_count,
        canonical_parse_passes=case_count,
        lean_kernel_passes=case_count,
        reference_replay_passes=case_count,
        independent_backend_passes=case_count,
        physical_trial_passes=1 if physical else 0,
        independent_numeric_seeds=3,
    )


def test_marginal_axis_coverage_does_not_certify_generalization() -> None:
    train = (
        _case((0, 0, 0, 0, 0), "train"),
        _case((1, 1, 1, 1, 1), "train"),
    )
    sealed = (
        _case((0, 1, 0, 1, 0), "sealed"),
        _case((1, 0, 1, 0, 1), "sealed"),
    )
    predictions = {case.case_id: case.target_signature for case in sealed}
    report = evaluate_generalization(
        train,
        sealed,
        predictions,
        _engineering(len(sealed)),
        projections=registered_shortcut_projections(max_order=1),
    )
    assert report.marginal_value_overlap_complete
    assert report.unseen_pairwise_interaction_count > 0
    assert report.sealed_accuracy_ppm == 1_000_000
    assert report.residual_shortcuts
    assert "registered_shortcuts_survive_training" in report.violations
    assert not report.eligible


def test_counterexample_guided_curriculum_destroys_registered_shortcuts() -> None:
    all_cases = tuple(
        _case(bits, "acquisition") for bits in product((0, 1), repeat=5)
    )
    projections = registered_shortcut_projections(max_order=2)
    evidence, trace = build_shortcut_destruction_curriculum(
        all_cases[:1], all_cases[1:], projections=projections, max_rounds=20
    )
    assert trace
    assert all(choice.newly_destroyed for choice in trace)
    assert not residual_shortcuts(evidence, projections)
    assert len({case.case_id for case in evidence}) == len(evidence)


def test_compositional_sealed_split_can_pass_without_tuple_reuse() -> None:
    train: list[FactorizedCase] = []
    sealed: list[FactorizedCase] = []
    for bits in product((0, 1), repeat=5):
        destination = sealed if bits[0] == bits[1] == 1 else train
        destination.append(_case(bits, "sealed" if destination is sealed else "train"))
    predictions = {case.case_id: case.target_signature for case in sealed}
    report = evaluate_generalization(
        train,
        sealed,
        predictions,
        _engineering(len(sealed)),
        projections=registered_shortcut_projections(max_order=2),
    )
    assert report.eligible
    assert report.exact_factor_tuple_overlap_count == 0
    assert report.unseen_pairwise_interaction_count > 0
    assert report.destroyed_shortcut_count == report.registered_shortcut_count


def test_physical_evidence_is_explicitly_separate_from_simulation() -> None:
    train: list[FactorizedCase] = []
    sealed: list[FactorizedCase] = []
    for bits in product((0, 1), repeat=5):
        destination = sealed if bits[0] == bits[1] == 1 else train
        destination.append(_case(bits, "sealed" if destination is sealed else "train"))
    predictions = {case.case_id: case.target_signature for case in sealed}
    simulation_only = _engineering(len(sealed), physical=False)
    physical_report = evaluate_generalization(
        train, sealed, predictions, simulation_only
    )
    simulation_report = evaluate_generalization(
        train,
        sealed,
        predictions,
        simulation_only,
        gate=GeneralizationGate(require_physical=False),
    )
    assert not physical_report.eligible
    assert "physical_trial_missing" in physical_report.engineering_violations
    assert simulation_report.eligible


def test_description_length_pressure_waits_until_shortcuts_are_destroyed() -> None:
    unresolved = TrainingObjectiveTerms(
        task_nll=1.0,
        counterfactual_ranking_loss=0.0,
        intervention_prediction_loss=0.0,
        nuisance_consistency_loss=0.0,
        recursive_credit_loss=0.0,
        description_length_bits=1_000_000.0,
        residual_shortcut_fraction=1.0,
    )
    resolved = TrainingObjectiveTerms(
        task_nll=1.0,
        counterfactual_ranking_loss=0.0,
        intervention_prediction_loss=0.0,
        nuisance_consistency_loss=0.0,
        recursive_credit_loss=0.0,
        description_length_bits=1_000_000.0,
        residual_shortcut_fraction=0.0,
    )
    assert lean_guided_training_objective(unresolved) == 5.0
    assert lean_guided_training_objective(resolved) == 2.0


def test_generalization_cli_emits_a_machine_readable_report(
    tmp_path: Path, capsys
) -> None:
    train: list[FactorizedCase] = []
    sealed: list[FactorizedCase] = []
    for bits in product((0, 1), repeat=5):
        destination = sealed if bits[0] == bits[1] == 1 else train
        destination.append(_case(bits, "sealed" if destination is sealed else "train"))
    corpus_path = tmp_path / "corpus.json"
    predictions_path = tmp_path / "predictions.json"
    engineering_path = tmp_path / "engineering.json"
    corpus_path.write_text(
        json.dumps(
            {
                "train": [case.to_dict() for case in train],
                "sealed": [case.to_dict() for case in sealed],
            }
        ),
        encoding="utf-8",
    )
    predictions_path.write_text(
        json.dumps({case.case_id: case.target_signature for case in sealed}),
        encoding="utf-8",
    )
    engineering_path.write_text(
        json.dumps(_engineering(len(sealed)).__dict__), encoding="utf-8"
    )
    code = main(
        [
            "generalization",
            "audit",
            str(corpus_path),
            "--predictions",
            str(predictions_path),
            "--engineering-receipt",
            str(engineering_path),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["eligible"] is True
    assert payload["lean_checker_pass"] in {True, None}


def test_online_acquisition_uses_world_model_beliefs_not_hidden_targets() -> None:
    evidence = (_case((0, 0, 0, 0, 0), "evidence"),)
    hidden_left = _case((0, 0, 1, 1, 1), "pool")
    hidden_right = _case((0, 0, 1, 0, 0), "pool")
    model_hash = "sha256:" + "1" * 64
    beliefs = (
        CandidateTargetBelief(
            AcquisitionCandidate.from_hidden_case(hidden_left),
            {"parity-0": 100_000, "parity-1": 900_000},
            model_hash,
        ),
        CandidateTargetBelief(
            AcquisitionCandidate.from_hidden_case(hidden_right),
            {"parity-0": 900_000, "parity-1": 100_000},
            model_hash,
        ),
    )
    choice = select_disagreement_experiment(
        evidence,
        beliefs,
        projections=registered_shortcut_projections(max_order=1),
    )
    assert choice is not None
    assert choice.expected_destroyed_shortcuts_ppm > 0
    assert set(choice.case_ids) <= {hidden_left.case_id, hidden_right.case_id}
    # Planning is not evidence: the version space changes only after evaluator
    # outcomes are revealed and materialized as FactorizedCase records.
    assert residual_shortcuts(
        evidence, registered_shortcut_projections(max_order=1)
    )


def test_factor_world_model_binds_predictions_to_revealed_evidence() -> None:
    evidence = (
        _case((0, 0, 0, 0, 0), "evidence"),
        _case((1, 0, 1, 0, 1), "evidence"),
    )
    hidden = _case((0, 1, 1, 1, 0), "pool")
    candidate = AcquisitionCandidate.from_hidden_case(hidden)
    model = fit_factorized_target_world_model(evidence, [candidate])
    belief = model.predict(candidate)
    assert sum(belief.target_probability_ppm.values()) == 1_000_000
    assert belief.model_hash == model.model_hash
    assert "target_signature" not in candidate.__dict__


def test_certified_acquisition_abstains_when_forecast_error_erases_gain() -> None:
    evidence = (_case((0, 0, 0, 0, 0), "evidence"),)
    hidden = _case((0, 0, 1, 1, 1), "pool")
    belief = CandidateTargetBelief(
        AcquisitionCandidate.from_hidden_case(hidden),
        {"parity-0": 100_000, "parity-1": 900_000},
        "sha256:" + "2" * 64,
    )
    receipt = "sha256:" + "3" * 64
    high_error = CalibratedCandidateTargetBelief(belief, 1_000_000, receipt)
    low_error = CalibratedCandidateTargetBelief(belief, 10_000, receipt)
    projections = registered_shortcut_projections(max_order=1)
    assert (
        select_certified_disagreement_experiment(
            evidence, [high_error], projections=projections
        )
        is None
    )
    selected = select_certified_disagreement_experiment(
        evidence, [low_error], projections=projections
    )
    assert selected is not None
    assert selected.lower_destroyed_shortcuts_ppm > 0


def test_grounded_separating_selector_is_target_hidden_and_structural() -> None:
    evidence = (_case((0, 0, 0, 0, 0), "evidence"),)
    hidden = (
        _case((0, 1, 1, 1, 1), "pool-a"),
        _case((0, 1, 0, 1, 0), "pool-b"),
        _case((1, 1, 1, 1, 1), "pool-c"),
    )
    candidates = tuple(AcquisitionCandidate.from_hidden_case(case) for case in hidden)
    projections = registered_shortcut_projections(max_order=1)
    before = residual_shortcuts(evidence, projections)
    choice = select_grounded_separating_experiment(
        evidence,
        candidates,
        projections=projections,
        maximum_batch_size=2,
        minimum_complement_distance=2,
    )
    assert choice is not None
    assert 1 <= len(choice.case_ids) <= 2
    assert choice.structurally_tested_shortcuts
    assert choice.complement_distance_sum >= 2
    assert all("target_signature" not in candidate.__dict__ for candidate in candidates)
    # A structural opportunity is not evidence and cannot shrink the version
    # space before the evaluator reveals the selected targets.
    assert residual_shortcuts(evidence, projections) == before


def test_grounded_separating_selector_abstains_without_projection_overlap() -> None:
    evidence = (_case((0, 0, 0, 0, 0), "evidence"),)
    hidden = _case((1, 1, 1, 1, 1), "pool")
    choice = select_grounded_separating_experiment(
        evidence,
        [AcquisitionCandidate.from_hidden_case(hidden)],
        projections=(("world",),),
    )
    assert choice is None


def test_grounded_separating_choice_enumeration_is_ranked_and_target_hidden() -> None:
    evidence = (_case((0, 0, 0, 0, 0), "evidence"),)
    hidden = tuple(
        _case(bits, f"pool-{index}")
        for index, bits in enumerate(
            ((0, 1, 1, 1, 1), (0, 1, 0, 1, 0), (1, 1, 1, 1, 1))
        )
    )
    candidates = tuple(AcquisitionCandidate.from_hidden_case(case) for case in hidden)
    choices = grounded_separating_choices(
        evidence,
        candidates,
        projections=registered_shortcut_projections(max_order=1),
        maximum_batch_size=2,
    )
    assert choices
    assert choices[0] == select_grounded_separating_experiment(
        evidence,
        candidates,
        projections=registered_shortcut_projections(max_order=1),
        maximum_batch_size=2,
    )
    assert all("target_signature" not in candidate.__dict__ for candidate in candidates)
