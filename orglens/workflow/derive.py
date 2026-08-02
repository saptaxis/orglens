"""derive_next_node — the pure function at the centre of the substrate.

Reads a packet, returns one classified outcome. Never writes, never launches.

Precedence is fixed and is not a priority list: malformed, terminal, node
guards, fallback. Between malformed and fallback, exactly one node guard may
match; two matching is an error, not a tiebreak, because whichever a session
picked first would be arbitrary.

Derivation has no opinion about humans. It always returns a node or a reason it
cannot; whether that node may run is the orchestrator's question, answered by
blocking.check().
"""

from __future__ import annotations

from pathlib import Path

from orglens.workflow import malformed as malformed_module
from orglens.workflow.guards import matches
from orglens.workflow.predicates import evaluate
from orglens.workflow.result import DerivationResult, Outcome
from orglens.workflow.snapshot import read_packet

FALLBACK = "fallback"


def derive_next_node(root: Path, workflow: dict) -> DerivationResult:
    snapshot = read_packet(root, workflow)
    facts = evaluate(snapshot, workflow)
    nodes = workflow.get("nodes", {})

    # 1. malformed — before anything else, and before fallback especially
    violation = malformed_module.detect(snapshot)
    if violation:
        return DerivationResult(
            outcome=Outcome.MALFORMED,
            reason=f"packet is malformed: {violation}",
            facts=facts,
        )

    # 2. terminal
    terminal = workflow.get("terminal", {})
    for label, predicate in terminal.items():
        if facts.get(predicate):
            return DerivationResult(
                outcome=Outcome.TERMINAL,
                reason=f"terminal: {label}",
                facts=facts,
            )

    # 3. node guards — exactly one may match
    fallback_nodes = [n for n, d in nodes.items() if d.get("guard") == FALLBACK]
    matched = [
        name
        for name, spec in nodes.items()
        if name not in fallback_nodes and matches(spec.get("guard", {}), facts)
    ]

    if len(matched) > 1:
        return DerivationResult(
            outcome=Outcome.AMBIGUOUS,
            reason=f"{len(matched)} guards matched: {', '.join(sorted(matched))}",
            matched=sorted(matched),
            facts=facts,
        )

    if len(matched) == 1:
        node = matched[0]
        return DerivationResult(
            outcome=Outcome.RUNNABLE,
            node=node,
            reason=_reason_for(node, facts),
            matched=matched,
            facts=facts,
        )

    # 4. fallback — only over a layout no known-state guard claimed
    if fallback_nodes:
        return DerivationResult(
            outcome=Outcome.ADOPTABLE,
            node=fallback_nodes[0],
            reason="no known-state guard matched; layout is unrecognised",
            facts=facts,
        )

    return DerivationResult(
        outcome=Outcome.UNKNOWN,
        reason="no guard matched and no fallback node is declared",
        facts=facts,
    )


def _reason_for(node: str, facts: dict[str, bool]) -> str:
    true_facts = sorted(name for name, value in facts.items() if value)
    return f"{node}: satisfied by {', '.join(true_facts) or 'no positive facts'}"
