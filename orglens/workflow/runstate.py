"""Run state — the program's working memory.

Append-only, one JSON object per line, four declared entry kinds. It holds what
happened; what happens next stays derived. That line is what keeps it from
becoming the status field I1 forbids: a past fact cannot drift, because nothing
that happens later makes it false.
"""

from __future__ import annotations

import json
from pathlib import Path

RUNS = "runs.jsonl"

ENTRY_TYPES = frozenset(
    {"node_completed", "needs_human", "human_resolved", "postcondition_failed"}
)

MANDATORY = ("type", "at", "event_id")

#: Keys that describe the present rather than the past.
FORBIDDEN_KEYS = frozenset(
    {"current_state", "status", "pending", "next_node", "state"}
)

#: Keys each type additionally requires.
REQUIRED_BY_TYPE = {
    "node_completed": ("node",),
    "needs_human": ("node", "question"),
    "human_resolved": ("resolves",),
    "postcondition_failed": ("node", "expected", "derived"),
}


def validate_entry(entry: dict) -> list[str]:
    problems: list[str] = []

    for key in MANDATORY:
        if key not in entry:
            problems.append(f"entry is missing mandatory key {key!r}")

    kind = entry.get("type")
    if kind is not None and kind not in ENTRY_TYPES:
        problems.append(f"unknown entry type {kind!r}")
    else:
        for key in REQUIRED_BY_TYPE.get(kind, ()):
            if key not in entry:
                problems.append(f"{kind} entry is missing {key!r}")

    for key in sorted(FORBIDDEN_KEYS & set(entry)):
        problems.append(
            f"{key!r} projects current state; run state records past facts only"
        )

    return problems


def read_entries(packet: Path) -> list[dict]:
    path = Path(packet) / RUNS
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text().splitlines() if line.strip()
    ]


def unresolved_needs_human(entries: list[dict]) -> dict | None:
    """The outstanding question, if any. Most recent wins."""
    resolved = {
        e.get("resolves") for e in entries if e.get("type") == "human_resolved"
    }
    outstanding = [
        e
        for e in entries
        if e.get("type") == "needs_human" and e.get("event_id") not in resolved
    ]
    return outstanding[-1] if outstanding else None


def completed(
    entries: list[dict], node: str, round_number: int | None = None
) -> bool:
    for entry in entries:
        if entry.get("type") != "node_completed" or entry.get("node") != node:
            continue
        if round_number is None or entry.get("round") == round_number:
            return True
    return False
