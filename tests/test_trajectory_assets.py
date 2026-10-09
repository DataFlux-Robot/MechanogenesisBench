from __future__ import annotations

import json

import pytest

from mechanogenesis_bench.canonical import digest
from mechanogenesis_bench.destruction_ranker import (
    destruction_examples_from_compiled_assets,
)
from mechanogenesis_bench.trajectory_assets import (
    TraceEvent,
    TraceHeader,
    TraceRecorder,
    compile_recorded_trace,
    compile_trajectory_assets,
    load_trace,
    validate_trace,
    write_compiled_trajectory_assets,
)


HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
HASH_C = "sha256:" + "c" * 64


def _header() -> TraceHeader:
    return TraceHeader(
        trace_id="trace-001",
        task_id="destroy-shortcuts",
        split_id="train-seed-17",
        source_kind="canonical_counterfactual",
        generator_hash=HASH_A,
        evaluator_hash=HASH_B,
        canonical_world_hash=HASH_C,
        created_at="2026-08-23T20:00:00+08:00",
    )


def _record_valid_trace(directory):
    recorder = TraceRecorder(directory, _header())
    timestamp = "2026-08-23T20:00:00+08:00"
    recorder.append("episode.opened", {"protocol": "forked-actions-v1"}, timestamp=timestamp)
    public_state = {"residual_count": 3, "evidence_count": 5}
    recorder.append(
        "state.snapshot",
        {
            "state_id": "state-0",
            "state_hash": digest(public_state),
            "public_state": public_state,
        },
        timestamp=timestamp,
    )
    actions = [
        {
            "action_id": "action-a",
            "public_features": {"structural_count": 2},
            "execution_cost_micros": 3,
        },
        {
            "action_id": "action-b",
            "public_features": {"structural_count": 1},
            "execution_cost_micros": 2,
        },
        {
            "action_id": "action-c",
            "public_features": {"structural_count": 1},
            "execution_cost_micros": 2,
        },
    ]
    candidate_set_hash = digest(actions)
    recorder.append(
        "candidate_set.frozen",
        {
            "state_id": "state-0",
            "candidate_set_hash": candidate_set_hash,
            "actions": actions,
        },
        timestamp=timestamp,
    )
    for action_id, prediction in (
        ("action-a", 2_000_000),
        ("action-b", 1_000_000),
        ("action-c", 1_000_000),
    ):
        recorder.append(
            "policy.forecast",
            {
                "state_id": "state-0",
                "candidate_set_hash": candidate_set_hash,
                "action_id": action_id,
                "predicted_destruction_micros": prediction,
                "model_hash": HASH_A,
                "calibration_receipt_hash": HASH_B,
            },
            timestamp=timestamp,
        )

    outcomes = (
        ("action-a", "accepted", 2, 10, 3),
        ("action-b", "accepted", 1, 6, 2),
        ("action-c", "rejected", 0, 0, 2),
    )
    for action_id, status, destroyed, gross, cost in outcomes:
        selection = recorder.append(
            "action.selected",
            {
                "state_id": "state-0",
                "candidate_set_hash": candidate_set_hash,
                "action_id": action_id,
            },
            timestamp=timestamp,
        )
        started = recorder.append(
            "experiment.started",
            {
                "selection_event_hash": selection.event_hash,
                "action_id": action_id,
            },
            timestamp=timestamp,
        )
        observed = recorder.append(
            "experiment.observed",
            {
                "started_event_hash": started.event_hash,
                "action_id": action_id,
                "status": status,
                "destroyed_shortcut_count": destroyed,
                "gross_value_micros": gross,
                "full_cost_penalty_micros": cost,
                "net_value_micros": gross - cost,
                "evidence_tier": "canonical_counterfactual",
                "evaluator_hash": HASH_B,
                "canonical_world_hash": HASH_C,
                "evaluator_receipt_hash": digest(
                    {"action_id": action_id, "status": status}
                ),
            },
            timestamp=timestamp,
        )
        if status == "accepted":
            recorder.append(
                "version_space.updated",
                {
                    "observed_event_hash": observed.event_hash,
                    "residual_before": 3,
                    "residual_after": 3 - destroyed,
                    "destroyed_shortcut_count": destroyed,
                },
                timestamp=timestamp,
            )
    recorder.append("episode.closed", {"status": "complete"}, timestamp=timestamp)
    return recorder


