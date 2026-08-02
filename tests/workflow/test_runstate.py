from __future__ import annotations

import json
from pathlib import Path

import pytest

from orglens.workflow.runstate import (
    ENTRY_TYPES,
    append_fact,
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


def test_exactly_four_kinds():
    assert ENTRY_TYPES == frozenset(
        {"node_completed", "resumed_at", "needs_human", "human_resolved"}
    )


def test_only_two_kinds_move_the_cursor():
    from orglens.workflow.runstate import ROUTING_TYPES

    assert ROUTING_TYPES == frozenset({"node_completed", "resumed_at"})


def test_resumed_at_must_name_a_node():
    problems = validate_entry({"type": "resumed_at", "at": "t", "event_id": "e"})
    assert any("node" in p for p in problems)


def test_the_cursor_is_empty_on_a_new_packet():
    from orglens.workflow.runstate import last_routing_node

    assert last_routing_node([]) is None


def test_a_completion_moves_the_cursor():
    from orglens.workflow.runstate import last_routing_node

    entries = [{"type": "node_completed", "node": "draft"}]
    assert last_routing_node(entries) == "draft"


def test_the_most_recent_routing_fact_wins():
    from orglens.workflow.runstate import last_routing_node

    entries = [
        {"type": "node_completed", "node": "draft"},
        {"type": "node_completed", "node": "critique"},
    ]
    assert last_routing_node(entries) == "critique"


def test_a_human_can_move_the_cursor_backwards():
    """goto is how you re-run a stage. It is a fact, not a setting."""
    from orglens.workflow.runstate import last_routing_node

    entries = [
        {"type": "node_completed", "node": "audit"},
        {"type": "resumed_at", "node": "draft", "note": "starting over"},
    ]
    assert last_routing_node(entries) == "draft"


def test_gates_do_not_move_the_cursor():
    from orglens.workflow.runstate import last_routing_node

    entries = [
        {"type": "node_completed", "node": "critique"},
        {"type": "needs_human", "node": "critique", "question": "q"},
        {"type": "human_resolved", "resolves": "x", "note": "ok"},
    ]
    assert last_routing_node(entries) == "critique"


def test_a_resumed_at_round_trips_through_append(tmp_path: Path):
    stamped = append_fact(tmp_path, {"type": "resumed_at", "node": "audit"})
    assert validate_entry(stamped) == []
    assert stamped["node"] == "audit"


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


def test_all_five_present_tense_keys_are_forbidden():
    from orglens.workflow.runstate import FORBIDDEN_KEYS

    assert FORBIDDEN_KEYS == frozenset(
        {"current_state", "status", "pending", "next_node", "state"}
    )
    for key in FORBIDDEN_KEYS:
        assert validate_entry({**OK, key: "x"}), f"{key} was accepted"


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


