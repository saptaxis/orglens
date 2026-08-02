from __future__ import annotations

from pathlib import Path

from orglens.workflow.snapshot import read_packet

WORKFLOW = {
    "artifact": {"family": "draft", "canonical": "draft.md", "history": "git"},
    "rounds": {"record": "decisions-{NN}.md"},
}


def test_reads_empty_packet(tmp_path: Path):
    snap = read_packet(tmp_path, WORKFLOW)
    assert snap.brief is None
    assert snap.artifact is None
    assert snap.rounds == {}
    assert snap.runs == []


def test_finds_brief_and_frontmatter(tmp_path: Path):
    (tmp_path / "writing-brief.md").write_text(
        "---\nfrozen: 2026-08-01\npublished: https://example.com/x\n---\n\n# Brief\n"
    )
    snap = read_packet(tmp_path, WORKFLOW)
    assert snap.brief == "writing-brief.md"
    assert snap.brief_frontmatter["published"] == "https://example.com/x"


def test_finds_canonical_artifact(tmp_path: Path):
    (tmp_path / "draft.md").write_text("prose")
    snap = read_packet(tmp_path, WORKFLOW)
    assert snap.artifact == "draft.md"


def test_artifact_family_rule_highest_version_wins(tmp_path: Path):
    (tmp_path / "draft-v1.md").write_text("one")
    (tmp_path / "draft-v2.md").write_text("two")
    snap = read_packet(tmp_path, WORKFLOW)
    assert snap.artifact == "draft-v2.md"


def test_round_pattern_comes_from_the_workflow_not_the_engine(tmp_path: Path):
    """No decisions-NN regex in the engine. The deck declares its pattern."""
    (tmp_path / "decisions-01.md").write_text("anything at all")
    (tmp_path / "decisions-02.md").write_text("anything at all")
    snap = read_packet(tmp_path, WORKFLOW)
    assert sorted(snap.rounds) == [1, 2]


def test_a_deck_may_use_a_different_round_pattern(tmp_path: Path):
    (tmp_path / "review-03.md").write_text("x")
    other = {**WORKFLOW, "rounds": {"record": "review-{NN}.md"}}
    snap = read_packet(tmp_path, other)
    assert sorted(snap.rounds) == [3]


def test_the_snapshot_does_not_read_document_bodies(tmp_path: Path):
    """RoundInfo carries a number and nothing else. What a round *says* is
    data for the next node, never routing input."""
    (tmp_path / "decisions-01.md").write_text("## Accept\n- something\n")
    snap = read_packet(tmp_path, WORKFLOW)
    assert snap.rounds[1].number == 1
    assert not hasattr(snap.rounds[1], "sections")


def test_adoption_is_not_a_snapshot_concept(tmp_path: Path):
    (tmp_path / "adoption.md").write_text("## Proposed\n- x\n")
    snap = read_packet(tmp_path, WORKFLOW)
    assert not hasattr(snap, "adoption")


def test_run_state_entries_are_read(tmp_path: Path):
    (tmp_path / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"critique","round":1,"at":"t","event_id":"1"}\n'
    )
    snap = read_packet(tmp_path, WORKFLOW)
    assert snap.runs[0]["node"] == "critique"
