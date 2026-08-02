"""Checking a workflow definition for defects before it is ever run.

This is a static check of the declaration alone — no fixtures, no synthetic
packets, no attempt to prove a property by constructing a scenario that
satisfies it. A scenario built by the same assumptions as the code it tests
agrees with those assumptions, not with reality; every defect that actually
mattered here was found by running against real files instead.

One of these checks exists because of a real failure: a node whose
``expect`` named itself. The postcondition check treated that node's own
completion as proof it had reached its own target, so a packet re-ran the
same step forever while every check along the way reported success. A
self-referential ``expect`` is now rejected before a workflow ever runs.
"""

from __future__ import annotations

from orglens.workflow.predicates import predicate_names

_OUTCOME_NAMES = frozenset({"runnable", "terminal", "ambiguous", "malformed", "unknown"})


def _guard_predicates(guard: dict, node: str, problems: list[str]) -> set[str]:
    """Names of the predicates a guard cites. A clause whose value is not a
    list (a bare string, for instance) is reported and skipped rather than
    iterated character by character.
    """
    names: set[str] = set()
    for clause in ("all", "any", "none"):
        if clause not in guard:
            continue
        value = guard[clause]
        if not isinstance(value, list):
            problems.append(
                f"node {node!r} guard clause {clause!r} is not a list: {value!r}"
            )
            continue
        names.update(value)
    return names


def validate_definition(workflow: dict) -> list[str]:
    """Return every problem found in ``workflow``, as human-readable
    strings naming the node and the offending value. Never raises: a
    malformed definition is data to report on, not an exception.
    """
    problems: list[str] = []

    nodes = workflow.get("nodes") or {}
    declared = set(nodes)
    known_predicates = predicate_names(workflow)

    for name, spec in nodes.items():
        if not isinstance(spec, dict):
            problems.append(f"node {name!r} is not a mapping: {spec!r}")
            continue

        guard = spec.get("guard")

        if not isinstance(guard, dict) or not guard:
            problems.append(f"node {name!r} has no usable guard: {guard!r}")
        else:
            for predicate in sorted(_guard_predicates(guard, name, problems)):
                if predicate not in known_predicates:
                    problems.append(
                        f"node {name!r} guards on unknown predicate {predicate!r}"
                    )

        mutates = bool(spec.get("mutates"))
        diagnoses = bool(spec.get("diagnoses"))
        if mutates and diagnoses:
            problems.append(f"node {name!r} declares both mutates and diagnoses")

        if diagnoses and "must_not_modify" not in spec:
            problems.append(
                f"node {name!r} declares diagnoses without must_not_modify"
            )

        expect = spec.get("expect")
        if expect is not None:
            if expect == name:
                problems.append(f"node {name!r} names itself in expect: {expect!r}")
            elif expect not in declared and expect not in _OUTCOME_NAMES:
                problems.append(
                    f"node {name!r} expects {expect!r}, which is neither a declared "
                    "node nor an outcome"
                )

    terminal = workflow.get("terminal")
    if terminal is not None and not isinstance(terminal, dict):
        problems.append(f"terminal is not a mapping: {terminal!r}")
    else:
        for label, predicate in (terminal or {}).items():
            if predicate not in known_predicates:
                problems.append(
                    f"terminal {label!r} names unknown predicate {predicate!r}"
                )

    return problems
