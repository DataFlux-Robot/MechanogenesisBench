"""Trace refinement tests: no self-authored receipt can bypass mismatches."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from mechanogenesis_bench.trace_refinement import (
    Trace,
    TraceEvent,
    TraceFaithfulRecord,
    TraceReceipt,
    trace_receipt_from_events,
)


def good() -> TraceFaithfulRecord:
    return trace_receipt_from_events(
        [
            {"sequence": 0, "input_digest": "in0", "output_digest": "out0", "cost": 3},
            {"sequence": 1, "input_digest": "in1", "output_digest": "out1", "cost": 4},
        ],
        raw_input_digest="raw-in",
        raw_output_digest="raw-out",
    )


def test_trace_receipt_refines():
    record = good()
    assert record.faithful
    assert record.receipt.event_summary == (0, 1)
    assert record.receipt.total_cost == 7


@pytest.mark.parametrize(
    "change, message",
    [
        ("summary", "projection"),
        ("input", "input digest"),
        ("output", "output digest"),
        ("cost", "cost fold"),
    ],
)
def test_tampered_receipt_rejected(change, message):
    record = good()
    receipt = record.receipt
    if change == "summary":
        receipt = TraceReceipt((9, 1), receipt.input_digest, receipt.output_digest, receipt.total_cost)
    elif change == "input":
        receipt = TraceReceipt(receipt.event_summary, "tampered", receipt.output_digest, receipt.total_cost)
    elif change == "output":
        receipt = TraceReceipt(receipt.event_summary, receipt.input_digest, "tampered", receipt.total_cost)
    else:
        receipt = TraceReceipt(receipt.event_summary, receipt.input_digest, receipt.output_digest, 99)
    tampered = TraceFaithfulRecord(record.trace, receipt)
    assert not tampered.faithful
    with pytest.raises(ValueError, match=message):
        tampered.validate()


def test_negative_event_fields_rejected():
    with pytest.raises(ValueError, match="sequence"):
        trace_receipt_from_events(
            [{"sequence": -1, "input_digest": "i", "output_digest": "o", "cost": 0}],
            raw_input_digest="i", raw_output_digest="o",
        )
    with pytest.raises(ValueError, match="cost"):
        trace_receipt_from_events(
            [{"sequence": 0, "input_digest": "i", "output_digest": "o", "cost": -1}],
            raw_input_digest="i", raw_output_digest="o",
        )


def test_empty_trace_has_zero_cost():
    record = trace_receipt_from_events([], raw_input_digest="i", raw_output_digest="o")
    assert record.faithful and record.receipt.total_cost == 0