def test_valid_trace_compiles_all_training_views_and_writes_bundle(tmp_path) -> None:
    trace_directory = tmp_path / "trace"
    _record_valid_trace(trace_directory)
    header, events = load_trace(trace_directory)
    report = validate_trace(header, events)
    assert report.valid
    assert report.target_hiding_verified

    assets = compile_trajectory_assets(header, events)
    assert len(assets.sft) == 2
    assert len(assets.preference) == 1
    assert len(assets.rl) == 3
    assert len(assets.world_model) == 2
    assert len(assets.calibration) == 1
    assert len(assets.rejected_or_failed) == 1
    assert assets.preference[0]["winner_action_id"] == "action-a"
    assert assets.preference[0]["loser_action_id"] == "action-b"
    assert all(
        action["forecast_event_hash"].startswith("sha256:")
        for action in assets.calibration[0]["actions"]
    )
    ranker_examples = destruction_examples_from_compiled_assets(assets)
    assert len(ranker_examples) == 3
    assert {item.destroyed_shortcut_count for item in ranker_examples} == {0, 1, 2}

    manifest_path = write_compiled_trajectory_assets(tmp_path / "compiled", assets)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["counts"]["rl"] == 3
    assert manifest["bundle_hash"].startswith("sha256:")
    automatic_manifest = compile_recorded_trace(
        trace_directory, tmp_path / "compiled-automatic"
    )
    assert automatic_manifest.exists()


def test_predecision_target_leak_is_rejected_at_record_time(tmp_path) -> None:
    recorder = TraceRecorder(tmp_path / "trace", _header())
    with pytest.raises(ValueError, match="evaluator-owned fields"):
        recorder.append(
            "state.snapshot",
            {
                "state_id": "state-0",
                "state_hash": HASH_A,
                "public_state": {"target_signature": "secret"},
            },
            timestamp="2026-08-23T20:00:00+08:00",
        )


def test_broken_event_chain_is_not_compilable() -> None:
    opened = TraceEvent.create(
        sequence=0,
        timestamp="2026-08-23T20:00:00+08:00",
        kind="episode.opened",
        data={},
        previous_event_hash=None,
    )
    closed = TraceEvent.create(
        sequence=1,
        timestamp="2026-08-23T20:00:01+08:00",
        kind="episode.closed",
        data={},
        previous_event_hash=None,
    )
    report = validate_trace(_header(), (opened, closed))
    assert not report.valid
    assert "event_hash_chain_broken" in report.violations
    with pytest.raises(ValueError, match="not compilable"):
        compile_trajectory_assets(_header(), (opened, closed))


def test_tampered_serialized_event_is_rejected_when_loaded(tmp_path) -> None:
    trace_directory = tmp_path / "trace"
    _record_valid_trace(trace_directory)
    events_path = trace_directory / "events.jsonl"
    rows = events_path.read_text(encoding="utf-8").splitlines()
    row = json.loads(rows[1])
    row["data"]["public_state"]["residual_count"] = 999
    rows[1] = json.dumps(row, sort_keys=True)
    events_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="content hash mismatch"):
        load_trace(trace_directory)


def test_observation_value_accounting_is_fail_closed(tmp_path) -> None:
    trace_directory = tmp_path / "trace"
    _record_valid_trace(trace_directory)
    header, events = load_trace(trace_directory)
    rewritten = []
    for event in events:
        data = dict(event.data)
        if event.kind == "experiment.observed" and data["action_id"] == "action-c":
            data["net_value_micros"] = 17
        rewritten.append(
            TraceEvent.create(
                sequence=event.sequence,
                timestamp=event.timestamp,
                kind=event.kind,
                data=data,
                previous_event_hash=(rewritten[-1].event_hash if rewritten else None),
            )
        )
    report = validate_trace(header, tuple(rewritten))
    assert not report.valid
    assert "observation_value_accounting_invalid" in report.violations
