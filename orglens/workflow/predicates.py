"""Named predicates over a packet snapshot.

Guards are combinations of these. Keep the set small: the exclusivity check
in validate.py covers fixtures across this vocabulary, and every addition
widens the space those fixtures must cover.
"""

from __future__ import annotations

from orglens.workflow.snapshot import PacketSnapshot, RoundInfo

PREDICATE_NAMES = frozenset(
    {
        "brief_exists",
        "brief_published",
        "artifact_exists",
        "no_rounds",
        "open_round",
        "no_open_round",
        "round_unresolved",
        "round_actionable",
        "adoption_unresolved",
        "last_round_critiqued",
        "last_round_audited",
    }
)


def _ran(snapshot: PacketSnapshot, node: str, round_number: int) -> bool:
    return any(
        r.get("type") == "node_completed"
        and r.get("node") == node
        and r.get("round") == round_number
        for r in snapshot.runs
    )


def _unresolved(round_info: RoundInfo) -> bool:
    return bool(round_info.sections.get("Proposed"))


def _actionable(round_info: RoundInfo) -> bool:
    return bool(
        round_info.sections.get("Accept") or round_info.sections.get("Modify")
    )


def _closed(snapshot: PacketSnapshot, round_info: RoundInfo) -> bool:
    """A round closes when there is nothing left to do to it.

    Either a mutating pass applied it, or it resolved with nothing to apply
    (reject-only). The second clause is what stops a fully-rejected round
    wedging the packet.
    """
    if _unresolved(round_info):
        return False
    if _ran(snapshot, "revise", round_info.number):
        return True
    return not _actionable(round_info)


def evaluate(snapshot: PacketSnapshot) -> dict[str, bool]:
    latest = max(snapshot.rounds) if snapshot.rounds else None
    round_info = snapshot.rounds[latest] if latest is not None else None

    if round_info is None:
        open_round = False
        unresolved = False
        actionable = False
    else:
        open_round = not _closed(snapshot, round_info)
        unresolved = _unresolved(round_info)
        actionable = open_round and _actionable(round_info)

    adoption_unresolved = bool(
        snapshot.adoption and snapshot.adoption.sections.get("Proposed")
    )

    return {
        "brief_exists": snapshot.brief is not None,
        "brief_published": bool(snapshot.brief_frontmatter.get("published")),
        "artifact_exists": snapshot.artifact is not None,
        "no_rounds": latest is None,
        "open_round": open_round,
        "no_open_round": not open_round,
        "round_unresolved": unresolved,
        "round_actionable": actionable,
        "adoption_unresolved": adoption_unresolved,
        "last_round_critiqued": latest is not None
        and _ran(snapshot, "critique", latest),
        "last_round_audited": latest is not None and _ran(snapshot, "audit", latest),
    }
