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


def test_parses_round_sections(tmp_path: Path):
    (tmp_path / "decisions-01.md").write_text(
        "## Proposed\n- a\n\n## Accept\n- b\n- c\n\n## Reject\n"
    )
    snap = read_packet(tmp_path, WORKFLOW)
    assert set(snap.rounds) == {1}
    assert snap.rounds[1].sections["Proposed"] == ["a"]
    assert snap.rounds[1].sections["Accept"] == ["b", "c"]
    assert snap.rounds[1].sections["Reject"] == []


def test_reads_run_log(tmp_path: Path):
    (tmp_path / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"critique","round":1}\n'
        '{"type":"node_completed","node":"revise","round":1}\n'
    )
    snap = read_packet(tmp_path, WORKFLOW)
    assert [r["node"] for r in snap.runs] == ["critique", "revise"]
