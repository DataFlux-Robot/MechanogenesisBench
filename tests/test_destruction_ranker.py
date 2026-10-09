from __future__ import annotations

from mechanogenesis_bench.destruction_ranker import (
    DestructionTrainingExample,
    StateMaximumCalibrationReceipt,
    calibrate_state_maximum_error,
    destruction_features,
    fit_ridge_destruction_ranker,
    select_calibrated_destruction_choice,
)
from mechanogenesis_bench.generalization import (
    AcquisitionCandidate,
    FactorizedCase,
    GENERALIZATION_AXES,
    grounded_separating_choices,
    registered_shortcut_projections,
)


def _case(bits: tuple[int, ...], split: str, target: str) -> FactorizedCase:
    token = "".join(str(bit) for bit in bits)
    return FactorizedCase(
        case_id=f"rank-{token}-{split}",
        split=split,
        factors={
            axis: f"v{bit}" for axis, bit in zip(GENERALIZATION_AXES, bits, strict=True)
        },
        target_signature=target,
        execution_cost=1 + sum(bits),
    )


def _examples() -> tuple[DestructionTrainingExample, ...]:
    values = []
    for state in range(8):
        for action in range(3):
            tested = float(action + 1)
            values.append(
                DestructionTrainingExample(
                    state_id=f"state-{state}",
                    action_id=f"action-{action}",
                    features={
                        "state.residual_count": 5.0,
                        "action.structural_count": tested,
                        "action.execution_cost_billions": float(action + 1),
                    },
                    destroyed_shortcut_count=action + 1,
                )
            )
    return tuple(values)


def test_state_maximum_calibration_binds_model_and_all_actions() -> None:
    examples = _examples()
    model = fit_ridge_destruction_ranker(examples[:12], ridge_penalty=0.1)
    calibration = calibrate_state_maximum_error(
        model,
        examples[12:],
        alpha_ppm=200_000,
        fit_split_hash=model.fit_example_hash,
    )
    assert calibration.model_hash == model.model_hash
    assert calibration.calibration_state_count == 4
    assert calibration.empirical_state_coverage_ppm == 1_000_000
    assert calibration.receipt_hash.startswith("sha256:")


def test_calibrated_ranker_abstains_when_state_max_error_erases_value() -> None:
    evidence = (_case((0, 0, 0, 0, 0), "evidence", "left"),)
    hidden = (
        _case((0, 1, 1, 1, 1), "pool-a", "right"),
        _case((0, 1, 0, 1, 0), "pool-b", "left"),
    )
    candidates = tuple(AcquisitionCandidate.from_hidden_case(case) for case in hidden)
    projections = registered_shortcut_projections(max_order=1)
    choices = grounded_separating_choices(
        evidence, candidates, projections=projections, maximum_batch_size=2
    )
    assert choices
    features = destruction_features(
        evidence, candidates, choices[0], projections=projections
    )
    examples = (
        DestructionTrainingExample("fit-0", "a", features, 1),
        DestructionTrainingExample("fit-1", "b", features, 1),
    )
    model = fit_ridge_destruction_ranker(examples, ridge_penalty=1.0)
    calibration = StateMaximumCalibrationReceipt(
        model_hash=model.model_hash,
        fit_split_hash=model.fit_example_hash,
        calibration_split_hash="sha256:" + "4" * 64,
        calibration_state_count=10,
        alpha_ppm=100_000,
        quantile_rank=10,
        simultaneous_error_micros=2_000_000,
        empirical_state_coverage_ppm=1_000_000,
    )
    assert (
        select_calibrated_destruction_choice(
            model,
            calibration,
            evidence,
            candidates,
            choices,
            projections=projections,
        )
        is None
    )
