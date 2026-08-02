"""Named predicates over a packet snapshot.

Booleans only, over filenames, frontmatter, and recorded facts. Nothing here
reads a document body — what a round *says* is data for the next node, and the
human's decision reaches the engine as "a human acted", never as parsed prose.

Keep the set small: the exclusivity check in validate.py covers fixtures across
this vocabulary, and every addition widens the space those fixtures cover.
"""

from __future__ import annotations

from orglens.workflow.snapshot import PacketSnapshot

PREDICATE_NAMES = frozenset(
    {
        "brief_exists",
        "brief_published",
        "artifact_exists",
        "artifact_noncanonical",
        "no_rounds",
        "round_open",
        "round_closed",
        "last_round_diagnosed_by_critique",
        "last_round_diagnosed_by_audit",
    }
)

#: Nodes whose completion closes a round. Overridable per deck via
#: `rounds.closed_by`; the default matches the writing deck.
DEFAULT_CLOSED_BY = ("revise",)


def _completed(snapshot: PacketSnapshot, node: str, round_number: int) -> bool:
    return any(
        entry.get("type") == "node_completed"
        and entry.get("node") == node
        and entry.get("round") == round_number
        for entry in snapshot.runs
    )


def evaluate(snapshot: PacketSnapshot, workflow: dict | None = None) -> dict[str, bool]:
    workflow = workflow or {}
    closed_by = tuple(
        workflow.get("rounds", {}).get("closed_by") or DEFAULT_CLOSED_BY
    )

    latest = max(snapshot.rounds) if snapshot.rounds else None

    if latest is None:
        closed = False
        open_round = False
    else:
        closed = any(_completed(snapshot, node, latest) for node in closed_by)
        open_round = not closed

    return {
        "brief_exists": snapshot.brief is not None,
        "brief_published": bool(snapshot.brief_frontmatter.get("published")),
        "artifact_exists": snapshot.artifact is not None,
        "artifact_noncanonical": snapshot.artifact is not None
        and not snapshot.artifact_canonical,
        "no_rounds": latest is None,
        "round_open": open_round,
        "round_closed": latest is not None and closed,
        "last_round_diagnosed_by_critique": latest is not None
        and _completed(snapshot, "critique", latest),
        "last_round_diagnosed_by_audit": latest is not None
        and _completed(snapshot, "audit", latest),
    }
