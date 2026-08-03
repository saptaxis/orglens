from __future__ import annotations

from pathlib import Path

import pytest

from orglens.workflow.job import resolve_job

WORKFLOW = {
    "roots": [".", "../shared"],
    "nodes": {
        "critique": {
            "role": "operators/critic.md",
            "reads": ["*-brief*.md", "draft*.md", "runs.jsonl", "findings*.md"],
            "writes": ["findings.md"],
            "human_review": True,
        },
        "local": {"role": "own/liner.md", "writes": ["draft.md"]},
        "inline": {"role": "self", "writes": ["draft.md"]},
    },
}


def build(tmp_path: Path) -> tuple[Path, Path]:
    packet = tmp_path / "pkt"
    packet.mkdir()
    (packet / "writing-brief.md").write_text("b")
    (packet / "draft.md").write_text("d")
    (packet / "draft-2.md").write_text("d2")
    deck = tmp_path / "deck"
    (deck / "own").mkdir(parents=True)
    (deck / "own" / "liner.md").write_text("liner")
    shared = tmp_path / "shared" / "operators"
    shared.mkdir(parents=True)
    (shared / "critic.md").write_text("critic")
    return packet, deck


def test_every_path_is_absolute(tmp_path: Path):
    packet, deck = build(tmp_path)
    job = resolve_job(packet, deck, WORKFLOW, "critique")
    for p in [job.role, *job.reads, *job.writes]:
        assert Path(p).is_absolute(), p


def test_a_glob_yields_every_match_sorted(tmp_path: Path):
    packet, deck = build(tmp_path)
    job = resolve_job(packet, deck, WORKFLOW, "critique")
    names = [Path(p).name for p in job.reads]
    assert names[:3] == ["writing-brief.md", "draft-2.md", "draft.md"] or set(
        names[:3]
    ) == {"writing-brief.md", "draft-2.md", "draft.md"}
    assert "draft-2.md" in names and "draft.md" in names


def test_a_read_matching_nothing_is_reported_not_fatal(tmp_path: Path):
    packet, deck = build(tmp_path)
    job = resolve_job(packet, deck, WORKFLOW, "critique")
    assert "findings*.md" in job.unmatched
    assert "draft*.md" not in job.unmatched


def test_a_file_matched_twice_is_read_once(tmp_path: Path):
    packet, deck = build(tmp_path)
    wf = {**WORKFLOW, "nodes": {**WORKFLOW["nodes"]}}
    wf["nodes"]["critique"] = {
        **WORKFLOW["nodes"]["critique"],
        "reads": ["draft.md", "draft*.md"],
    }
    job = resolve_job(packet, deck, wf, "critique")
    assert job.reads.count(str(packet / "draft.md")) == 1


def test_writes_are_literal_names_under_the_packet(tmp_path: Path):
    packet, deck = build(tmp_path)
    job = resolve_job(packet, deck, WORKFLOW, "critique")
    assert job.writes == [str(packet / "findings.md")]


def test_a_role_resolves_through_the_shared_root(tmp_path: Path):
    packet, deck = build(tmp_path)
    job = resolve_job(packet, deck, WORKFLOW, "critique")
    assert job.role == str((tmp_path / "shared" / "operators" / "critic.md").resolve())


def test_a_role_in_the_deck_wins_over_the_shared_root(tmp_path: Path):
    packet, deck = build(tmp_path)
    job = resolve_job(packet, deck, WORKFLOW, "local")
    assert job.role == str((deck / "own" / "liner.md").resolve())


def test_self_means_no_role_file(tmp_path: Path):
    packet, deck = build(tmp_path)
    assert resolve_job(packet, deck, WORKFLOW, "inline").role is None


def test_a_missing_role_names_every_root_tried(tmp_path: Path):
    packet, deck = build(tmp_path)
    wf = {**WORKFLOW, "nodes": {"x": {"role": "nope/ghost.md", "writes": []}}}
    with pytest.raises(FileNotFoundError) as exc:
        resolve_job(packet, deck, wf, "x")
    assert "ghost.md" in str(exc.value)
    assert "../shared" in str(exc.value)


def test_roots_default_to_the_deck(tmp_path: Path):
    packet, deck = build(tmp_path)
    wf = {"nodes": {"local": {"role": "own/liner.md", "writes": []}}}
    assert resolve_job(packet, deck, wf, "local").role == str(
        (deck / "own" / "liner.md").resolve()
    )


def test_declaration_fields_carry_through(tmp_path: Path):
    packet, deck = build(tmp_path)
    job = resolve_job(packet, deck, WORKFLOW, "critique")
    assert job.human_review is True


def test_an_undeclared_node_is_an_error(tmp_path: Path):
    packet, deck = build(tmp_path)
    with pytest.raises(KeyError, match="ghost"):
        resolve_job(packet, deck, WORKFLOW, "ghost")
