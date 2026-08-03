from __future__ import annotations

from pathlib import Path

from orglens.workflow.derive import derive_next_node
from orglens.workflow.result import Outcome

WORKFLOW = {
    "terminal": {"published": "exists:PUBLISHED"},
    "nodes": {
        "brief": {"guard": {"all": ["after:nothing"]}},
        "draft": {"guard": {"all": ["after:brief"]}},
        "critique": {"guard": {"any": ["after:draft", "after:polish"]}},
        "revise": {"guard": {"all": ["after:critique"]}},
        "audit": {"guard": {"all": ["after:revise"]}},
        "polish": {"guard": {"all": ["after:audit"]}},
    },
}


def log(tmp_path: Path, *nodes: str) -> None:
    (tmp_path / "runs.jsonl").write_text(
        "".join(
            '{"type":"node_completed","node":"%s","at":"t","event_id":"%d"}\n' % (n, i)
            for i, n in enumerate(nodes)
        )
    )


def derive(p: Path):
    return derive_next_node(p, WORKFLOW)


def test_four_outcomes_only():
    assert {o.value for o in Outcome} == {
        "runnable",
        "terminal",
        "ambiguous",
        "unknown",
    }


def test_an_empty_packet_starts_at_the_entry_node(tmp_path: Path):
    r = derive(tmp_path)
    assert r.outcome == Outcome.RUNNABLE and r.node == "brief"


def test_the_pipeline_walks(tmp_path: Path):
    for done, expected in [
        (("brief",), "draft"),
        (("brief", "draft"), "critique"),
        (("brief", "draft", "critique"), "revise"),
        (("brief", "draft", "critique", "revise"), "audit"),
        (("brief", "draft", "critique", "revise", "audit"), "polish"),
    ]:
        log(tmp_path, *done)
        assert derive(tmp_path).node == expected, done


def test_the_pipeline_loops_in_place(tmp_path: Path):
    """A second round over the same directory. No files are cleared."""
    log(tmp_path, "brief", "draft", "critique", "revise", "audit", "polish")
    assert derive(tmp_path).node == "critique"


def test_a_human_move_reroutes(tmp_path: Path):
    (tmp_path / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"polish","at":"t","event_id":"1"}\n'
        '{"type":"resumed_at","node":"revise","note":"redo","at":"t","event_id":"2"}\n'
    )
    assert derive(tmp_path).node == "audit"


def test_terminal_beats_every_guard(tmp_path: Path):
    (tmp_path / "PUBLISHED").write_text("")
    log(tmp_path, "brief")
    assert derive(tmp_path).outcome == Outcome.TERMINAL


def test_an_unrecognised_cursor_is_unknown(tmp_path: Path):
    log(tmp_path, "a-node-this-workflow-does-not-declare")
    r = derive(tmp_path)
    assert r.outcome == Outcome.UNKNOWN and r.node is None


def test_unknown_reports_which_entries_failed(tmp_path: Path):
    """The glob report where it matters most."""
    log(tmp_path, "a-node-this-workflow-does-not-declare")
    reason = derive(tmp_path).reason
    assert "critique" in reason
    assert "after:draft" in reason
    assert "False" in reason


def test_two_matching_guards_is_an_error_not_a_tiebreak(tmp_path: Path):
    broken = {
        "nodes": {
            "a": {"guard": {"all": ["after:nothing"]}},
            "b": {"guard": {"all": ["after:nothing"]}},
        }
    }
    r = derive_next_node(tmp_path, broken)
    assert r.outcome == Outcome.AMBIGUOUS
    assert sorted(r.matched) == ["a", "b"]


def test_derivation_has_no_opinion_about_humans(tmp_path: Path):
    (tmp_path / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"brief","at":"t","event_id":"1"}\n'
        '{"type":"needs_human","node":"brief","question":"q","at":"t","event_id":"2"}\n'
    )
    assert derive(tmp_path).node == "draft"


def test_no_integrity_outcome_survives():
    assert not hasattr(Outcome, "MALFORMED")


# --- fix round 1: a `none` clause must name its blocking entry too ---------


def test_unknown_names_a_none_clause_entry_that_blocked_it(tmp_path: Path):
    """A `none` clause blocks when its entry is true — the opposite test
    from `all`/`any`. The reason must still name it, with its true value."""
    workflow = {
        "nodes": {
            "revise": {
                "guard": {
                    "all": ["after:critique"],
                    "none": ["exists:LOCK"],
                }
            }
        }
    }
    (tmp_path / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"critique","at":"t","event_id":"1"}\n'
    )
    (tmp_path / "LOCK").write_text("")
    r = derive_next_node(tmp_path, workflow)
    assert r.outcome == Outcome.UNKNOWN
    assert "exists:LOCK=True" in r.reason


def test_an_entry_named_by_two_clauses_prints_once(tmp_path: Path):
    """An entry that blocks via more than one clause of the same guard is
    named once in the reason, not once per clause."""
    workflow = {
        "nodes": {
            "x": {
                "guard": {
                    "all": ["exists:GATE"],
                    "any": ["exists:GATE", "exists:OTHER"],
                }
            }
        }
    }
    r = derive_next_node(tmp_path, workflow)
    assert r.outcome == Outcome.UNKNOWN
    assert r.reason.count("exists:GATE=") == 1
