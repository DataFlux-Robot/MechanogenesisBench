"""Python refinement mirror for formal/lean/.../TraceRefinement.lean.

A receipt is not proof that an event happened.  This module provides the
smallest runtime object needed to refine a raw event trace into a receipt:
projection, input/output binding, and cost fold must all match exactly.

This is deliberately separate from the historical update-credit receipt
schema. Existing artifacts remain readable; new generation certificates may
require a `TraceFaithfulRecord` alongside them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class TraceEvent:
    sequence: int
    input_digest: str
    output_digest: str
    cost: int

    def validate(self) -> None:
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0:
            raise ValueError("event sequence must be a nonnegative int")
        if isinstance(self.cost, bool) or not isinstance(self.cost, int) or self.cost < 0:
            raise ValueError("event cost must be a nonnegative int")
        for name, value in (("input_digest", self.input_digest), ("output_digest", self.output_digest)):
            if not isinstance(value, str) or not value:
                raise ValueError(f"event {name} must be nonempty text")


@dataclass(frozen=True)
class Trace:
    events: tuple[TraceEvent, ...]
    raw_input_digest: str
    raw_output_digest: str

    def validate(self) -> None:
        for event in self.events:
            event.validate()
        if not self.raw_input_digest or not self.raw_output_digest:
            raise ValueError("trace raw input/output digests must be nonempty")


@dataclass(frozen=True)
class TraceReceipt:
    event_summary: tuple[int, ...]
    input_digest: str
    output_digest: str
    total_cost: int

    def validate(self) -> None:
        if isinstance(self.total_cost, bool) or not isinstance(self.total_cost, int) or self.total_cost < 0:
            raise ValueError("receipt total_cost must be a nonnegative int")


@dataclass(frozen=True)
class TraceFaithfulRecord:
    trace: Trace
    receipt: TraceReceipt
    source: str = "runtime"

    def validate(self) -> None:
        self.trace.validate()
        self.receipt.validate()
        expected_summary = tuple(event.sequence for event in self.trace.events)
        if expected_summary != self.receipt.event_summary:
            raise ValueError("trace event projection does not match receipt")
        if self.trace.raw_input_digest != self.receipt.input_digest:
            raise ValueError("trace input digest does not match receipt")
        if self.trace.raw_output_digest != self.receipt.output_digest:
            raise ValueError("trace output digest does not match receipt")
        expected_cost = sum(event.cost for event in self.trace.events)
        if expected_cost != self.receipt.total_cost:
            raise ValueError("trace cost fold does not match receipt")

    @property
    def faithful(self) -> bool:
        try:
            self.validate()
        except ValueError:
            return False
        return True


def trace_receipt_from_events(
    events: Sequence[Mapping[str, Any]],
    *,
    raw_input_digest: str,
    raw_output_digest: str,
) -> TraceFaithfulRecord:
    """Compile raw runtime events; strict types and exact projection."""
    trace_events = tuple(
        TraceEvent(
            sequence=event["sequence"],
            input_digest=event["input_digest"],
            output_digest=event["output_digest"],
            cost=event["cost"],
        )
        for event in events
    )
    trace = Trace(trace_events, raw_input_digest, raw_output_digest)
    receipt = TraceReceipt(
        event_summary=tuple(event.sequence for event in trace_events),
        input_digest=raw_input_digest,
        output_digest=raw_output_digest,
        total_cost=sum(event.cost for event in trace_events),
    )
    result = TraceFaithfulRecord(trace, receipt)
    result.validate()
    return result
