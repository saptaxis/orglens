"""Guard evaluation — structured combinations of named predicates.

Not an expression language. `all` / `any` / `none` over a closed vocabulary,
combined conjunctively. No parsing, no precedence, no strings to interpret.
"""

from __future__ import annotations


def _lookup(facts: dict[str, bool], name: str) -> bool:
    if name not in facts:
        raise KeyError(f"unknown predicate: {name!r}")
    return facts[name]


def matches(guard: dict | str, facts: dict[str, bool]) -> bool:
    """True when every present clause is satisfied."""
    if not isinstance(guard, dict) or not guard:
        return False

    if "all" in guard and not all(_lookup(facts, n) for n in guard["all"]):
        return False
    if "any" in guard and not any(_lookup(facts, n) for n in guard["any"]):
        return False
    if "none" in guard and any(_lookup(facts, n) for n in guard["none"]):
        return False
    return True
