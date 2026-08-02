"""The model's vocabulary is closed. This test is why.

workflow.md carries a `Deliberately absent` list. Every concept on it was added
for a real reason, outlived that reason, and survived a cleanup because it had
no domain nouns in it. Prose did not stop that happening three times. This does.

Adding a concept now means editing an enumeration here, which is visible in a
diff and has to be argued for.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parents[2] / "orglens" / "workflow"

#: workflow.md, "Deliberately absent". A hit in the deck-agnostic engine is a
#: concept the model does not have.
#: Removed CONCEPTS only. Present-tense run-state keys are pinned by an
#: equality assertion below instead: run state has to name them in order to
#: reject them, and `next_node` as a substring also matches the model's own
#: `derive_next_node`. A ban that forbids naming the thing you are rejecting
#: deletes the safety check rather than the concept.
BANNED = (
    "round",
    "disposition",
    "adopt",
    "fallback",
    "proposed",
    "decisions",
)


def engine_sources() -> list[Path]:
    return sorted(p for p in ENGINE.glob("*.py") if p.name != "__init__.py")


@pytest.mark.parametrize("word", BANNED)
def test_no_absent_concept_appears_in_the_engine(word: str):
    hits = []
    for path in engine_sources():
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if re.search(word, line, re.IGNORECASE):
                hits.append(f"{path.name}:{number}: {line.strip()}")
    assert not hits, (
        f"{word!r} is on workflow.md's deliberately-absent list:\n" + "\n".join(hits)
    )


def test_the_outcome_enum_is_exactly_the_model():
    from orglens.workflow.result import Outcome

    assert {o.value for o in Outcome} == {
        "runnable",
        "terminal",
        "ambiguous",
        "malformed",
        "unknown",
    }


def test_run_state_declares_exactly_three_kinds():
    from orglens.workflow.runstate import ENTRY_TYPES

    assert ENTRY_TYPES == frozenset(
        {"node_completed", "needs_human", "human_resolved"}
    )


def test_the_static_predicate_set_is_exactly_four():
    """Two more are generated per deck. These four are all the engine knows."""
    from orglens.workflow.predicates import STATIC_PREDICATES

    assert STATIC_PREDICATES == frozenset(
        {
            "brief_exists",
            "brief_published",
            "artifact_exists",
            "artifact_noncanonical",
        }
    )


def test_run_state_forbids_exactly_the_present_tense_keys():
    """Pinned by equality, not by a substring ban — see BANNED's note."""
    from orglens.workflow.runstate import FORBIDDEN_KEYS

    assert FORBIDDEN_KEYS == frozenset(
        {"current_state", "status", "pending", "next_node", "state"}
    )


def test_the_engine_names_no_file_from_any_deck():
    """job.py once resolved @adoption to the literal string "adoption.md"."""
    allowed = {"runs.jsonl"}
    for path in engine_sources():
        for literal in re.findall(r"[\"']([\w./-]+\.(?:md|ya?ml))[\"']", path.read_text()):
            assert literal in allowed, f"{path.name} names a deck file: {literal}"
