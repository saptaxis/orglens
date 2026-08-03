"""What runs next, derived fresh from a packet's current shape.

Precedence is exactly two steps. First, every terminal value the deck
declares is checked against the packet's facts; if any one of them holds,
the run is over and nothing else is consulted. Otherwise every node's guard
is checked against the same facts. Exactly one match names the node to run.
More than one match is a deck authoring error, not a tiebreak to resolve
quietly. No match at all is not an error either — it is a packet shape the
deck's guards do not recognise, and the reason explains, node by node, which
guard entries came back false so the gap is a diagnosis rather than a
mystery.

This module only reads a packet and answers a question about it. It never
writes to the packet and never launches anything on its behalf.
"""

from __future__ import annotations

from pathlib import Path

from orglens.workflow.guards import matches
from orglens.workflow.predicates import evaluate
from orglens.workflow.result import DerivationResult, Outcome
from orglens.workflow.snapshot import read_packet


def _unknown_reason(nodes: dict, facts: dict[str, bool]) -> str:
    """One line per declared node, naming the guard entries that blocked it.

    An ``all`` entry blocks its clause when it is false. A ``none`` entry
    blocks its clause when it is true — the opposite test, because presence
    is what a ``none`` clause forbids. An ``any`` clause blocks only when
    every one of its entries is false, in which case every one of them is
    named. An entry named by more than one clause of the same guard is
    reported once, not once per clause.
    """
    lines = []
    for name, spec in nodes.items():
        guard = spec.get("guard", {})
        blocking: dict[str, bool] = {}

        for entry in guard.get("all", []):
            if not facts.get(entry):
                blocking.setdefault(entry, facts.get(entry))

        any_entries = guard.get("any", [])
        if any_entries and not any(facts.get(entry) for entry in any_entries):
            for entry in any_entries:
                blocking.setdefault(entry, facts.get(entry))

        for entry in guard.get("none", []):
            if facts.get(entry):
                blocking.setdefault(entry, facts.get(entry))

        parts = [f"{entry}={value}" for entry, value in blocking.items()]
        lines.append(f"{name}: " + ", ".join(parts))
    return "\n".join(lines)


def derive_next_node(root: Path, workflow: dict) -> DerivationResult:
    """Read one packet and answer what runs next, or why nothing does."""
    snapshot = read_packet(Path(root))
    facts = evaluate(snapshot, workflow)

    for label, literal in workflow.get("terminal", {}).items():
        if facts.get(literal):
            return DerivationResult(
                outcome=Outcome.TERMINAL,
                node=None,
                reason=f"terminal: {label} ({literal}=True)",
                matched=[],
                facts=facts,
            )

    nodes = workflow.get("nodes", {})
    matched = [
        name for name, spec in nodes.items() if matches(spec.get("guard", {}), facts)
    ]

    if len(matched) == 1:
        node = matched[0]
        return DerivationResult(
            outcome=Outcome.RUNNABLE,
            node=node,
            reason=f"{node}: guard matched",
            matched=matched,
            facts=facts,
        )

    if len(matched) > 1:
        return DerivationResult(
            outcome=Outcome.AMBIGUOUS,
            node=None,
            reason="more than one guard matched: " + ", ".join(sorted(matched)),
            matched=matched,
            facts=facts,
        )

    return DerivationResult(
        outcome=Outcome.UNKNOWN,
        node=None,
        reason=_unknown_reason(nodes, facts),
        matched=[],
        facts=facts,
    )
