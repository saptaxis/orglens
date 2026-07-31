"""Validation of a workflow definition, and of its edges against fixtures.

Fixtures, not a general prover. Proving what states `revise` can produce would
need a model of what an LLM writes and what a human then ratifies. What has
actually found every defect in this design is tracing concrete cycles, so that
is what this automates.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from orglens.workflow.derive import FALLBACK, derive_next_node
from orglens.workflow.malformed import CONDITIONS
from orglens.workflow.predicates import PREDICATE_NAMES
from orglens.workflow.result import Outcome


def _edge_pairs(workflow: dict) -> list[tuple[str, str]]:
    pairs = []
    for edge in workflow.get("edges", []):
        if isinstance(edge, str) and "->" in edge:
            source, target = edge.split("->", 1)
            pairs.append((source.strip(), target.strip()))
        elif isinstance(edge, dict):
            pairs.append((edge.get("from", ""), edge.get("to", "")))
    return pairs


def validate_definition(workflow: dict) -> list[str]:
    problems: list[str] = []
    nodes = workflow.get("nodes", {})

    for name, spec in nodes.items():
        if not isinstance(spec, dict):
            continue
        guard = spec.get("guard")
        if guard == FALLBACK:
            continue
        if not isinstance(guard, dict) or not guard:
            problems.append(f"node {name!r} has no usable guard")
            continue
        for clause in ("all", "any", "none"):
            for predicate in guard.get(clause, []):
                if predicate not in PREDICATE_NAMES:
                    problems.append(
                        f"node {name!r} uses unknown predicate {predicate!r}"
                    )

    for source, target in _edge_pairs(workflow):
        for endpoint in (source, target):
            if endpoint not in nodes:
                problems.append(f"edge references undeclared node {endpoint!r}")

    for condition in workflow.get("malformed", []):
        if condition not in CONDITIONS:
            problems.append(f"unknown malformed condition {condition!r}")

    terminal = workflow.get("terminal", {})
    for label, predicate in terminal.items():
        if predicate not in PREDICATE_NAMES:
            problems.append(
                f"terminal {label!r} uses unknown predicate {predicate!r}"
            )

    return problems


def validate_edges(
    workflow: dict, fixtures: list[tuple[dict, str]]
) -> list[str]:
    """Each fixture is ({filename: content}, expected_node). Reports mismatches."""
    problems: list[str] = []

    for index, (files, expected) in enumerate(fixtures):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, content in files.items():
                (root / name).write_text(content)
            result = derive_next_node(root, workflow)

        actual = result.node
        if result.outcome in (Outcome.MALFORMED, Outcome.AMBIGUOUS):
            actual = str(result.outcome)
        if actual != expected:
            problems.append(
                f"fixture {index}: expected {expected}, got {actual} "
                f"({result.reason})"
            )

    return problems
