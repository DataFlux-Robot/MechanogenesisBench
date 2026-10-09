"""Negative + positive tests for the S1 causal-update contract mirror.

Every negative test is a theorem on the Lean side
(`future_read_forces_violate`, `budget_mismatch_forces_violate`,
`missing_cost_forces_violate`, `losing_forks_dropped_forces_violate`,
`transport_undeclared_forces_not_promote`, `margin_failure_forces_not_promote`,
`promote_margin_certified_by_calibrated_estimates`); these tests pin the
Python mirror to the same obligations.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from mechanogenesis_bench.s1_contract import (
    Decision,
    Evidence,
    Interval,
    check_s1,
    digest,
    evidence_from_run,
    mirror_parity,
)


def good_evidence(**overrides) -> Evidence:
    base = dict(
        parent_checkpoint_hash=digest("parent"),
        child_parent_hash=digest("parent"),
        runtime_hash=digest("runtime"),
        supervised_tokens=1000,
        matched_tokens=1000,
        optimizer_steps=10,
        matched_steps=10,
        credit_seal_hash=digest("credit-seal"),
        final_query_seal_hash=digest("final-seal"),
        future_unread=True,
        fork_isolated=True,
        rrc_evidence_hash=digest("rrc"),
        placebo_evidence_hash=digest("placebo"),
        attribution_matched=True,
        candidate_interval=Interval(90, 100),
        cluster_valid=True,
        shift_bound=5,
        transport_declared=True,
        full_cost=3,
        cost_complete=True,
        parent_future_interval=Interval(50, 60),
        placebo_future_interval=Interval(55, 65),
        losing_forks_preserved=True,
    )
    base.update(overrides)
    return Evidence(**base)


def test_mirror_parity_with_lean():
    assert mirror_parity() == []


def test_positive_case_promotes():
    decision, gates = check_s1(good_evidence())
    assert decision is Decision.PROMOTE
    assert gates == []


def test_parent_mismatch_violates():
    decision, gates = check_s1(
        good_evidence(child_parent_hash=digest("other-parent"))
    )
    assert decision is Decision.VIOLATE
    assert gates == [1]


def test_budget_mismatch_violates():
    decision, gates = check_s1(good_evidence(supervised_tokens=1200))
    assert decision is Decision.VIOLATE
    assert gates == [2]


def test_future_read_leak_violates():
    decision, gates = check_s1(good_evidence(future_unread=False))
    assert decision is Decision.VIOLATE
    assert gates == [3]


def test_fork_not_isolated_violates():
    decision, gates = check_s1(good_evidence(fork_isolated=False))
    assert decision is Decision.VIOLATE
    assert gates == [4]


def test_attribution_mismatch_violates():
    decision, gates = check_s1(good_evidence(attribution_matched=False))
    assert decision is Decision.VIOLATE
    assert gates == [5]


def test_missing_cost_violates():
    decision, gates = check_s1(good_evidence(cost_complete=False))
    assert decision is Decision.VIOLATE
    assert gates == [8]


def test_losing_forks_dropped_violates():
    decision, gates = check_s1(good_evidence(losing_forks_preserved=False))
    assert decision is Decision.VIOLATE
    assert gates == [10]


def test_undeclared_transport_abstains_not_promotes():
    decision, gates = check_s1(good_evidence(transport_declared=False))
    assert decision is Decision.ABSTAIN
    assert gates == [7]


def test_missing_margin_abstains_not_promotes():
    decision, gates = check_s1(
        good_evidence(parent_future_interval=Interval(50, 95))
    )
    assert decision is Decision.ABSTAIN
    assert 9 in gates


def test_placebo_margin_binding():
    # candidate clears parent but NOT placebo after full cost → abstain
    decision, gates = check_s1(
        good_evidence(placebo_future_interval=Interval(80, 98))
    )
    assert decision is Decision.ABSTAIN
    assert 9 in gates


def test_invalid_interval_abstains():
    decision, gates = check_s1(
        good_evidence(candidate_interval=Interval(100, 90))
    )
    assert decision is Decision.ABSTAIN
    assert gates == [6]


def test_hard_failure_dominates_soft():
    # even with everything else fine, a leak + no margin reports only hard
    decision, gates = check_s1(
        good_evidence(future_unread=False, transport_declared=False)
    )
    assert decision is Decision.VIOLATE
    assert gates == [3]


def test_run_receipt_constructor_strict():
    e = good_evidence()
    from dataclasses import asdict

    receipts = asdict(e)
    built = evidence_from_run(receipts)
    assert built == e
    with pytest.raises(ValueError, match="unknown"):
        evidence_from_run({**receipts, "extra_key": 1})
    with pytest.raises(ValueError, match="missing"):
        evidence_from_run({k: v for k, v in receipts.items() if k != "full_cost"})
