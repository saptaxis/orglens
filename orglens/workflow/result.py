"""The classified outcome of a derivation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Outcome(StrEnum):
    RUNNABLE = "runnable"
    TERMINAL = "terminal"
    AMBIGUOUS = "ambiguous"
    MALFORMED = "malformed"
    ADOPTABLE = "adoptable"
    UNKNOWN = "unknown"


@dataclass
class DerivationResult:
    outcome: Outcome
    node: str | None = None
    reason: str = ""
    matched: list[str] = field(default_factory=list)
    facts: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "outcome": str(self.outcome),
            "node": self.node,
            "reason": self.reason,
            "matched": self.matched,
            "facts": self.facts,
        }
