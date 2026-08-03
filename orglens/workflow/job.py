"""Files in, files out.

A job turns "node X is next" into a concrete assignment: which role card
drives the pass, which files it reads, which files it writes. The engine
does not open any of these paths — it only names them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

_NO_ROLE = {"self", "none"}


@dataclass
class Job:
    node: str
    role: str | None
    reads: list[str]
    writes: list[str]
    requires: dict
    human_review: bool
    unmatched: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "node": self.node,
            "role": self.role,
            "reads": list(self.reads),
            "writes": list(self.writes),
            "requires": dict(self.requires),
            "human_review": self.human_review,
            "unmatched": list(self.unmatched),
        }


def _resolve_reads(packet: Path, globs: list[str]) -> tuple[list[str], list[str]]:
    reads: list[str] = []
    unmatched: list[str] = []
    seen: set[str] = set()
    for pattern in globs:
        matches = sorted(str(p.resolve()) for p in packet.glob(pattern))
        if not matches:
            unmatched.append(pattern)
            continue
        for match in matches:
            if match not in seen:
                seen.add(match)
                reads.append(match)
    return reads, unmatched


def _resolve_writes(packet: Path, names: list[str]) -> list[str]:
    return [str((packet / name).resolve()) for name in names]


def _resolve_role(role: str | None, deck: Path, roots: list[str]) -> str | None:
    if role is None or role in _NO_ROLE:
        return None

    tried: list[str] = []
    for root in roots:
        base = (deck / root).resolve()
        candidate = base / role
        tried.append(str(candidate))
        if candidate.is_file():
            return str(candidate)

    raise FileNotFoundError(
        f"role {role!r} not found under any root {roots!r} (deck {deck}); tried: "
        + ", ".join(tried)
    )


def resolve_job(packet: Path, deck: Path, workflow: dict, node: str) -> Job:
    packet = Path(packet).resolve()
    deck = Path(deck).resolve()

    nodes = workflow.get("nodes", {})
    if node not in nodes:
        raise KeyError(node)
    declaration = nodes[node]

    roots = workflow.get("roots", ["."])
    role = _resolve_role(declaration.get("role"), deck, roots)

    reads, unmatched = _resolve_reads(packet, declaration.get("reads", []))
    writes = _resolve_writes(packet, declaration.get("writes", []))

    return Job(
        node=node,
        role=role,
        reads=reads,
        writes=writes,
        requires=declaration.get("requires", {}),
        human_review=declaration.get("human_review", False),
        unmatched=unmatched,
    )
