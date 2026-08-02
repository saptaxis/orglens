from __future__ import annotations

from pathlib import Path

from orglens.workflow.derive import derive_next_node
from orglens.workflow.result import Outcome

WORKFLOW = {
    "brief": "*-brief.md",
    "artifact": {"family": "draft", "canonical": "draft.md"},
    "terminal": {"published": "brief_published"},
    "nodes": {
        "brief": {
            "mutates": True,
            "guard": {"none": ["brief_exists", "awaiting_mutation"]},
        },
        "draft": {
            "mutates": True,
            "guard": {
                "all": ["brief_exists"],
                "none": ["artifact_exists", "awaiting_mutation"],
            },
        },
        "critique": {
            "diagnoses": True,
            "guard": {
                "all": ["brief_exists", "artifact_exists"],
                "none": [
                    "artifact_noncanonical",
                    "awaiting_mutation",
                    "last_diagnostic_is_critique",
                ],
            },
        },
        "revise": {
            "mutates": True,
            "guard": {"all": ["awaiting_mutation"], "none": ["artifact_noncanonical"]},
        },
        "audit": {
            "diagnoses": True,
            "guard": {
                "all": ["brief_exists", "artifact_exists", "last_diagnostic_is_critique"],
                "none": ["artifact_noncanonical", "awaiting_mutation"],
            },
        },
    },
}


def derive(path: Path):
    return derive_next_node(path, WORKFLOW)


def log(tmp_path: Path, *nodes: str) -> None:
    (tmp_path / "runs.jsonl").write_text(
        "".join(
            '{"type":"node_completed","node":"%s","at":"t","event_id":"%d"}\n' % (n, i)
            for i, n in enumerate(nodes)
        )
    )


def content(tmp_path: Path) -> None:
    (tmp_path / "writing-brief.md").write_text("# Brief")
    (tmp_path / "draft.md").write_text("prose")


# --- the cycle, traced end to end -------------------------------------------

def test_empty_packet_needs_a_brief(tmp_path: Path):
    assert derive(tmp_path).node == "brief"


def test_a_brief_alone_needs_a_draft(tmp_path: Path):
    (tmp_path / "writing-brief.md").write_text("# Brief")
    assert derive(tmp_path).node == "draft"


def test_a_fresh_draft_is_critiqued(tmp_path: Path):
    content(tmp_path)
    log(tmp_path, "brief", "draft")
    assert derive(tmp_path).node == "critique"


def test_a_diagnosis_is_revised(tmp_path: Path):
    content(tmp_path)
    log(tmp_path, "brief", "draft", "critique")
    assert derive(tmp_path).node == "revise"


def test_after_a_critique_cycle_the_next_diagnostic_is_audit(tmp_path: Path):
    content(tmp_path)
    log(tmp_path, "brief", "draft", "critique", "revise")
    assert derive(tmp_path).node == "audit"


def test_an_audit_is_revised(tmp_path: Path):
    content(tmp_path)
    log(tmp_path, "brief", "draft", "critique", "revise", "audit")
    assert derive(tmp_path).node == "revise"


def test_after_an_audit_cycle_the_next_diagnostic_is_critique(tmp_path: Path):
    """The alternation closes. This is the whole cycle in one assertion."""
    content(tmp_path)
    log(tmp_path, "brief", "draft", "critique", "revise", "audit", "revise")
    assert derive(tmp_path).node == "critique"


# --- precedence and failure modes -------------------------------------------

def test_published_is_terminal_and_beats_every_guard(tmp_path: Path):
    (tmp_path / "writing-brief.md").write_text("---\npublished: https://x/y\n---\n")
    (tmp_path / "draft.md").write_text("prose")
    assert derive(tmp_path).outcome == Outcome.TERMINAL


def test_an_unrecognised_layout_is_unknown_not_a_node(tmp_path: Path):
    """What adoption used to be. Nothing is named; a human looks at it."""
    (tmp_path / "writing-brief.md").write_text("# Brief")
    (tmp_path / "draft-v2.md").write_text("prose")
    result = derive(tmp_path)
    assert result.outcome == Outcome.UNKNOWN
    assert result.node is None


def test_a_log_naming_a_file_that_is_not_there_is_malformed(tmp_path: Path):
    content(tmp_path)
    (tmp_path / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"critique","at":"t","event_id":"1",'
        '"wrote":["findings.md"]}\n'
    )
    assert derive(tmp_path).outcome == Outcome.MALFORMED


def test_malformed_is_tested_before_terminal(tmp_path: Path):
    (tmp_path / "writing-brief.md").write_text("---\npublished: https://x/y\n---\n")
    (tmp_path / "draft.md").write_text("prose")
    (tmp_path / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"critique","at":"t","event_id":"1",'
        '"wrote":["gone.md"]}\n'
    )
    assert derive(tmp_path).outcome == Outcome.MALFORMED


def test_two_matching_guards_is_an_error_not_a_tiebreak(tmp_path: Path):
    broken = {
        **WORKFLOW,
        "nodes": {
            "a": {"guard": {"all": ["brief_exists"]}},
            "b": {"guard": {"all": ["brief_exists"]}},
        },
    }
    (tmp_path / "writing-brief.md").write_text("# Brief")
    result = derive_next_node(tmp_path, broken)
    assert result.outcome == Outcome.AMBIGUOUS
    assert sorted(result.matched) == ["a", "b"]


def test_a_log_without_its_files_is_never_ambiguous(tmp_path: Path):
    """A brief deleted mid-loop once matched both `brief` and `revise`.

    Exhaustive simulation over every log permutation to length 6 crossed with
    every file-state found 23436 such collisions; `none: [awaiting_mutation]`
    on the two entry nodes removes all of them without touching the cycle.
    A packet whose log records work its files do not corroborate is not fresh.
    """
    (tmp_path / "draft.md").write_text("prose")
    log(tmp_path, "critique")
    result = derive(tmp_path)
    assert result.outcome != Outcome.AMBIGUOUS


def test_derivation_has_no_opinion_about_humans(tmp_path: Path):
    """An outstanding question does not change what derives. Blocking is
    the orchestrator's question, answered separately."""
    content(tmp_path)
    (tmp_path / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"draft","at":"t","event_id":"1"}\n'
        '{"type":"needs_human","node":"draft","question":"q","at":"t","event_id":"2"}\n'
    )
    assert derive(tmp_path).node == "critique"


def test_the_reason_names_the_facts_that_matched(tmp_path: Path):
    content(tmp_path)
    log(tmp_path, "brief", "draft")
    assert "brief_exists" in derive(tmp_path).reason
