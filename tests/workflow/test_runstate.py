from __future__ import annotations

import json
from pathlib import Path

import pytest

from orglens.workflow.runstate import (
    ENTRY_TYPES,
    append_fact,
    last_completed,
    read_entries,
    unresolved_needs_human,
    validate_entry,
)

OK = {
    "type": "node_completed",
    "at": "2026-08-02T09:14:02+05:30",
    "event_id": "e1",
    "node": "critique",
}


def test_exactly_three_kinds():
    assert ENTRY_TYPES == frozenset(
        {"node_completed", "needs_human", "human_resolved"}
    )


def test_a_well_formed_entry_has_no_problems():
    assert validate_entry(OK) == []


def test_missing_mandatory_keys_are_reported():
    problems = validate_entry({"type": "node_completed", "node": "x"})
    assert any("at" in p for p in problems)
    assert any("event_id" in p for p in problems)


def test_an_unknown_type_is_reported():
    assert any("invented" in p for p in validate_entry({**OK, "type": "invented"}))


def test_a_present_tense_projection_is_reported():
    assert any("status" in p for p in validate_entry({**OK, "status": "waiting"}))


def test_human_resolved_must_name_what_it_resolves():
    problems = validate_entry(
        {"type": "human_resolved", "at": "t", "event_id": "e2", "note": "ok"}
    )
    assert any("resolves" in p for p in problems)


def test_append_stamps_the_mandatory_keys(tmp_path: Path):
    """The writer's output is valid by construction — no second schema."""
    stamped = append_fact(tmp_path, {"type": "node_completed", "node": "draft"})
    assert validate_entry(stamped) == []
    assert stamped["event_id"] and stamped["at"]
    on_disk = json.loads((tmp_path / "runs.jsonl").read_text().strip())
    assert on_disk == stamped


def test_append_refuses_an_invalid_fact(tmp_path: Path):
    with pytest.raises(ValueError, match="question"):
        append_fact(tmp_path, {"type": "needs_human", "node": "critique"})


def test_append_refuses_a_present_tense_key(tmp_path: Path):
    with pytest.raises(ValueError, match="next_node"):
        append_fact(tmp_path, {"type": "node_completed", "node": "a", "next_node": "b"})


def test_append_never_rewrites(tmp_path: Path):
    append_fact(tmp_path, {"type": "node_completed", "node": "a"})
    append_fact(tmp_path, {"type": "node_completed", "node": "b"})
    assert [e["node"] for e in read_entries(tmp_path)] == ["a", "b"]


def test_missing_run_state_is_empty_not_an_error(tmp_path: Path):
    assert read_entries(tmp_path) == []


def test_finds_an_unresolved_needs_human():
    entries = [{"type": "needs_human", "event_id": "n1", "question": "does X count?"}]
    assert unresolved_needs_human(entries)["event_id"] == "n1"


def test_a_resolved_question_is_not_outstanding():
    entries = [
        {"type": "needs_human", "event_id": "n1", "question": "q"},
        {"type": "human_resolved", "event_id": "r1", "resolves": "n1", "note": "yes"},
    ]
    assert unresolved_needs_human(entries) is None


def test_the_most_recent_unresolved_wins():
    entries = [
        {"type": "needs_human", "event_id": "n1", "question": "first"},
        {"type": "human_resolved", "event_id": "r1", "resolves": "n1", "note": "ok"},
        {"type": "needs_human", "event_id": "n2", "question": "second"},
    ]
    assert unresolved_needs_human(entries)["question"] == "second"


def test_last_completed_picks_the_most_recent_of_a_set():
    entries = [
        {"type": "node_completed", "node": "critique"},
        {"type": "node_completed", "node": "revise"},
        {"type": "node_completed", "node": "audit"},
    ]
    assert last_completed(entries, {"critique", "audit"}) == "audit"
    assert last_completed(entries, {"revise"}) == "revise"
    assert last_completed(entries, {"brief"}) is None


def test_last_completed_ignores_other_kinds():
    entries = [
        {"type": "node_completed", "node": "critique"},
        {"type": "needs_human", "node": "revise", "question": "q"},
    ]
    assert last_completed(entries, {"critique", "revise"}) == "critique"
