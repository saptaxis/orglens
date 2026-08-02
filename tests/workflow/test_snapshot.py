from __future__ import annotations

from pathlib import Path

from orglens.workflow.snapshot import read_packet

WORKFLOW = {
    "brief": "*-brief.md",
    "artifact": {"family": "draft", "canonical": "draft.md", "history": "git"},
}


def test_an_empty_packet(tmp_path: Path):
    snap = read_packet(tmp_path, WORKFLOW)
    assert snap.brief is None and snap.artifact is None and snap.runs == []


def test_a_missing_directory_is_empty_not_an_error(tmp_path: Path):
    assert read_packet(tmp_path / "nope", WORKFLOW).files == []


def test_finds_the_brief_and_its_frontmatter(tmp_path: Path):
    (tmp_path / "writing-brief.md").write_text("---\nprofile: research\n---\n# Brief")
    snap = read_packet(tmp_path, WORKFLOW)
    assert snap.brief == "writing-brief.md"
    assert snap.brief_frontmatter["profile"] == "research"


def test_the_brief_glob_comes_from_the_deck(tmp_path: Path):
    """No deck filename in the engine. A different deck names its own."""
    (tmp_path / "spec.md").write_text("# Spec")
    other = {**WORKFLOW, "brief": "spec.md"}
    assert read_packet(tmp_path, other).brief == "spec.md"


def test_a_workflow_declaring_no_brief_finds_none(tmp_path: Path):
    (tmp_path / "writing-brief.md").write_text("# Brief")
    assert read_packet(tmp_path, {"artifact": {"family": "draft"}}).brief is None


def test_the_highest_family_member_is_the_artifact(tmp_path: Path):
    (tmp_path / "draft-v1.md").write_text("old")
    (tmp_path / "draft-v2.md").write_text("new")
    assert read_packet(tmp_path, WORKFLOW).artifact == "draft-v2.md"


def test_a_bare_family_name_is_version_one(tmp_path: Path):
    (tmp_path / "draft.md").write_text("x")
    snap = read_packet(tmp_path, WORKFLOW)
    assert snap.artifact == "draft.md" and snap.artifact_canonical is True


def test_a_versioned_artifact_is_not_canonical(tmp_path: Path):
    (tmp_path / "draft-v2.md").write_text("x")
    assert read_packet(tmp_path, WORKFLOW).artifact_canonical is False


def test_unrecognised_files_are_listed_and_nothing_more(tmp_path: Path):
    """A file the deck did not declare is a filename. It is never opened."""
    (tmp_path / "notes-from-a-call.md").write_text("## Proposed\n- do a thing\n")
    snap = read_packet(tmp_path, WORKFLOW)
    assert "notes-from-a-call.md" in snap.files
    assert snap.artifact is None


def test_run_state_is_read(tmp_path: Path):
    (tmp_path / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"critique","at":"t","event_id":"1"}\n'
    )
    assert read_packet(tmp_path, WORKFLOW).runs[0]["node"] == "critique"
