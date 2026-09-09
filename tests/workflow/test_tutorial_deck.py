"""The tutorial deck, and the claims its DECK.md makes.

This deck is the only witness that the engine is generic. The writing deck
cannot prove it — the engine was grown alongside it, so a domain assumption
would be invisible from inside. A bug-triage loop sharing zero vocabulary with
an essay is the check.

The DECK.md walkthrough is a promise to whoever runs it. These tests hold it to
that promise, because a tutorial that lies is worse than no tutorial.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from orglens.workflow.definition import load_workflow
from orglens.workflow.derive import derive_next_node
from orglens.workflow.job import resolve_job
from orglens.workflow.result import Outcome
from orglens.workflow.validate import validate_definition

DECK = Path(__file__).resolve().parents[2] / "capabilities" / "decks" / "tutorial"
WORKFLOW_PATH = DECK / "WORKFLOW.yaml"


@pytest.fixture
def workflow() -> dict:
    return load_workflow(WORKFLOW_PATH)


def packet(tmp_path: Path, cursor: str | None = None, **files: str) -> Path:
    (tmp_path / "report.md").write_text("a bug")
    for name, body in files.items():
        (tmp_path / name.replace("__", ".")).write_text(body)
    if cursor:
        (tmp_path / "runs.jsonl").write_text(
            '{"type":"node_completed","node":"%s","at":"t","event_id":"1"}\n' % cursor
        )
    return tmp_path


def test_the_shipped_definition_validates(workflow):
    assert validate_definition(workflow) == []


#: The writing deck's node names, recorded here rather than loaded. That deck
#: moved to `orglens-extras`, and the claim below is about words, not files —
#: a literal keeps the proof in this repo instead of making it depend on one
#: the reader may not have. Update it if that deck's vocabulary changes.
ANOTHER_DECKS_VOCABULARY = {"audit", "brief", "critique", "draft", "polish", "revise"}


def test_the_deck_shares_no_vocabulary_with_another_deck(workflow):
    """The point of this deck. If these overlap it proves nothing."""
    assert set(workflow["nodes"]) & ANOTHER_DECKS_VOCABULARY == set()


@pytest.mark.parametrize(
    "cursor,expected",
    [
        (None, "reproduce"),
        ("reproduce", "fix"),
        ("fix", "verify"),
        ("verify", "reproduce"),  # the loop-back edge
    ],
)
def test_the_loop_walks_and_closes(tmp_path: Path, workflow, cursor, expected):
    result = derive_next_node(packet(tmp_path, cursor), workflow)
    assert result.outcome == Outcome.RUNNABLE
    assert result.node == expected


def test_exactly_one_node_matches_at_every_cursor(tmp_path: Path, workflow):
    for cursor in [None, *workflow["nodes"]]:
        result = derive_next_node(packet(tmp_path, cursor), workflow)
        assert result.outcome == Outcome.RUNNABLE, (cursor, result.reason)


def test_a_closed_packet_is_terminal_whatever_the_cursor(tmp_path: Path, workflow):
    """DECK.md §6, and the correction in 'Try changing it'."""
    root = packet(tmp_path, "fix")
    (root / "CLOSED").write_text("")
    assert derive_next_node(root, workflow).outcome == Outcome.TERMINAL


def test_deleting_the_log_returns_to_the_entry_node(tmp_path: Path, workflow):
    """DECK.md 'Try changing it' — only true once CLOSED is gone too."""
    root = packet(tmp_path, "fix")
    (root / "runs.jsonl").unlink()
    assert derive_next_node(root, workflow).node == "reproduce"


def test_a_read_that_matches_nothing_is_reported_not_fatal(tmp_path: Path, workflow):
    """DECK.md §2 promises `verdict.md (no match)` on the first round."""
    job = resolve_job(packet(tmp_path), DECK, workflow, "reproduce")
    assert "verdict.md" in job.unmatched
    assert any(p.endswith("report.md") for p in job.reads)


def test_every_role_the_deck_names_exists(tmp_path: Path, workflow):
    for name in workflow["nodes"]:
        job = resolve_job(packet(tmp_path), DECK, workflow, name)
        assert job.role is not None and Path(job.role).is_file(), name


def test_the_gate_is_declared_where_the_tutorial_says(workflow):
    """DECK.md §4."""
    assert workflow["nodes"]["fix"].get("human_review") is True
    assert not workflow["nodes"]["reproduce"].get("human_review")


def test_two_nodes_claiming_one_cursor_is_caught_statically(workflow):
    """DECK.md 'Try changing it', first bullet — the exact edit it suggests."""
    broken = copy.deepcopy(workflow)
    broken["nodes"]["verify"]["guard"] = {"all": ["after:reproduce"]}
    problems = validate_definition(broken)
    assert any("fix" in p and "verify" in p and "after:reproduce" in p for p in problems)


def test_the_tutorial_only_shows_commands_that_exist():
    """A walkthrough that names a verb the CLI lacks is a broken tutorial."""
    import re

    from orglens.workflow.cli import workflow as workflow_group

    verbs = set(workflow_group.commands)
    shown = set(re.findall(r"orglens workflow (\w+)", (DECK / "DECK.md").read_text()))
    assert shown <= verbs, f"DECK.md names verbs that do not exist: {shown - verbs}"
