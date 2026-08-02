"""Checking a deck's workflow definition before anything runs.

Routing has exactly two predicate forms: `exists:<glob>`, which asks the
packet's directory, and `after:<node>`, which asks the run log for its
cursor — the node named by the most recent routing fact. Because the cursor
is a single position, exactly one `after:` predicate is ever true for a
given snapshot. That turns one shape of definition bug into something a
checker can decide on its own, with no packet and no directory listing: if
two nodes' guards can both be satisfied by the same cursor value, the
definition is ambiguous no matter what the filesystem later says.

`validate_definition` never raises. It is the one gate standing between an
arbitrary mapping and the rest of the engine, so it has to survive whatever
shape it is handed.
"""

from __future__ import annotations

from orglens.workflow.predicates import AFTER, EXISTS, NOTHING

_CLAUSES = ("all", "any", "none")


def validate_definition(workflow: dict) -> list[str]:
    """Every problem with `workflow`, or an empty list if it is sound."""
    if not isinstance(workflow, dict):
        return [f"a workflow definition must be a mapping, got {workflow!r}"]

    problems: list[str] = []

    raw_nodes = workflow.get("nodes")
    nodes = raw_nodes if isinstance(raw_nodes, dict) else {}
    declared = {name for name in nodes if isinstance(name, str)}

    if NOTHING in nodes:
        problems.append(
            f"node {NOTHING!r} is reserved for the empty cursor and cannot "
            "be declared"
        )

    usable_guards: dict[str, dict] = {}

    for name, node in nodes.items():
        label = name if isinstance(name, str) else repr(name)

        if not isinstance(node, dict):
            problems.append(f"node {label!r} is not a mapping: {node!r}")
            continue

        guard = node.get("guard")
        if _is_usable_guard(guard):
            usable_guards[label] = guard
            for clause in _CLAUSES:
                for literal in guard.get(clause, []):
                    problems.extend(_check_literal(label, literal, declared))
        else:
            problems.append(f"node {label!r} has no usable guard: {guard!r}")

        writes = node.get("writes", [])
        if isinstance(writes, list):
            for entry in writes:
                if isinstance(entry, str) and _has_glob_character(entry):
                    problems.append(
                        f"node {label!r} writes a glob, not a literal name: "
                        f"{entry!r}"
                    )

    terminal = workflow.get("terminal")
    if isinstance(terminal, dict):
        for key, literal in terminal.items():
            owner = f"terminal[{key!r}]"
            problems.extend(_check_literal(owner, literal, declared))

    roots = workflow.get("roots")
    if roots is not None and (
        not isinstance(roots, list) or not all(isinstance(r, str) for r in roots)
    ):
        problems.append(f"roots must be a list of strings, got {roots!r}")

    problems.extend(_check_ambiguity(usable_guards, declared))

    return problems


def _is_usable_guard(guard: object) -> bool:
    if not isinstance(guard, dict) or not guard:
        return False
    present = [clause for clause in _CLAUSES if clause in guard]
    if not present:
        return False
    return all(isinstance(guard[clause], list) for clause in present)


def _has_glob_character(entry: str) -> bool:
    return any(character in entry for character in "*?[")


def _check_literal(owner: str, literal: object, declared: set[str]) -> list[str]:
    if not isinstance(literal, str) or not (
        literal.startswith(EXISTS) or literal.startswith(AFTER)
    ):
        return [f"{owner} names an unrecognized literal: {literal!r}"]

    if literal.startswith(AFTER):
        target = literal[len(AFTER):]
        if target != NOTHING and target not in declared:
            return [f"{owner} names an undeclared node: {literal!r}"]

    return []


def _check_ambiguity(usable_guards: dict[str, dict], declared: set[str]) -> list[str]:
    problems: list[str] = []
    for cursor in sorted(declared | {NOTHING}):
        matched = sorted(
            name
            for name, guard in usable_guards.items()
            if _could_match_cursor(guard, cursor)
        )
        if len(matched) > 1:
            cursor_literal = f"{AFTER}{cursor}"
            problems.append(
                f"nodes {matched!r} could each be satisfied by cursor "
                f"{cursor_literal!r} — ambiguous routing"
            )
    return problems


def _could_match_cursor(guard: dict, cursor: str) -> bool:
    """Could this guard match with the cursor fixed at `cursor`?

    Only `after:` literals are pinned by the cursor. Anything else (an
    `exists:` literal, or a literal this guard has no business carrying) is
    not decided by the cursor at all, so it is treated as free to come out
    either way — whichever favors a match.
    """
    if "all" in guard and not _all_could_match(guard["all"], cursor):
        return False
    if "any" in guard and not _any_could_match(guard["any"], cursor):
        return False
    if "none" in guard and not _none_could_match(guard["none"], cursor):
        return False
    return True


def _after_target(literal: object) -> str | None:
    if isinstance(literal, str) and literal.startswith(AFTER):
        return literal[len(AFTER):]
    return None


def _all_could_match(literals: list, cursor: str) -> bool:
    for literal in literals:
        target = _after_target(literal)
        if target is not None and target != cursor:
            return False
    return True


def _any_could_match(literals: list, cursor: str) -> bool:
    free = False
    for literal in literals:
        target = _after_target(literal)
        if target is None:
            free = True
        elif target == cursor:
            return True
    return free


def _none_could_match(literals: list, cursor: str) -> bool:
    for literal in literals:
        target = _after_target(literal)
        if target is not None and target == cursor:
            return False
    return True
