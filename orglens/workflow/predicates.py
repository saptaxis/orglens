"""Facts about a packet, answered from a snapshot and the deck alone.

Artifacts are one canonical file with git as their history, so the only
questions worth asking of the run log are sequence questions: has a
diagnosing node completed since the last mutating one (``awaiting_mutation``),
and which one it was (``last_diagnostic_is_{node}``). The deck says which of
its nodes mutate the artifact and which diagnose it; this module never
learns a node's name of its own, and generates the sequence predicates
fresh from whatever the deck declares.
"""

from __future__ import annotations

from orglens.workflow.runstate import last_completed
from orglens.workflow.snapshot import PacketSnapshot

STATIC_PREDICATES: frozenset[str] = frozenset(
    {
        "brief_exists",
        "brief_published",
        "artifact_exists",
        "artifact_noncanonical",
    }
)


def _nodes_with(workflow: dict, flag: str) -> set[str]:
    """Names of the nodes the deck declares with ``flag: true``. A node
    whose value is not a dict declares nothing and is skipped rather than
    raising — reporting that shape as a problem is `validate_definition`'s
    job, not this one's.
    """
    nodes = workflow.get("nodes") or {}
    return {
        name
        for name, spec in nodes.items()
        if isinstance(spec, dict) and spec.get(flag)
    }


def predicate_names(workflow: dict) -> frozenset[str]:
    """The complete predicate vocabulary for ``workflow``: the static four
    plus ``awaiting_mutation`` plus one ``last_diagnostic_is_{node}`` per
    diagnosing node the deck declares.
    """
    diagnosing = _nodes_with(workflow, "diagnoses")
    generated = {"awaiting_mutation"} | {
        f"last_diagnostic_is_{node}" for node in diagnosing
    }
    return STATIC_PREDICATES | generated


def evaluate(snapshot: PacketSnapshot, workflow: dict) -> dict[str, bool]:
    """Evaluate every predicate ``predicate_names(workflow)`` names against
    ``snapshot``. Requires ``workflow`` because the sequence predicates
    cannot be generated without the node declarations.
    """
    mutating = _nodes_with(workflow, "mutates")
    diagnosing = _nodes_with(workflow, "diagnoses")

    # The most recently completed node among either role settles which role
    # is "more recent" without ever comparing timestamps: `last_completed`
    # scans the log from the end, so whichever role it lands on first is
    # the one that happened last.
    last_of_either = last_completed(snapshot.runs, mutating | diagnosing)
    last_diagnostic = last_completed(snapshot.runs, diagnosing)
    awaiting_mutation = last_of_either is not None and last_of_either in diagnosing

    facts: dict[str, bool] = {
        "brief_exists": snapshot.brief is not None,
        "brief_published": bool(snapshot.brief_frontmatter.get("published")),
        "artifact_exists": snapshot.artifact is not None,
        "artifact_noncanonical": snapshot.artifact is not None
        and not snapshot.artifact_canonical,
        "awaiting_mutation": awaiting_mutation,
    }
    for node in diagnosing:
        facts[f"last_diagnostic_is_{node}"] = last_diagnostic == node

    return facts
