from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .canonical import digest


TRACE_SCHEMA_VERSION = "MechanogenesisTrace/0.1"
TRACE_COMPILER_VERSION = "MechanogenesisTraceCompiler/0.1"

EVENT_KINDS = (
    "episode.opened",
    "state.snapshot",
    "candidate_set.frozen",
    "policy.forecast",
    "action.selected",
    "experiment.started",
    "experiment.observed",
    "version_space.updated",
    "episode.closed",
)

PREDECISION_EVENT_KINDS = {
    "state.snapshot",
    "candidate_set.frozen",
    "policy.forecast",
    "action.selected",
}

_FORBIDDEN_PREDECISION_FIELDS = {
    "target",
    "target_signature",
    "true_target",
    "hidden_target",
    "observed_target",
    "realized_destroyed_shortcuts",
    "destroyed_shortcut_count",
    "net_value_micros",
}


def _require_hash(value: str, field: str) -> None:
    if not _is_hash(value):
        raise ValueError(f"{field} must be a sha256 digest")


def _is_hash(value: object) -> bool:
    return isinstance(value, str) and value.startswith("sha256:") and len(value) == 71


def _field_names(value: object) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _field_names(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _field_names(item)


def _assert_predecision_target_hidden(kind: str, data: Mapping[str, object]) -> None:
    if kind not in PREDECISION_EVENT_KINDS:
        return
    leaked = sorted(set(_field_names(data)) & _FORBIDDEN_PREDECISION_FIELDS)
    if leaked:
        raise ValueError(
            "predecision event contains evaluator-owned fields: " + ", ".join(leaked)
        )


@dataclass(frozen=True)
class TraceHeader:
    trace_id: str
    task_id: str
    split_id: str
    source_kind: str
    generator_hash: str
    evaluator_hash: str
    canonical_world_hash: str
    created_at: str
    parent_trace_hash: str | None = None

    def __post_init__(self) -> None:
        if not all((self.trace_id, self.task_id, self.split_id, self.source_kind)):
            raise ValueError("trace header identifiers must be non-empty")
        for field, value in (
            ("generator_hash", self.generator_hash),
            ("evaluator_hash", self.evaluator_hash),
            ("canonical_world_hash", self.canonical_world_hash),
        ):
            _require_hash(value, field)
        if self.parent_trace_hash is not None:
            _require_hash(self.parent_trace_hash, "parent_trace_hash")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "trace_id": self.trace_id,
            "task_id": self.task_id,
            "split_id": self.split_id,
            "source_kind": self.source_kind,
            "generator_hash": self.generator_hash,
            "evaluator_hash": self.evaluator_hash,
            "canonical_world_hash": self.canonical_world_hash,
            "created_at": self.created_at,
            "parent_trace_hash": self.parent_trace_hash,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "TraceHeader":
        if raw.get("schema_version") != TRACE_SCHEMA_VERSION:
            raise ValueError("unsupported trace header schema")
        return cls(
            trace_id=str(raw["trace_id"]),
            task_id=str(raw["task_id"]),
            split_id=str(raw["split_id"]),
            source_kind=str(raw["source_kind"]),
            generator_hash=str(raw["generator_hash"]),
            evaluator_hash=str(raw["evaluator_hash"]),
            canonical_world_hash=str(raw["canonical_world_hash"]),
            created_at=str(raw["created_at"]),
            parent_trace_hash=(
                str(raw["parent_trace_hash"])
                if raw.get("parent_trace_hash") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class TraceEvent:
    sequence: int
    timestamp: str
    kind: str
    data: Mapping[str, object]
    previous_event_hash: str | None
    event_hash: str

    def __post_init__(self) -> None:
        if self.sequence < 0 or self.kind not in EVENT_KINDS or not self.timestamp:
            raise ValueError("trace event envelope is invalid")
        if self.previous_event_hash is not None:
            _require_hash(self.previous_event_hash, "previous_event_hash")
        _require_hash(self.event_hash, "event_hash")
        _assert_predecision_target_hidden(self.kind, self.data)
        if self.event_hash != digest(self.unsigned_dict()):
            raise ValueError("trace event content hash mismatch")

    def unsigned_dict(self) -> dict[str, object]:
        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "kind": self.kind,
            "data": dict(self.data),
            "previous_event_hash": self.previous_event_hash,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self.unsigned_dict(), "event_hash": self.event_hash}

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        timestamp: str,
        kind: str,
        data: Mapping[str, object],
        previous_event_hash: str | None,
    ) -> "TraceEvent":
        unsigned = {
            "schema_version": TRACE_SCHEMA_VERSION,
            "sequence": sequence,
            "timestamp": timestamp,
            "kind": kind,
            "data": dict(data),
            "previous_event_hash": previous_event_hash,
        }
        return cls(
            sequence=sequence,
            timestamp=timestamp,
            kind=kind,
            data=dict(data),
            previous_event_hash=previous_event_hash,
            event_hash=digest(unsigned),
        )

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "TraceEvent":
        if raw.get("schema_version") != TRACE_SCHEMA_VERSION:
            raise ValueError("unsupported trace event schema")
        data = raw.get("data")
        if not isinstance(data, Mapping):
            raise ValueError("trace event data must be an object")
        return cls(
            sequence=int(raw["sequence"]),
            timestamp=str(raw["timestamp"]),
            kind=str(raw["kind"]),
            data=dict(data),
            previous_event_hash=(
                str(raw["previous_event_hash"])
                if raw.get("previous_event_hash") is not None
                else None
            ),
            event_hash=str(raw["event_hash"]),
        )


class TraceRecorder:
    """Append-only local-first recorder with an event hash chain."""

    def __init__(self, directory: Path, header: TraceHeader) -> None:
        self.directory = directory
        self.header = header
        self.events_path = directory / "events.jsonl"
        directory.mkdir(parents=True, exist_ok=False)
        (directory / "trajectory.json").write_text(
            json.dumps(header.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.events_path.write_text("", encoding="utf-8")
        self._events: list[TraceEvent] = []

    @property
    def events(self) -> tuple[TraceEvent, ...]:
        return tuple(self._events)

    def append(
        self, kind: str, data: Mapping[str, object], *, timestamp: str
    ) -> TraceEvent:
        event = TraceEvent.create(
            sequence=len(self._events),
            timestamp=timestamp,
            kind=kind,
            data=data,
            previous_event_hash=(self._events[-1].event_hash if self._events else None),
        )
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")
            handle.flush()
        self._events.append(event)
        return event


@dataclass(frozen=True)
class TraceValidationReport:
    valid: bool
    violations: tuple[str, ...]
    event_count: int
    state_count: int
    frozen_candidate_set_count: int
    selected_action_count: int
    observed_action_count: int
    version_update_count: int
    target_hiding_verified: bool
    trace_hash: str


def load_trace(directory: Path) -> tuple[TraceHeader, tuple[TraceEvent, ...]]:
    header_raw = json.loads((directory / "trajectory.json").read_text(encoding="utf-8"))
    header = TraceHeader.from_mapping(header_raw)
    events = tuple(
        TraceEvent.from_mapping(json.loads(line))
        for line in (directory / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    return header, events


def validate_trace(
    header: TraceHeader, events: Sequence[TraceEvent]
) -> TraceValidationReport:
    violations: list[str] = []
    if not events or events[0].kind != "episode.opened":
        violations.append("episode_missing_open")
    if not events or events[-1].kind != "episode.closed":
        violations.append("episode_missing_close")
    if sum(event.kind == "episode.opened" for event in events) != 1:
        violations.append("episode_open_count_invalid")
    if sum(event.kind == "episode.closed" for event in events) != 1:
        violations.append("episode_close_count_invalid")
    previous: str | None = None
    for index, event in enumerate(events):
        if event.sequence != index:
            violations.append("event_sequence_gap")
        if event.previous_event_hash != previous:
            violations.append("event_hash_chain_broken")
        previous = event.event_hash

    states: dict[str, Mapping[str, object]] = {}
    candidate_sets: dict[tuple[str, str], dict[str, Mapping[str, object]]] = {}
    forecast_keys: set[tuple[str, str, str]] = set()
    selection_events: dict[str, TraceEvent] = {}
    started_events: dict[str, TraceEvent] = {}
    observed_events: dict[str, TraceEvent] = {}
    started_selection_hashes: set[str] = set()
    observed_start_hashes: set[str] = set()
    updated_observations: set[str] = set()
    update_count = 0
    target_hiding = True

    for event in events:
        data = event.data
        if event.kind in PREDECISION_EVENT_KINDS:
            if set(_field_names(data)) & _FORBIDDEN_PREDECISION_FIELDS:
                target_hiding = False
                violations.append("predecision_target_leak")

        if event.kind == "state.snapshot":
            state_id = str(data.get("state_id") or "")
            state_hash = str(data.get("state_hash") or "")
            public_state = data.get("public_state")
            if (
                not state_id
                or not _is_hash(state_hash)
                or not isinstance(public_state, Mapping)
            ):
                violations.append("state_snapshot_invalid")
            elif state_hash != digest(public_state):
                violations.append("state_snapshot_hash_mismatch")
            elif state_id in states:
                violations.append("state_snapshot_duplicate")
            else:
                states[state_id] = data

        elif event.kind == "candidate_set.frozen":
            state_id = str(data.get("state_id") or "")
            candidate_set_hash = str(data.get("candidate_set_hash") or "")
            actions = data.get("actions")
            if state_id not in states:
                violations.append("candidate_set_without_state")
                continue
            if not _is_hash(candidate_set_hash) or not isinstance(actions, list):
                violations.append("candidate_set_invalid")
                continue
            action_map: dict[str, Mapping[str, object]] = {}
            for action in actions:
                if not isinstance(action, Mapping):
                    violations.append("candidate_action_invalid")
                    continue
                action_id = str(action.get("action_id") or "")
                public_features = action.get("public_features")
                execution_cost = action.get("execution_cost_micros")
                if (
                    not action_id
                    or action_id in action_map
                    or not isinstance(public_features, Mapping)
                    or not isinstance(execution_cost, int)
                    or execution_cost < 0
                ):
                    violations.append("candidate_action_invalid")
                else:
                    action_map[action_id] = action
            if digest(actions) != candidate_set_hash:
                violations.append("candidate_set_hash_mismatch")
            candidate_sets[(state_id, candidate_set_hash)] = action_map

        elif event.kind == "policy.forecast":
            state_id = str(data.get("state_id") or "")
            set_hash = str(data.get("candidate_set_hash") or "")
            action_id = str(data.get("action_id") or "")
            actions = candidate_sets.get((state_id, set_hash))
            if actions is None or action_id not in actions:
                violations.append("forecast_action_not_in_frozen_set")
            forecast_key = (state_id, set_hash, action_id)
            if forecast_key in forecast_keys:
                violations.append("forecast_duplicate")
            forecast_keys.add(forecast_key)
            prediction = data.get("predicted_destruction_micros")
            if not isinstance(prediction, int) or prediction < 0:
                violations.append("forecast_value_invalid")
            for field in ("model_hash", "calibration_receipt_hash"):
                if not _is_hash(data.get(field)):
                    violations.append(f"forecast_{field}_invalid")

        elif event.kind == "action.selected":
            state_id = str(data.get("state_id") or "")
            set_hash = str(data.get("candidate_set_hash") or "")
            action_id = str(data.get("action_id") or "")
            actions = candidate_sets.get((state_id, set_hash))
            if actions is None or action_id not in actions:
                violations.append("selected_action_not_in_frozen_set")
            selection_events[event.event_hash] = event

        elif event.kind == "experiment.started":
            selection_hash = str(data.get("selection_event_hash") or "")
            selection = selection_events.get(selection_hash)
            if selection is None:
                violations.append("experiment_without_selection")
            elif data.get("action_id") != selection.data.get("action_id"):
                violations.append("experiment_action_mismatch")
            if selection_hash in started_selection_hashes:
                violations.append("selection_started_twice")
            started_selection_hashes.add(selection_hash)
            started_events[event.event_hash] = event

        elif event.kind == "experiment.observed":
            started_hash = str(data.get("started_event_hash") or "")
            started = started_events.get(started_hash)
            if started is None:
                violations.append("observation_without_start")
            elif data.get("action_id") != started.data.get("action_id"):
                violations.append("observation_action_mismatch")
            if started_hash in observed_start_hashes:
                violations.append("experiment_observed_twice")
            observed_start_hashes.add(started_hash)
            if not _is_hash(data.get("evaluator_receipt_hash")):
                violations.append("observation_without_evaluator_receipt")
            if data.get("status") not in {"accepted", "rejected", "failed"}:
                violations.append("observation_status_invalid")
            if str(data.get("evaluator_hash") or "") != header.evaluator_hash:
                violations.append("observation_evaluator_mismatch")
            if str(data.get("canonical_world_hash") or "") != header.canonical_world_hash:
                violations.append("observation_world_mismatch")
            destroyed = data.get("destroyed_shortcut_count")
            gross = data.get("gross_value_micros")
            cost = data.get("full_cost_penalty_micros")
            net = data.get("net_value_micros")
            if not isinstance(destroyed, int) or destroyed < 0:
                violations.append("observation_destruction_invalid")
            if not all(isinstance(value, int) for value in (gross, cost, net)):
                violations.append("observation_value_accounting_missing")
            elif cost < 0 or gross - cost != net:
                violations.append("observation_value_accounting_invalid")
            observed_events[event.event_hash] = event

        elif event.kind == "version_space.updated":
            update_count += 1
            observed_hash = str(data.get("observed_event_hash") or "")
            observed = observed_events.get(observed_hash)
            if observed is None:
                violations.append("version_update_without_observation")
                continue
            if observed_hash in updated_observations:
                violations.append("version_update_duplicate")
            updated_observations.add(observed_hash)
            if observed.data.get("status") != "accepted":
                violations.append("version_update_for_unaccepted_observation")
            before = int(data.get("residual_before", -1))
            after = int(data.get("residual_after", -1))
            destroyed = int(data.get("destroyed_shortcut_count", -1))
            if before < 0 or after < 0 or after > before or before - after != destroyed:
                violations.append("version_update_accounting_invalid")
            if observed.data.get("destroyed_shortcut_count") != destroyed:
                violations.append("version_update_outcome_mismatch")

    for event_hash, observed in observed_events.items():
        if observed.data.get("status") == "accepted" and event_hash not in updated_observations:
            violations.append("accepted_observation_without_version_update")
    if len(selection_events) != len(started_events):
        violations.append("selection_start_count_mismatch")
    if len(started_events) != len(observed_events):
        violations.append("start_observation_count_mismatch")
    if not observed_events:
        violations.append("episode_without_observation")

    trace_hash = digest(
        {
            "header": header.to_dict(),
            "event_hashes": [event.event_hash for event in events],
        }
    )
    return TraceValidationReport(
        valid=not violations,
        violations=tuple(violations),
        event_count=len(events),
        state_count=len(states),
        frozen_candidate_set_count=len(candidate_sets),
        selected_action_count=len(selection_events),
        observed_action_count=len(observed_events),
        version_update_count=update_count,
        target_hiding_verified=target_hiding,
        trace_hash=trace_hash,
    )


@dataclass(frozen=True)
class CompiledTrajectoryAssets:
    source_trace_hash: str
    sft: tuple[Mapping[str, object], ...]
    preference: tuple[Mapping[str, object], ...]
    rl: tuple[Mapping[str, object], ...]
    world_model: tuple[Mapping[str, object], ...]
    calibration: tuple[Mapping[str, object], ...]
    rejected_or_failed: tuple[Mapping[str, object], ...]
    manifest: Mapping[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": TRACE_COMPILER_VERSION,
            "source_trace_hash": self.source_trace_hash,
            "sft": list(self.sft),
            "preference": list(self.preference),
            "rl": list(self.rl),
            "world_model": list(self.world_model),
            "calibration": list(self.calibration),
            "rejected_or_failed": list(self.rejected_or_failed),
            "manifest": dict(self.manifest),
        }


def compile_trajectory_assets(
    header: TraceHeader, events: Sequence[TraceEvent]
) -> CompiledTrajectoryAssets:
    report = validate_trace(header, events)
    if not report.valid:
        raise ValueError("trace is not compilable: " + ", ".join(report.violations))

    states: dict[str, Mapping[str, object]] = {}
    action_sets: dict[tuple[str, str], dict[str, Mapping[str, object]]] = {}
    selections: dict[str, TraceEvent] = {}
    starts: dict[str, TraceEvent] = {}
    forecasts: dict[tuple[str, str, str], TraceEvent] = {}
    observations_by_parent: dict[
        tuple[str, str], list[tuple[Mapping[str, object], TraceEvent]]
    ] = {}
    updates_by_observation: dict[str, TraceEvent] = {}
    for event in events:
        data = event.data
        if event.kind == "state.snapshot":
            states[str(data["state_id"])] = data
        elif event.kind == "candidate_set.frozen":
            action_sets[(str(data["state_id"]), str(data["candidate_set_hash"]))] = {
                str(action["action_id"]): action
                for action in data["actions"]  # type: ignore[index]
            }
        elif event.kind == "policy.forecast":
            forecasts[
                (
                    str(data["state_id"]),
                    str(data["candidate_set_hash"]),
                    str(data["action_id"]),
                )
            ] = event
        elif event.kind == "action.selected":
            selections[event.event_hash] = event
        elif event.kind == "experiment.started":
            starts[event.event_hash] = event
        elif event.kind == "experiment.observed":
            started = starts[str(data["started_event_hash"])]
            selection = selections[str(started.data["selection_event_hash"])]
            state_id = str(selection.data["state_id"])
            set_hash = str(selection.data["candidate_set_hash"])
            action = action_sets[(state_id, set_hash)][str(data["action_id"])]
            observations_by_parent.setdefault((state_id, set_hash), []).append(
                (action, event)
            )
        elif event.kind == "version_space.updated":
            updates_by_observation[str(data["observed_event_hash"])] = event

    sft: list[Mapping[str, object]] = []
    rl: list[Mapping[str, object]] = []
    world_model: list[Mapping[str, object]] = []
    calibration: list[Mapping[str, object]] = []
    rejected: list[Mapping[str, object]] = []
    preference: list[Mapping[str, object]] = []
    for (state_id, candidate_set_hash), observed in sorted(
        observations_by_parent.items()
    ):
        ranked: list[tuple[int, str, Mapping[str, object], TraceEvent]] = []
        calibration_actions: list[Mapping[str, object]] = []
        for action, observation in observed:
            outcome = observation.data
            action_id = str(outcome["action_id"])
            status = str(outcome["status"])
            net_value = int(outcome.get("net_value_micros", 0))
            update = updates_by_observation.get(observation.event_hash)
            sample = {
                "state_id": state_id,
                "state": dict(states[state_id]),
                "action_id": action_id,
                "action": dict(action),
                "status": status,
                "destroyed_shortcut_count": int(
                    outcome.get("destroyed_shortcut_count", 0)
                ),
                "gross_value_micros": int(outcome.get("gross_value_micros", 0)),
                "full_cost_penalty_micros": int(
                    outcome.get("full_cost_penalty_micros", 0)
                ),
                "net_value_micros": net_value,
                "evidence_tier": str(outcome.get("evidence_tier", "unknown")),
                "evaluator_receipt_hash": str(outcome["evaluator_receipt_hash"]),
                "observed_event_hash": observation.event_hash,
            }
            rl.append(sample)
            if status == "accepted":
                world_model.append(
                    {
                        **sample,
                        "residual_after": (
                            int(update.data["residual_after"]) if update is not None else None
                        ),
                    }
                )
                if int(outcome.get("destroyed_shortcut_count", 0)) > 0 and net_value > 0:
                    sft.append(sample)
                ranked.append((net_value, action_id, action, observation))
            else:
                rejected.append(sample)
            forecast = forecasts.get((state_id, candidate_set_hash, action_id))
            if forecast is not None:
                calibration_actions.append(
                    {
                        "action_id": action_id,
                        "public_features": dict(action["public_features"]),
                        "predicted_destruction_micros": int(
                            forecast.data["predicted_destruction_micros"]
                        ),
                        "realized_destruction_micros": int(
                            outcome.get("destroyed_shortcut_count", 0)
                        )
                        * 1_000_000,
                        "forecast_event_hash": forecast.event_hash,
                        "observed_event_hash": observation.event_hash,
                    }
                )
        if calibration_actions:
            calibration.append(
                {
                    "state_id": state_id,
                    "candidate_set_hash": candidate_set_hash,
                    "actions": calibration_actions,
                }
            )
        if len(ranked) >= 2:
            ranked.sort(key=lambda item: (item[0], item[1]))
            loser = ranked[0]
            winner = ranked[-1]
            if winner[0] > loser[0]:
                preference.append(
                    {
                        "state_id": state_id,
                        "candidate_set_hash": candidate_set_hash,
                        "winner_action_id": winner[1],
                        "loser_action_id": loser[1],
                        "winner_net_value_micros": winner[0],
                        "loser_net_value_micros": loser[0],
                        "winner_observed_event_hash": winner[3].event_hash,
                        "loser_observed_event_hash": loser[3].event_hash,
                    }
                )

    manifest = {
        "compiler_version": TRACE_COMPILER_VERSION,
        "source_trace_hash": report.trace_hash,
        "source_event_count": report.event_count,
        "target_hiding_verified": report.target_hiding_verified,
        "counts": {
            "sft": len(sft),
            "preference": len(preference),
            "rl": len(rl),
            "world_model": len(world_model),
            "calibration_states": len(calibration),
            "rejected_or_failed": len(rejected),
        },
        "asset_hashes": {
            "sft": digest(sft),
            "preference": digest(preference),
            "rl": digest(rl),
            "world_model": digest(world_model),
            "calibration": digest(calibration),
            "rejected_or_failed": digest(rejected),
        },
        "claim_ceiling": (
            "Compiled supervision is valid only at the recorded evidence tier. "
            "Canonical counterfactual execution is not physical evidence."
        ),
    }
    return CompiledTrajectoryAssets(
        source_trace_hash=report.trace_hash,
        sft=tuple(sft),
        preference=tuple(preference),
        rl=tuple(rl),
        world_model=tuple(world_model),
        calibration=tuple(calibration),
        rejected_or_failed=tuple(rejected),
        manifest=manifest,
    )


def write_compiled_trajectory_assets(
    directory: Path, assets: CompiledTrajectoryAssets
) -> Path:
    """Write deterministic dataset views and a manifest into a new directory."""

    directory.mkdir(parents=True, exist_ok=False)
    named_views = {
        "sft": assets.sft,
        "preference": assets.preference,
        "rl": assets.rl,
        "world_model": assets.world_model,
        "calibration": assets.calibration,
        "rejected_or_failed": assets.rejected_or_failed,
    }
    for name, records in named_views.items():
        (directory / f"{name}.jsonl").write_text(
            "".join(
                json.dumps(dict(record), sort_keys=True) + "\n" for record in records
            ),
            encoding="utf-8",
        )
    manifest = {
        **dict(assets.manifest),
        "bundle_hash": digest(assets.to_dict()),
    }
    path = directory / "manifest.json"
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def compile_recorded_trace(trace_directory: Path, output_directory: Path) -> Path:
    """Validate a completed interaction and materialize its training bundle."""

    header, events = load_trace(trace_directory)
    assets = compile_trajectory_assets(header, events)
    return write_compiled_trajectory_assets(output_directory, assets)
