from __future__ import annotations

from pathlib import Path

from orglens.workflow.derive import derive_next_node
from orglens.workflow.result import Outcome

WORKFLOW = {
    "artifact": {"family": "draft", "canonical": "draft.md", "history": "git"},
    "rounds": {"record": "decisions-{NN}.md", "closed_by": ["revise"]},
    "terminal": {"published": "brief_published"},
    "malformed": [
        "log_names_missing_file",
        "round_both_critiqued_and_audited",
        "rounds_without_artifact",
        "round_number_gap",
    ],
    "nodes": {
        "adopt": {"guard": "fallback"},
        "brief": {"guard": {"none": ["brief_exists"]}},
        "draft": {"guard": {"all": ["brief_exists"], "none": ["artifact_exists"]}},
        "critique": {
            "guard": {
                "all": ["brief_exists", "artifact_exists"],
                "any": ["no_rounds", "round_closed"],
                "none": ["artifact_noncanonical", "last_round_diagnosed_by_critique"],
            }
        },
        "revise": {"guard": {"all": ["round_open"], "none": ["artifact_noncanonical"]}},
        "audit": {
            "guard": {
                "all": [
                    "brief_exists",
                    "artifact_exists",
                    "round_closed",
                    "last_round_diagnosed_by_critique",
                ],
                "none": ["artifact_noncanonical"],
            }
        },
    },
}


import copy

WORKFLOW_NONCANON = copy.deepcopy(WORKFLOW)
for _n in ("critique", "revise", "audit"):
    WORKFLOW_NONCANON["nodes"][_n]["guard"]["none"] = ["artifact_noncanonical"]


def derive(tmp_path: Path):
    return derive_next_node(tmp_path, WORKFLOW)


def test_empty_packet_routes_to_brief(tmp_path: Path):
    r = derive(tmp_path)
    assert r.outcome == Outcome.RUNNABLE
    assert r.node == "brief"


def test_brief_without_artifact_routes_to_draft(tmp_path: Path):
    (tmp_path / "writing-brief.md").write_text("# Brief")
    r = derive(tmp_path)
    assert r.node == "draft"


def test_draft_without_rounds_routes_to_critique(tmp_path: Path):
    (tmp_path / "writing-brief.md").write_text("# Brief")
    (tmp_path / "draft.md").write_text("prose")
    r = derive(tmp_path)
    assert r.node == "critique"


def test_waiting_is_not_a_derivation_outcome():
    from orglens.workflow.result import Outcome

    assert not hasattr(Outcome, "WAITING")


def test_an_open_round_routes_to_the_closing_node(tmp_path: Path):
    """No `wait`. Whether it may RUN is the orchestrator's question."""
    (tmp_path / "writing-brief.md").write_text("# Brief")
    (tmp_path / "draft.md").write_text("prose")
    (tmp_path / "decisions-01.md").write_text("anything")
    r = derive(tmp_path)
    assert r.outcome == Outcome.RUNNABLE
    assert r.node == "revise"


def test_a_closed_round_routes_to_the_next_diagnostic(tmp_path: Path):
    (tmp_path / "writing-brief.md").write_text("# Brief")
    (tmp_path / "draft.md").write_text("prose")
    (tmp_path / "decisions-01.md").write_text("anything")
    (tmp_path / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"critique","round":1,"at":"t","event_id":"1"}\n'
        '{"type":"node_completed","node":"revise","round":1,"at":"t","event_id":"2"}\n'
    )
    r = derive(tmp_path)
    assert r.node == "audit"


def test_reject_only_round_continues_to_next_diagnostic(tmp_path: Path):
    """The dead state. A round whose findings were all rejected must not wedge
    the packet — the revise pass had nothing to apply and completed anyway, so
    the round is closed and the loop moves to the other diagnostic."""
    (tmp_path / "writing-brief.md").write_text("# Brief")
    (tmp_path / "draft.md").write_text("prose")
    (tmp_path / "decisions-01.md").write_text("anything")
    (tmp_path / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"audit","round":1,"at":"t","event_id":"1"}\n'
        '{"type":"node_completed","node":"revise","round":1,"at":"t","event_id":"2"}\n'
    )
    r = derive(tmp_path)
    assert r.outcome == Outcome.RUNNABLE
    assert r.node == "critique"


def test_adoption_is_not_special_cased_in_derivation(tmp_path: Path):
    """An adoption.md is just a file. Blocking is the orchestrator's job."""
    (tmp_path / "writing-brief.md").write_text("# Brief")
    (tmp_path / "draft-v2.md").write_text("prose")
    (tmp_path / "adoption.md").write_text("anything")
    r = derive(tmp_path)
    assert r.outcome == Outcome.ADOPTABLE


def test_artifact_without_brief_is_not_ambiguous(tmp_path: Path):
    """brief and critique both fired here before brief_exists was added."""
    (tmp_path / "draft.md").write_text("prose")
    r = derive(tmp_path)
    assert r.outcome == Outcome.RUNNABLE
    assert r.node == "brief"


def test_published_packet_is_terminal(tmp_path: Path):
    (tmp_path / "writing-brief.md").write_text(
        "---\npublished: https://example.com/x\n---\n"
    )
    (tmp_path / "draft.md").write_text("prose")
    r = derive(tmp_path)
    assert r.outcome == Outcome.TERMINAL
    assert r.node is None


def test_malformed_beats_fallback(tmp_path: Path):
    """A broken packet must be reported, never silently adopted."""
    (tmp_path / "decisions-01.md").write_text("anything")
    r = derive(tmp_path)
    assert r.outcome == Outcome.MALFORMED
    assert "rounds_without_artifact" in r.reason


def test_ambiguity_is_reported_not_resolved(tmp_path: Path):
    broken = {
        **WORKFLOW,
        "nodes": {
            "one": {"guard": {"all": ["brief_exists"]}},
            "two": {"guard": {"all": ["brief_exists"]}},
        },
    }
    (tmp_path / "writing-brief.md").write_text("# Brief")
    r = derive_next_node(tmp_path, broken)
    assert r.outcome == Outcome.AMBIGUOUS
    assert sorted(r.matched) == ["one", "two"]


def test_result_carries_facts_and_reason(tmp_path: Path):
    r = derive(tmp_path)
    assert r.facts["brief_exists"] is False
    assert r.reason


def test_noncanonical_artifact_routes_to_adopt(tmp_path: Path):
    """Defect 9, found the first time this ran on a real directory.

    A packet with draft-v1/draft-v2 was indistinguishable from a fresh
    canonical one — the family rule accepts draft-v2.md as the artifact, so
    `critique` fired and `adopt` never ran for exactly the case it exists for.
    This workflow always writes canonically (I1a), so a non-canonical artifact
    is evidence something else produced it.
    """
    (tmp_path / "writing-brief.md").write_text("# Brief")
    (tmp_path / "draft-v1.md").write_text("one")
    (tmp_path / "draft-v2.md").write_text("two")
    r = derive_next_node(tmp_path, WORKFLOW_NONCANON)
    assert r.outcome == Outcome.ADOPTABLE
    assert r.node == "adopt"


def test_canonical_artifact_still_routes_to_critique(tmp_path: Path):
    (tmp_path / "writing-brief.md").write_text("# Brief")
    (tmp_path / "draft.md").write_text("prose")
    r = derive_next_node(tmp_path, WORKFLOW_NONCANON)
    assert r.outcome == Outcome.RUNNABLE
    assert r.node == "critique"
