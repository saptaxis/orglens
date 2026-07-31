"""Malformed-packet detection.

Tested before every node guard and before fallback adoption. A half-written
packet that superficially resembles new work must be reported, never adopted —
that is a silent wrong answer, the one failure mode with no other defence.
"""

from __future__ import annotations

from orglens.workflow.snapshot import PacketSnapshot

CONDITIONS = (
    "log_names_missing_file",
    "round_both_critiqued_and_audited",
    "rounds_without_artifact",
    "round_number_gap",
)


def detect(snapshot: PacketSnapshot) -> str | None:
    present = set(snapshot.files)

    for record in snapshot.runs:
        for name in (record.get("wrote") or {}):
            if name not in present:
                return "log_names_missing_file"

    by_round: dict[int, set[str]] = {}
    for record in snapshot.runs:
        if record.get("type") != "node_completed":
            continue
        number = record.get("round")
        if number is not None:
            by_round.setdefault(number, set()).add(record.get("node"))
    for nodes in by_round.values():
        if {"critique", "audit"} <= nodes:
            return "round_both_critiqued_and_audited"

    if snapshot.rounds and snapshot.artifact is None:
        return "rounds_without_artifact"

    if snapshot.rounds:
        numbers = sorted(snapshot.rounds)
        if numbers != list(range(1, len(numbers) + 1)):
            return "round_number_gap"

    return None
