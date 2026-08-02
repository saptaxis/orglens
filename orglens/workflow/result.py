"""The four shapes derivation can answer with, and nothing else.

A derivation either names exactly one node to run, names none because a
terminal value already holds, names none because more than one node's guard
matched, or names none because nothing matched at all. Those four shapes are
closed: :class:`Outcome` has no fifth member, and no member here is a
permanent verdict about the packet — every one of them is recomputed fresh
from the packet's current shape each time derivation runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Outcome(StrEnum):
    RUNNABLE = "runnable"
    TERMINAL = "terminal"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


@dataclass
class DerivationResult:
    outcome: Outcome
    node: str | None
    reason: str
    matched: list[str] = field(default_factory=list)
    facts: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "outcome": self.outcome.value,
            "node": self.node,
            "reason": self.reason,
            "matched": list(self.matched),
            "facts": dict(self.facts),
        }
