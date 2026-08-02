"""Deciding what runs next, in three fixed steps.

Given a packet directory and the workflow that describes it, this module
reads the files and the run log, evaluates every fact the workflow's
predicates define, and returns the first of three checks that has an
opinion: does the log claim work the files do not back up, has the packet
already reached an end state, and — only once both of those are settled —
which single node's guard matches the facts.

A layout that matches no node's guard is not made to fit anything. It
names no node; whatever decides what happens to an unrecognised directory
is a separate concern from this one.

This module has no opinion about a human. Whether an open question in the
log should stop a node from starting is answered elsewhere; here, a fact is
a fact regardless of whether anyone has been asked about it yet.
"""

from __future__ import annotations

from pathlib import Path

from orglens.workflow.guards import matches
from orglens.workflow.predicates import evaluate
from orglens.workflow.result import DerivationResult, Outcome
from orglens.workflow.snapshot import PacketSnapshot, read_packet


def _unbacked_write(snapshot: PacketSnapshot) -> str | None:
    """Name a file a completed step claims to have produced that is not
    present, or ``None`` if every such claim is backed up by a file on
    disk. A step that named nothing to check is not examined.
    """
    for entry in snapshot.runs:
        if entry.get("type") != "node_completed":
            continue
        written = entry.get("wrote")
        if not written:
            continue
        for name in written:
            if name not in snapshot.files:
                return name
    return None


def derive_next_node(root: Path, workflow: dict) -> DerivationResult:
    """Read ``root`` under ``workflow`` and decide what happens next.

    Three checks run in a fixed order, and the first that has an opinion
    settles the outcome: a log entry unbacked by a file on disk, an end
    state the facts already satisfy, then whichever single node's guard
    the facts match. Reading and deciding are all this does — it never
    writes anything back.
    """
    snapshot = read_packet(root, workflow)
    facts = evaluate(snapshot, workflow)

    missing = _unbacked_write(snapshot)
    if missing is not None:
        return DerivationResult(
            outcome=Outcome.MALFORMED,
            node=None,
            reason=f"the log credits a file that is not present: {missing!r}",
            facts=facts,
        )

    for label, predicate in (workflow.get("terminal") or {}).items():
        if facts.get(predicate):
            return DerivationResult(
                outcome=Outcome.TERMINAL,
                node=None,
                reason=f"{predicate!r} is true ({label})",
                facts=facts,
            )

    nodes = workflow.get("nodes") or {}
    matched = [
        name
        for name, spec in nodes.items()
        if matches((spec or {}).get("guard") or {}, facts)
    ]

    if len(matched) > 1:
        return DerivationResult(
            outcome=Outcome.AMBIGUOUS,
            node=None,
            reason=f"more than one guard matched: {', '.join(sorted(matched))}",
            matched=matched,
            facts=facts,
        )

    if not matched:
        return DerivationResult(
            outcome=Outcome.UNKNOWN,
            node=None,
            reason="no node's guard matches this layout",
            facts=facts,
        )

    node = matched[0]
    guard = (nodes[node] or {}).get("guard") or {}
    satisfied = [
        name
        for name in list(guard.get("all", [])) + list(guard.get("any", []))
        if facts.get(name)
    ]
    reason = f"{node!r} matched on {', '.join(satisfied)}" if satisfied else f"{node!r} matched"

    return DerivationResult(
        outcome=Outcome.RUNNABLE,
        node=node,
        reason=reason,
        matched=matched,
        facts=facts,
    )
