"""Run state: the program's working memory.

A run's state is not a snapshot to overwrite — it is a growing ledger of
past facts. Each line in ``runs.jsonl`` records something that has already
happened: a node completed, a human was asked a question, a human answered
it. Nothing in the ledger is ever rewritten, because a past fact cannot
drift — only new facts can be added.

This module is the one place that knows what a valid fact looks like
(``validate_entry``), the one place that writes them (``append_fact``, which
stamps the mandatory bookkeeping keys and then validates what it is about to
write, so a fact on disk is valid by construction), and the one place that
reads them back to answer the two questions the rest of the workflow engine
actually asks: where does the run stand right now (``last_routing_node``,
the cursor), and is there an open question a human hasn't answered yet
(``unresolved_needs_human``).

A packet lives in one directory, reused indefinitely — file existence cannot
say what comes next, because after one pass every output exists and keeps
existing. Only the order of facts in this ledger can. Two kinds of fact move
the cursor: a node finishing on its own (``node_completed``), and a human
deliberately naming where work resumes (``resumed_at``). Moving the cursor
is always a new fact appended to the end, never a field changed in place.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path

ENTRY_TYPES: frozenset[str] = frozenset(
    {"node_completed", "resumed_at", "needs_human", "human_resolved"}
)

# The two kinds of fact that move the cursor. Everything else records
# something about a node without changing where the run stands.
ROUTING_TYPES: frozenset[str] = frozenset({"node_completed", "resumed_at"})

# Keys that describe the present or the future rather than record a fact
# about the past. A run-state entry is a fact that already happened; it
# must never carry a projection of "current" state or a plan for "next".
FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {"current_state", "status", "pending", "next_node", "state"}
)

_MANDATORY_KEYS: frozenset[str] = frozenset({"type", "at", "event_id"})

_REQUIRED_BY_TYPE: dict[str, frozenset[str]] = {
    "node_completed": frozenset({"node"}),
    "resumed_at": frozenset({"node"}),
    "needs_human": frozenset({"node", "question"}),
    "human_resolved": frozenset({"resolves"}),
}


def validate_entry(entry: dict) -> list[str]:
    """Return every problem with ``entry``, or an empty list if it is well formed."""
    problems: list[str] = []

    for key in sorted(_MANDATORY_KEYS):
        if key not in entry:
            problems.append(f"missing mandatory key: {key!r}")

    entry_type = entry.get("type")
    if entry_type is not None and entry_type not in ENTRY_TYPES:
        problems.append(f"invented entry type: {entry_type!r}")

    if entry_type in _REQUIRED_BY_TYPE:
        for key in sorted(_REQUIRED_BY_TYPE[entry_type]):
            if key not in entry:
                problems.append(f"{entry_type} is missing required key: {key!r}")

    for key in sorted(FORBIDDEN_KEYS):
        if key in entry:
            problems.append(f"forbidden key (not a past fact): {key!r}")

    return problems


def read_entries(packet: Path) -> list[dict]:
    """Read every recorded fact for this packet, oldest first.

    A packet that has not recorded anything yet has an empty run state, not
    a missing file that is an error.
    """
    run_state = packet / "runs.jsonl"
    if not run_state.exists():
        return []
    entries = []
    for line in run_state.read_text().splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def append_fact(packet: Path, fact: dict) -> dict:
    """Stamp, validate, and append a fact. Returns the stamped fact.

    ``at`` and ``event_id`` are stamped only when absent, so a caller may
    supply its own. The complete, stamped fact is then validated; any
    problem raises ``ValueError`` naming every problem found, so an invalid
    fact never reaches disk.
    """
    stamped = dict(fact)
    if "at" not in stamped:
        stamped["at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    if "event_id" not in stamped:
        stamped["event_id"] = uuid.uuid4().hex[:12]

    problems = validate_entry(stamped)
    if problems:
        raise ValueError("; ".join(problems))

    packet.mkdir(parents=True, exist_ok=True)
    run_state = packet / "runs.jsonl"
    with run_state.open("a") as handle:
        handle.write(json.dumps(stamped) + "\n")

    return stamped


def unresolved_needs_human(entries: list[dict]) -> dict | None:
    """Return the most recent ``needs_human`` fact with no matching
    ``human_resolved``, or ``None`` if every question has been answered.
    """
    resolved = {
        e["resolves"] for e in entries if e.get("type") == "human_resolved"
    }
    outstanding = [
        e
        for e in entries
        if e.get("type") == "needs_human" and e.get("event_id") not in resolved
    ]
    return outstanding[-1] if outstanding else None


def last_routing_node(entries: list[dict]) -> str | None:
    """Return the node of the most recent routing fact, or ``None``.

    This is the cursor: the node of the most recent entry whose type is in
    ``ROUTING_TYPES``. A ``needs_human`` or ``human_resolved`` fact leaves
    the cursor where it was — asking a question and answering it do not by
    themselves move the run forward.
    """
    for entry in reversed(entries):
        if entry.get("type") in ROUTING_TYPES:
            return entry["node"]
    return None


def workflow_version(path: Path) -> str:
    """Content-address a workflow definition file.

    `append_fact` stamps this value onto every recorded fact — a note of
    which definition was in force when the fact was written, nothing more.
    Nothing in this engine reads the stamp back: no comparison against the
    current definition, no check, no invalidation of a cursor written under
    an earlier one. It is bookkeeping only, until something is built to
    consult it.
    """
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return f"sha256:{digest}"
