"""Whether a human owes the packet an answer.

A human is never a node, never an actor in the graph, and never a routing
outcome. Human involvement is a pause on the orchestrator, expressed as an
unresolved `needs_human` entry in run state.

Derivation is not consulted about humans and does not know they exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from orglens.workflow.runstate import read_entries, unresolved_needs_human


@dataclass
class Block:
    question: str
    node: str
    raised_by: str
    event_id: str


def check(packet: Path) -> Block | None:
    """The outstanding question, if a human owes one. None means proceed."""
    entry = unresolved_needs_human(read_entries(Path(packet)))
    if entry is None:
        return None
    return Block(
        question=entry.get("question", ""),
        node=entry.get("node", ""),
        raised_by=entry.get("raised_by", "node"),
        event_id=entry.get("event_id", ""),
    )
