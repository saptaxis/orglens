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
    """One line per declared node, naming the guard entries that were false."""
    lines = []
    for name, spec in nodes.items():
        guard = spec.get("guard", {})
        entries = []
        for clause in ("all", "any", "none"):
            entries.extend(guard.get(clause, []))
        false_entries = [
            f"{entry}={facts.get(entry)}" for entry in entries if not facts.get(entry)
        ]
        lines.append(f"{name}: " + ", ".join(false_entries))
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
