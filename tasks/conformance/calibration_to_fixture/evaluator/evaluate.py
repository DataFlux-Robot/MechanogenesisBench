#!/usr/bin/env python3
"""Private conformance evaluator; it certifies no real-world physics."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from statistics import fmean


def fork_credit(receipts: list[dict[str, object]]) -> tuple[float, float]:
    trials: list[dict[str, float]] = []
    for receipt in receipts:
        raw_trials = receipt.get("recursive_fork_trials", [])
        if isinstance(raw_trials, list):
            trials.extend(item for item in raw_trials if isinstance(item, dict))
    if not trials:
        return 0.0, 0.0

    time_deltas: list[float] = []
    budget_deltas: list[float] = []
    for trial in trials:
        baseline_time = float(trial["baseline_future_time_s"])
        child_time = float(trial["child_future_time_s"])
        baseline_budget = float(trial["baseline_future_cost_usd"])
        child_budget = float(trial["child_future_cost_usd"])
        if baseline_time <= 0 or baseline_budget <= 0:
            return 0.0, 0.0
        time_deltas.append((baseline_time - child_time) / baseline_time)
        budget_deltas.append((baseline_budget - child_budget) / baseline_budget)
    return fmean(time_deltas), fmean(budget_deltas)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    submission = json.loads(args.submission.read_text(encoding="utf-8"))
    spec = json.loads((args.task_dir / "private/spec.json").read_text(encoding="utf-8"))
    decisions: list[dict[str, object]] = []

    for generation in submission["generations"]:
        index = int(generation["index"])
        artifact = generation["artifact"]
        receipts = generation["experiment_receipts"]
        before_upper = 0.0
        after_lower = 0.0
        margin = 1.0
        net_value = -1.0
        robustness = 0.0

        if index == 0 and artifact.get("artifact_type") == "calibration_fixture":
            before_error = float(artifact["pose_error_before_mm"])
            after_error = float(artifact["pose_error_after_mm"])
            before_upper = -before_error
            after_lower = -after_error
            margin = float(spec["calibration"]["margin"])
            errors = [
                float(value)
                for receipt in receipts
                for value in receipt.get("blinded_pose_errors_mm", [])
            ]
            robustness = (
                sum(value <= spec["calibration"]["max_pose_error_mm"] for value in errors)
                / len(errors)
                if errors
                else 0.0
            )
            net_value = (
                (before_error - after_error) * 100.0
                - float(artifact["design_cost_usd"]) / float(artifact["reuse_count"])
            )
        elif index == 1 and artifact.get("artifact_type") == "production_fixture":
            before_upper = float(artifact["yield_before"])
            trials = [float(value) for value in artifact["yield_after_trials"]]
            after_lower = min(trials) if trials else 0.0
            margin = float(spec["fixture"]["margin"])
            blinded_yields = [
                float(value)
                for receipt in receipts
                for value in receipt.get("blinded_yields", [])
            ]
            robustness = (
                sum(value >= spec["fixture"]["min_yield"] for value in blinded_yields)
                / len(blinded_yields)
                if blinded_yields
                else 0.0
            )
            net_value = (
                (after_lower - before_upper) * 100.0
                - float(artifact["design_cost_usd"]) / float(artifact["reuse_count"])
            )

        rrc_time, rrc_budget = fork_credit(receipts)
        accepted = (
            after_lower >= before_upper + margin
            and net_value > 0
            and robustness >= float(spec["minimum_robustness"])
        )
        decisions.append(
            {
                "index": index,
                "artifact_hash": generation["artifact_hash"],
                "accepted": accepted,
                "before_upper": before_upper,
                "after_lower": after_lower,
                "margin": margin,
                "net_value": net_value,
                "robustness_pass_rate": robustness,
                "evidence_tier": "conformance",
                "rrc_time_rate_delta": rrc_time,
                "rrc_budget_rate_delta": rrc_budget,
            }
        )

    report = {
        "schema_version": "0.1",
        "task_id": "conformance.calibration_to_fixture",
        "task_package_digest": os.environ["MBENCH_TASK_PACKAGE_DIGEST"],
        "evaluator_digest": os.environ["MBENCH_EVALUATOR_BUNDLE_DIGEST"],
        "decisions": decisions,
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
