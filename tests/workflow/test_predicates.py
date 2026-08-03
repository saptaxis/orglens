from __future__ import annotations

from pathlib import Path

import pytest

from orglens.workflow.predicates import AFTER, EXISTS, NOTHING, evaluate, predicate_names
from orglens.workflow.snapshot import read_packet

WORKFLOW = {
    "terminal": {"done": "exists:PUBLISHED"},
    "nodes": {
        "brief": {"guard": {"all": ["after:nothing"]}},
        "draft": {"guard": {"all": ["after:brief"], "none": ["exists:draft.md"]}},
        "critique": {"guard": {"any": ["after:draft", "after:polish"]}},
        "polish": {"guard": {"all": ["after:critique"]}},
    },
}


def facts(tmp_path: Path) -> dict[str, bool]:
    return evaluate(read_packet(tmp_path), WORKFLOW)


def log(tmp_path: Path, *entries: tuple[str, str]) -> None:
    (tmp_path / "runs.jsonl").write_text(
        "".join(
            '{"type":"%s","node":"%s","at":"t","event_id":"%d"}\n' % (t, n, i)
            for i, (t, n) in enumerate(entries)
        )
    )


def test_the_two_forms_are_declared():
    assert (EXISTS, AFTER, NOTHING) == ("exists:", "after:", "nothing")


def test_the_vocabulary_is_whatever_the_deck_names():
    assert predicate_names(WORKFLOW) == frozenset(
        {
            "exists:PUBLISHED",
            "exists:draft.md",
            "after:nothing",
            "after:brief",
            "after:draft",
            "after:polish",
            "after:critique",
        }
    )


def test_a_deck_with_other_names_gets_other_predicates():
    other = {"nodes": {"deploy": {"guard": {"all": ["exists:*.tf", "after:plan"]}}}}
    assert predicate_names(other) == frozenset({"exists:*.tf", "after:plan"})


def test_every_declared_predicate_is_returned(tmp_path: Path):
    assert set(facts(tmp_path)) == set(predicate_names(WORKFLOW))


def test_exists_matches_by_glob(tmp_path: Path):
    (tmp_path / "draft.md").write_text("x")
    assert facts(tmp_path)["exists:draft.md"] is True
    assert facts(tmp_path)["exists:PUBLISHED"] is False


def test_a_glob_matches_any_name(tmp_path: Path):
    (tmp_path / "notes-2.txt").write_text("x")
    wf = {"nodes": {"n": {"guard": {"all": ["exists:notes-*.txt"]}}}}
    assert evaluate(read_packet(tmp_path), wf)["exists:notes-*.txt"] is True


def test_an_empty_packet_is_after_nothing(tmp_path: Path):
    f = facts(tmp_path)
    assert f["after:nothing"] is True
    assert f["after:brief"] is False


def test_the_cursor_is_the_last_routing_fact(tmp_path: Path):
    log(tmp_path, ("node_completed", "brief"), ("node_completed", "draft"))
    f = facts(tmp_path)
    assert f["after:draft"] is True
    assert f["after:brief"] is False
    assert f["after:nothing"] is False


def test_a_human_move_sets_the_cursor(tmp_path: Path):
    log(tmp_path, ("node_completed", "polish"), ("resumed_at", "brief"))
    assert facts(tmp_path)["after:brief"] is True


def test_exactly_one_after_predicate_is_true(tmp_path: Path):
    log(tmp_path, ("node_completed", "critique"))
    f = facts(tmp_path)
    assert sum(1 for k, v in f.items() if k.startswith(AFTER) and v) == 1


def test_an_unknown_prefix_is_an_error(tmp_path: Path):
    wf = {"nodes": {"n": {"guard": {"all": ["invented:thing"]}}}}
    with pytest.raises(ValueError, match="invented:thing"):
        evaluate(read_packet(tmp_path), wf)
