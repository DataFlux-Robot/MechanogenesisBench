"""Executable mirror of `formal/lean/Mechanogenesis/Kernel/S1CausalContract.lean`.

The S1 causal-update promotion contract (ten gates).  The Lean side fixes the
decision semantics and proves what each decision obligates; this module
mirrors `Interval` / `Evidence` / `Decision` / `checkS1` exactly and adds the
per-gate violation report Lean deliberately omits.

Field-for-field parity with the Lean `Evidence` structure is enforced by
`tests/test_s1_contract.py::test_mirror_parity_with_lean` (names and gate
numbers).  Keep both sides in lockstep: changing one requires changing the
other in the same commit.

The closed loop with training reality (per the handoff §3.2):
  1. an S1 run emits exactly these receipts/counts into `Evidence`;
  2. `check_s1` decides promote / abstain / violate and reports which gates
     failed;
  3. repeated abstentions or premise failures feed back into the Lean
     premises (e.g. the error bounds feeding `rrc_discrimination_threshold`),
     never into silent threshold relaxation.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
from hashlib import sha256
from typing import Any


def digest(value: str) -> int:
    """Content-addressed digest as used across the kernel (Nat hex → int)."""
    return int(sha256(value.encode("utf-8")).hexdigest()[:16], 16)


@dataclass(frozen=True)
class Interval:
    lower: int
    upper: int

    def valid(self) -> bool:
        return self.lower <= self.upper


class Decision(str, Enum):
    PROMOTE = "promote"
    ABSTAIN = "abstain"
    VIOLATE = "violate"


@dataclass(frozen=True)
class Evidence:
    # Gate 1: CommonParent
    parent_checkpoint_hash: int
    child_parent_hash: int
    runtime_hash: int
    # Gate 2: MatchedUpdateBudget
    supervised_tokens: int
    matched_tokens: int
    optimizer_steps: int
    matched_steps: int
    # Gate 3: FutureUnread
    credit_seal_hash: int
    final_query_seal_hash: int
    future_unread: bool
    # Gate 4: ForkIsolation
    fork_isolated: bool
    # Gate 5: Attribution
    rrc_evidence_hash: int
    placebo_evidence_hash: int
    attribution_matched: bool
    # Gate 6: ReliableSelection
    candidate_interval: Interval
    cluster_valid: bool
    # Gate 7: Transport
    shift_bound: int
    transport_declared: bool
    # Gate 8: FullCost
    full_cost: int
    cost_complete: bool
    # Gate 9: Promotion margins
    parent_future_interval: Interval
    placebo_future_interval: Interval
    # Gate 10: FailurePreservation
    losing_forks_preserved: bool


GATE_NAMES = {
    1: "CommonParent",
    2: "MatchedUpdateBudget",
    3: "FutureUnread",
    4: "ForkIsolation",
    5: "Attribution",
    6: "ReliableSelection",
    7: "Transport",
    8: "FullCost",
    9: "PromotionMargins",
    10: "FailurePreservation",
}


def hard_gate_failures(e: Evidence) -> list[int]:
    failures: list[int] = []
    if e.child_parent_hash != e.parent_checkpoint_hash:
        failures.append(1)
    if not (
        e.supervised_tokens == e.matched_tokens
        and e.optimizer_steps == e.matched_steps
    ):
        failures.append(2)
    if not e.future_unread:
        failures.append(3)
    if not e.fork_isolated:
        failures.append(4)
    if not e.attribution_matched:
        failures.append(5)
    if not e.cost_complete:
        failures.append(8)
    if not e.losing_forks_preserved:
        failures.append(10)
    return failures


def soft_gate_failures(e: Evidence) -> list[int]:
    failures: list[int] = []
    if not e.cluster_valid:
        failures.append(6)
    if not e.transport_declared:
        failures.append(7)
    if not (
        e.candidate_interval.valid()
        and e.parent_future_interval.valid()
        and e.placebo_future_interval.valid()
    ):
        failures.append(6)
    if not (
        e.parent_future_interval.upper + e.full_cost < e.candidate_interval.lower
        and e.placebo_future_interval.upper + e.full_cost
        < e.candidate_interval.lower
    ):
        failures.append(9)
    return failures


def check_s1(e: Evidence) -> tuple[Decision, list[int]]:
    """Mirror of `Mechanogenesis.S1.checkS1` plus the failing-gate report."""
    hard = hard_gate_failures(e)
    if hard:
        return Decision.VIOLATE, hard
    soft = soft_gate_failures(e)
    if soft:
        return Decision.ABSTAIN, soft
    return Decision.PROMOTE, []


LEAN_EVIDENCE_FIELDS = (
    "parentCheckpointHash childParentHash runtimeHash "
    "supervisedTokens matchedTokens optimizerSteps matchedSteps "
    "creditSealHash finalQuerySealHash futureUnread "
    "forkIsolated "
    "rrcEvidenceHash placeboEvidenceHash attributionMatched "
    "candidateInterval clusterValid "
    "shiftBound transportDeclared "
    "fullCost costComplete "
    "parentFutureInterval placeboFutureInterval "
    "losingForksPreserved"
).split()


def snake(name: str) -> str:
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0:
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def mirror_parity() -> list[str]:
    """Python field names ↔ Lean field names (for the parity test)."""
    python_fields = [f.name for f in fields(Evidence)]
    expected = [snake(n) for n in LEAN_EVIDENCE_FIELDS]
    mismatches = []
    if python_fields != expected:
        mismatches.append(
            f"field drift: python={python_fields} lean={expected}"
        )
    return mismatches


def evidence_from_run(run_receipts: dict[str, Any]) -> Evidence:
    """Build Evidence from a run receipt mapping (metric-ledger constructor).

    This is the single entry point a four-fork run uses to compile its
    receipts into the contract; unknown keys are rejected so missing metrics
    surface immediately instead of defaulting silently.
    """
    known = {f.name for f in fields(Evidence)}
    unknown = set(run_receipts) - known
    if unknown:
        raise ValueError(f"unknown receipt keys: {sorted(unknown)}")
    missing = known - set(run_receipts)
    if missing:
        raise ValueError(f"missing receipt keys: {sorted(missing)}")
    normalized = dict(run_receipts)
    for key in ("candidate_interval", "parent_future_interval",
                "placebo_future_interval"):
        value = normalized[key]
        if isinstance(value, dict):
            normalized[key] = Interval(**value)
    return Evidence(**normalized)
