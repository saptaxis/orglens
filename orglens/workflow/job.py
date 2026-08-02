"""A job — a node with everything resolved.

Derivation returns a node name. A runtime handed only that has to infer which
file is the brief, what {next} means, and where the role lives. Every inference
is a place to be wrong, so the job resolves all of them first.

The rule: computation belongs where the state is. {next} resolves here, in the
only place that knows the round. The agent receives answers, never expressions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from orglens.workflow.profile import load_profile
from orglens.workflow.snapshot import read_packet

#: The closed set of structural references. Closed because the guards already
#: depend on these identifications — without them there is no routing.
STRUCTURAL = ("@brief", "@artifact", "@rounds", "@adoption", "@runstate")


@dataclass
class Job:
    node: str
    role: str | None = None
    profile: str = ""
    reads: list[str] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)
    must_not_modify: list[str] = field(default_factory=list)
    requires: dict = field(default_factory=dict)
    human_review: bool = False
    expect: str | None = None

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


def _next_round(snapshot) -> int:
    return (max(snapshot.rounds) + 1) if snapshot.rounds else 1


def _round_files(packet: Path, workflow: dict) -> list[str]:
    from orglens.workflow.snapshot import _round_pattern

    pattern = _round_pattern(workflow)
    return [p.name for p in packet.iterdir() if p.is_file() and pattern.fullmatch(p.name)]


def _resolve_read(
    ref: str, packet: Path, deck: Path, snapshot, profile_config: dict,
    workflow: dict
) -> list[str]:
    if ref == "@brief":
        return [str(packet / snapshot.brief)] if snapshot.brief else []
    if ref == "@artifact":
        return [str(packet / snapshot.artifact)] if snapshot.artifact else []
    if ref == "@runstate":
        return [str(packet / "runs.jsonl")]
    if ref == "@rounds":
        # the declared round records only — not "everything else", which swept
        # up adoption.md, stray drafts, and the run log
        return sorted(str(packet / name) for name in _round_files(packet, workflow))
    if ref == "@adoption":
        target = packet / "adoption.md"
        return [str(target)] if target.exists() else []
    if ref.startswith("@profile."):
        key = ref.split(".", 1)[1]
        value = profile_config.get(key)
        return [str(deck / value)] if value else []
    if any(ch in ref for ch in "*?["):
        return sorted(str(p) for p in packet.glob(ref))
    candidate = packet / ref
    if not candidate.exists():
        candidate = deck / ref
    return [str(candidate)]


def resolve_job(packet: Path, deck: Path, workflow: dict, node: str) -> Job:
    packet, deck = Path(packet).resolve(), Path(deck).resolve()
    spec = workflow.get("nodes", {}).get(node)
    if spec is None:
        raise KeyError(f"no node {node!r} in this workflow")

    snapshot = read_packet(packet, workflow)
    profile_name, profile_config = load_profile(
        packet, workflow, snapshot.brief_frontmatter
    )

    reads: list[str] = []
    for ref in spec.get("reads") or []:
        for path in _resolve_read(
            ref, packet, deck, snapshot, profile_config, workflow
        ):
            if path not in reads:          # a file named twice is read once
                reads.append(path)

    next_round = _next_round(snapshot)
    writes = [
        str(packet / w.replace("{next}", f"{next_round:02d}"))
        for w in (spec.get("writes") or [])
    ]

    protected = spec.get("must_not_modify") or []
    written = {Path(w).name for w in writes}
    if "**" in protected:
        must_not_modify = [
            str(packet / name)
            for name in snapshot.files
            if name not in written and name != "runs.jsonl"
        ]
    else:
        must_not_modify = [
            str(packet / p) for p in protected if Path(p).name not in written
        ]

    role = spec.get("role")
    return Job(
        node=node,
        role=str(deck / role) if role and role not in ("self", "none") else None,
        profile=profile_name,
        reads=reads,
        writes=writes,
        must_not_modify=sorted(must_not_modify),
        requires=spec.get("requires") or {},
        human_review=bool(spec.get("human_review")),
        expect=spec.get("expect"),
    )
