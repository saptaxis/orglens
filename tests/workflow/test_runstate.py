from __future__ import annotations

from pathlib import Path

from orglens.workflow.runstate import (
    ENTRY_TYPES,
    completed,
    read_entries,
    unresolved_needs_human,
    validate_entry,
)

OK = {
    "type": "node_completed",
    "at": "2026-08-02T09:14:02+05:30",
    "event_id": "e1",
    "workflow_version": "sha256:1a4f",
    "node": "critique",
}


def test_the_four_entry_types_are_declared():
    assert ENTRY_TYPES == frozenset(
        {"node_completed", "needs_human", "human_resolved", "postcondition_failed"}
    )


def test_a_well_formed_entry_has_no_problems():
    assert validate_entry(OK) == []


def test_missing_mandatory_keys_are_reported():
    problems = validate_entry({"type": "node_completed"})
    assert any("at" in p for p in problems)
    assert any("event_id" in p for p in problems)


def test_an_unknown_type_is_reported():
    problems = validate_entry({**OK, "type": "invented"})
    assert any("invented" in p for p in problems)


def test_a_present_tense_projection_is_reported():
    """Past facts belong; projections of the present do not."""
    problems = validate_entry({**OK, "current_state": "waiting"})
    assert any("current_state" in p for p in problems)


def test_human_resolved_must_name_what_it_resolves():
    problems = validate_entry(
        {"type": "human_resolved", "at": "t", "event_id": "e2", "note": "ok"}
    )
    assert any("resolves" in p for p in problems)


def test_reads_entries_in_order(tmp_path: Path):
    (tmp_path / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"a","at":"t","event_id":"1"}\n'
        '{"type":"node_completed","node":"b","at":"t","event_id":"2"}\n'
    )
    assert [e["node"] for e in read_entries(tmp_path)] == ["a", "b"]


def test_missing_run_state_is_empty_not_an_error(tmp_path: Path):
    assert read_entries(tmp_path) == []


def test_finds_an_unresolved_needs_human():
    entries = [
        {"type": "needs_human", "event_id": "n1", "question": "does X count?"},
    ]
    assert unresolved_needs_human(entries)["event_id"] == "n1"


def test_a_resolved_needs_human_is_not_outstanding():
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


def test_completed_reads_node_and_round():
    entries = [
        {"type": "node_completed", "node": "critique", "round": 1},
        {"type": "needs_human", "node": "critique"},
    ]
    assert completed(entries, "critique", 1) is True
    assert completed(entries, "revise", 1) is False
    assert completed(entries, "critique") is True
