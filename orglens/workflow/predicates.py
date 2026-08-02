"""Two predicate forms, both parameterized by the deck.

The engine names neither a file nor a node. Every literal a guard clause or
a terminal value can use comes from the deck's own workflow definition:
``exists:<glob>`` asks the packet's directory listing, ``after:<node>`` asks
the run log for its cursor — the node named by the most recent routing fact.
``after:nothing`` is the one reserved case: it is true exactly when there is
no routing fact yet, because a packet's directory is reused indefinitely and
so cannot itself say what has already happened.

Because the cursor is a single position, exactly one ``after:`` predicate is
ever true for a given snapshot.
"""

from __future__ import annotations

import fnmatch

from orglens.workflow.runstate import last_routing_node
from orglens.workflow.snapshot import PacketSnapshot

EXISTS = "exists:"
AFTER = "after:"
NOTHING = "nothing"


def predicate_names(workflow: dict) -> frozenset[str]:
    """Every literal the deck's guards and terminal values name."""
    names: set[str] = set()
    for node in workflow.get("nodes", {}).values():
        guard = node.get("guard", {})
        for clause in ("all", "any", "none"):
            names.update(guard.get(clause, []))
    names.update(workflow.get("terminal", {}).values())
    return frozenset(names)


def evaluate(snapshot: PacketSnapshot, workflow: dict) -> dict[str, bool]:
    """Evaluate every predicate the deck names against one packet snapshot."""
    cursor = last_routing_node(snapshot.runs)
    facts: dict[str, bool] = {}
    for literal in predicate_names(workflow):
        if literal.startswith(EXISTS):
            glob = literal[len(EXISTS):]
            facts[literal] = any(
                fnmatch.fnmatch(name, glob) for name in snapshot.files
            )
        elif literal.startswith(AFTER):
            node = literal[len(AFTER):]
            if node == NOTHING:
                facts[literal] = cursor is None
            else:
                facts[literal] = cursor == node
        else:
            raise ValueError(literal)
    return facts
