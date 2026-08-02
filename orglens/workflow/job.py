"""Resolve a node's declaration into a fully-resolved job.

A workflow declares nodes; each node reads references and writes literal
filenames. This module turns a node name into a ``Job``: every path
absolute, every read reference expanded and de-duplicated in first-seen
order, every write a literal filename against the packet — there is
nothing to number, because an artifact and its companion files are each
one canonical file with git as their history.

The brief, the artifact, and the run ledger are the three structural
references (``STRUCTURAL``) the engine resolves by construction. Every
other read reference is either a profile reference resolved against the
deck, or a path — bare or a glob — resolved against the packet, checked
against the deck when the packet does not have it. The engine names no
deck file itself: a node that wants a particular file lists it in
``reads``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from orglens.workflow.profile import load_profile
from orglens.workflow.snapshot import PacketSnapshot, read_packet

STRUCTURAL = ("@brief", "@artifact", "@runstate")


@dataclass
class Job:
    node: str
    role: str | None
    profile: str
    reads: list[str]
    writes: list[str]
    must_not_modify: list[str]
    requires: dict = field(default_factory=dict)
    human_review: bool = False
    expect: str | list[str] | None = None

    def to_dict(self) -> dict:
        return {
            "node": self.node,
            "role": self.role,
            "profile": self.profile,
            "reads": self.reads,
            "writes": self.writes,
            "must_not_modify": self.must_not_modify,
            "requires": self.requires,
            "human_review": self.human_review,
            "expect": self.expect,
        }


def resolve_job(packet: Path, deck: Path, workflow: dict, node: str) -> Job:
    """Resolve ``node`` in ``workflow`` into a ``Job``.

    Both roots are resolved so that every path this emits is absolute.
    Raises ``KeyError`` if ``node`` is not declared.
    """
    packet = Path(packet).resolve()
    deck = Path(deck).resolve()

    nodes = workflow.get("nodes", {})
    if node not in nodes:
        raise KeyError(f"node {node!r} is not declared; known nodes: {sorted(nodes)}")
    declaration = nodes[node]

    snapshot = read_packet(packet, workflow)
    profile_name, profile_config = load_profile(
        packet, workflow, snapshot.brief_frontmatter
    )

    reads: list[str] = []
    for ref in declaration.get("reads", []):
        for resolved in _expand_read(ref, packet, deck, snapshot, profile_config):
            if resolved not in reads:
                reads.append(resolved)

    writes = [str((packet / name).resolve()) for name in declaration.get("writes", [])]

    must_not_modify = _expand_must_not_modify(
        declaration.get("must_not_modify", []), packet, snapshot, writes
    )

    return Job(
        node=node,
        role=_resolve_role(declaration.get("role"), deck),
        profile=profile_name,
        reads=reads,
        writes=writes,
        must_not_modify=must_not_modify,
        requires=declaration.get("requires", {}),
        human_review=declaration.get("human_review", False),
        expect=declaration.get("expect"),
    )


def _resolve_role(role: str | None, deck: Path) -> str | None:
    """A pass with no separate role card yields ``None``; anything else
    names a card relative to the deck.
    """
    if role in (None, "self", "none"):
        return None
    return str((deck / role).resolve())


def _expand_read(
    ref: str,
    packet: Path,
    deck: Path,
    snapshot: PacketSnapshot,
    profile_config: dict,
) -> list[str]:
    """Expand one ``reads`` entry to zero or more absolute paths."""
    if ref == "@brief":
        return [_require(packet, snapshot.brief, "brief")]
    if ref == "@artifact":
        return [_require(packet, snapshot.artifact, "artifact")]
    if ref == "@runstate":
        return [str((packet / "runs.jsonl").resolve())]
    if ref.startswith("@profile."):
        return [_require_profile_path(ref, deck, profile_config)]
    if ref.startswith("@"):
        raise KeyError(f"unknown structural reference: {ref!r}; known: {STRUCTURAL}")
    if _is_glob(ref):
        return _expand_glob(ref, packet, deck)
    return [str(_resolve_bare(ref, packet, deck))]


def _require(packet: Path, name: str | None, label: str) -> str:
    if name is None:
        raise FileNotFoundError(f"packet has no {label}: {packet}")
    return str((packet / name).resolve())


def _require_profile_path(ref: str, deck: Path, profile_config: dict) -> str:
    """Resolve ``@profile.<key>`` against the deck and fail loudly rather
    than hand back a path nobody checked. A value the profile does not
    carry, or a value that does not name a file the deck actually has, is
    a marker defect, and a silent nonexistent path in ``reads`` is how one
    reaches a live run undetected.
    """
    key = ref.split(".", 1)[1]
    if key not in profile_config:
        raise KeyError(
            f"profile has no {key!r}; known keys: {sorted(profile_config)}"
        )
    value = profile_config[key]
    resolved = (deck / value).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(
            f"@profile.{key} = {value!r} resolves to {resolved}, which does "
            f"not exist under deck root {deck}"
        )
    return str(resolved)


def _is_glob(ref: str) -> bool:
    return any(ch in ref for ch in "*?[")


def _resolve_bare(ref: str, packet: Path, deck: Path) -> Path:
    """A bare path is checked against the packet first; if it is not
    there, it is checked against the deck.
    """
    candidate = packet / ref
    if candidate.exists():
        return candidate.resolve()
    return (deck / ref).resolve()


def _expand_glob(pattern: str, packet: Path, deck: Path) -> list[str]:
    """Globs are only ever allowed in ``reads``, never in ``writes``."""
    matches = sorted(str(p.resolve()) for p in packet.glob(pattern) if p.is_file())
    if matches:
        return matches
    return sorted(str(p.resolve()) for p in deck.glob(pattern) if p.is_file())


def _expand_must_not_modify(
    entries: list[str],
    packet: Path,
    snapshot: PacketSnapshot,
    writes: list[str],
) -> list[str]:
    """``["**"]`` expands to every file present in the packet, minus this
    node's declared writes and ``runs.jsonl``. Any other explicit list
    expands to those paths, minus any that are also declared writes.
    """
    writes_set = set(writes)
    runs_path = str((packet / "runs.jsonl").resolve())

    remaining = list(entries)
    candidates: list[str] = []
    if "**" in remaining:
        candidates.extend(
            str((packet / name).resolve())
            for name in snapshot.files
            if str((packet / name).resolve()) != runs_path
        )
        remaining = [entry for entry in remaining if entry != "**"]

    for entry in remaining:
        if _is_glob(entry):
            candidates.extend(
                str(p.resolve()) for p in packet.glob(entry) if p.is_file()
            )
        else:
            candidates.append(str((packet / entry).resolve()))

    result: list[str] = []
    for candidate in candidates:
        if candidate in writes_set:
            continue
        if candidate not in result:
            result.append(candidate)
    return result
