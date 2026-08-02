from __future__ import annotations

from pathlib import Path

from orglens.workflow.predicates import PREDICATE_NAMES, evaluate
from orglens.workflow.snapshot import read_packet

WORKFLOW = {
    "artifact": {"family": "draft", "canonical": "draft.md", "history": "git"},
    "rounds": {"record": "decisions-{NN}.md", "closed_by": ["revise"]},
}


def facts(tmp_path: Path) -> dict[str, bool]:
    return evaluate(read_packet(tmp_path, WORKFLOW))


def test_empty_packet(tmp_path: Path):
    f = facts(tmp_path)
    assert f["brief_exists"] is False
    assert f["artifact_exists"] is False
    assert f["no_rounds"] is True
    assert f["round_open"] is False


def test_brief_and_artifact_present(tmp_path: Path):
    (tmp_path / "writing-brief.md").write_text("# Brief")
    (tmp_path / "draft.md").write_text("prose")
    f = facts(tmp_path)
    assert f["brief_exists"] is True
    assert f["artifact_exists"] is True
    assert f["artifact_noncanonical"] is False


def test_noncanonical_artifact(tmp_path: Path):
    (tmp_path / "writing-brief.md").write_text("# Brief")
    (tmp_path / "draft-v2.md").write_text("prose")
    assert facts(tmp_path)["artifact_noncanonical"] is True


def test_published_frontmatter(tmp_path: Path):
    (tmp_path / "writing-brief.md").write_text(
        "---\npublished: https://example.com/x\n---\n"
    )
    assert facts(tmp_path)["brief_published"] is True


def test_a_round_with_no_closing_node_is_open(tmp_path: Path):
    """Open/closed comes from run state, never from what the round says."""
    (tmp_path / "decisions-01.md").write_text("anything")
    f = facts(tmp_path)
    assert f["round_open"] is True
    assert f["round_closed"] is False


def test_a_round_a_closing_node_completed_is_closed(tmp_path: Path):
    (tmp_path / "decisions-01.md").write_text("anything")
    (tmp_path / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"revise","round":1,"at":"t","event_id":"1"}\n'
    )
    f = facts(tmp_path)
    assert f["round_open"] is False
    assert f["round_closed"] is True


def test_which_node_opened_the_last_round(tmp_path: Path):
    (tmp_path / "decisions-01.md").write_text("anything")
    (tmp_path / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"critique","round":1,"at":"t","event_id":"1"}\n'
    )
    f = facts(tmp_path)
    assert f["last_round_diagnosed_by_critique"] is True
    assert f["last_round_diagnosed_by_audit"] is False


def test_no_editorial_vocabulary_survives():
    for gone in (
        "round_unresolved",
        "round_actionable",
        "adoption_unresolved",
        "open_round",
        "no_open_round",
    ):
        assert gone not in PREDICATE_NAMES


def test_every_declared_predicate_is_returned(tmp_path: Path):
    assert set(facts(tmp_path)) == set(PREDICATE_NAMES)
