"""The outcome of deriving what runs next, and the record of how it was
decided.

Five outcomes cover every packet: one names a node to run, one says the
packet is done, one says the log disagrees with the files on disk, one says
two nodes claimed the same packet at once, and one says the layout does not
match anything the workflow declares. That last one names no node — a
directory the workflow does not recognise is not made to fit; it is simply
not derivable, and something other than this module decides what happens to
it next.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Outcome(str, Enum):
    RUNNABLE = "runnable"
    TERMINAL = "terminal"
    UNKNOWN = "unknown"
    MALFORMED = "malformed"
    AMBIGUOUS = "ambiguous"


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
