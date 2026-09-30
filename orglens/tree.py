"""The tree `part_of` builds. One reading of it, used by everything.

Every unit is a node. A unit with no `part_of` is a top-level node; every
other hangs under the unit it names. Membership is stated, never contained:
where a folder sits plays no part here.

Two things a marker can say that a tree cannot hold are kept visible rather
than dropped: a parent that is no unit, and a cycle. Both leave the unit
top-level, so nothing that walks the tree loses it or loops on it, and both
are listed for `check` to report.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Tree:
    #: name -> parent, only for a parent that is a unit and not in a cycle.
    parent: dict[str, str] = field(default_factory=dict)
    #: name -> its children, sorted.
    children: dict[str, list[str]] = field(default_factory=dict)
    #: No parent, a parent that is no unit, or in a cycle. Sorted.
    top: list[str] = field(default_factory=list)
    #: name -> the parent it names that is no unit.
    unknown: dict[str, str] = field(default_factory=dict)
    #: Each cycle once, from its smallest name, in the order the chain runs.
    cycles: list[list[str]] = field(default_factory=list)


def build(part_of: dict[str, str | None]) -> Tree:
    unknown = {n: p for n, p in part_of.items() if p and p not in part_of}

    in_cycle: set[str] = set()
    cycles: list[list[str]] = []
    for start in sorted(part_of):
        chain: list[str] = []
        here: str | None = start
        while here in part_of and here not in chain and here not in in_cycle:
            chain.append(here)
            here = part_of[here]
        if here in chain:
            loop = chain[chain.index(here):]
            first = loop.index(min(loop))
            cycles.append(loop[first:] + loop[:first])
            in_cycle.update(loop)

    parent = {
        n: p for n, p in part_of.items()
        if p and p in part_of and n not in in_cycle
    }
    children: dict[str, list[str]] = {}
    for n, p in sorted(parent.items()):
        children.setdefault(p, []).append(n)
    top = sorted(n for n in part_of if n not in parent)
    return Tree(parent=parent, children=children, top=top,
                unknown=unknown, cycles=sorted(cycles))


def below(tree: Tree, name: str) -> list[str]:
    """`name` and every unit under it, depth first, sorted at each level."""
    out: list[str] = []
    stack = [name]
    while stack:
        here = stack.pop()
        if here in out:
            continue
        out.append(here)
        stack.extend(reversed(tree.children.get(here, [])))
    return out


def draw(tree: Tree, label, start: str | None = None) -> list[str]:
    """The tree as lines, every top node and its subtree, or `start`'s.
    `label(name)` gives a node's text; a parent that is no unit and a cycle
    are marked after it, since both leave the unit top-level."""
    cycle_of = {n: c for c in tree.cycles for n in c}

    def text(name: str) -> str:
        marks = []
        if name in tree.unknown:
            marks.append(f"part of {tree.unknown[name]}: no such unit")
        if name in cycle_of:
            loop = cycle_of[name]
            marks.append("in a cycle: " + " > ".join([*loop, loop[0]]))
        return label(name) + "".join(f"  ({m})" for m in marks)

    lines: list[str] = []

    def walk(name: str, lead: str, seen: set[str]) -> None:
        kids = [k for k in tree.children.get(name, []) if k not in seen]
        for i, kid in enumerate(kids):
            last = i == len(kids) - 1
            lines.append(lead + ("└── " if last else "├── ") + text(kid))
            walk(kid, lead + ("    " if last else "│   "), seen | {kid})

    for top in ([start] if start is not None else tree.top):
        lines.append(text(top))
        walk(top, "", {top})
    return lines


def nested(tree: Tree, start: str, node) -> dict:
    """`start`'s subtree as nested data: `node(name)` gives a node's fields,
    and `children` is added."""
    return {**node(start),
            "children": [nested(tree, kid, node) for kid in tree.children.get(start, [])]}
