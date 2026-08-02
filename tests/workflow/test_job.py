from __future__ import annotations

from pathlib import Path

from orglens.workflow.job import STRUCTURAL, resolve_job

WORKFLOW = {
    "marker": "writing.yaml",
    "brief": "*-brief.md",
    "artifact": {"family": "draft", "canonical": "draft.md"},
    "nodes": {
        "critique": {
            "role": "references/roles/critic.md",
            "reads": ["@brief", "@artifact", "@profile.voice"],
            "writes": ["findings.md"],
            "must_not_modify": ["**"],
            "requires": {"interpreter": "not-the-producer"},
            "human_review": True,
            "expect": "revise",
            "diagnoses": True,
        },
        "revise": {"role": "references/roles/liner.md", "writes": ["draft.md"]},
    },
}


def build(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / "writing.yaml").write_text(
        "default: portfolio\n"
        "profiles:\n  portfolio: {voice: references/voice/portfolio.md}\n"
    )
    packet = tmp_path / "a-piece"
    packet.mkdir()
    (packet / "writing-brief.md").write_text("# Brief")
    (packet / "draft.md").write_text("prose")
    deck = tmp_path / "deck"
    (deck / "references" / "voice").mkdir(parents=True)
    (deck / "references" / "roles").mkdir(parents=True)
    (deck / "references" / "roles" / "critic.md").write_text("# critic")
    (deck / "references" / "voice" / "portfolio.md").write_text("# voice")
    return packet, deck


def test_three_structural_references():
    assert STRUCTURAL == ("@brief", "@artifact", "@runstate")


def test_every_path_is_absolute(tmp_path: Path):
    packet, deck = build(tmp_path)
    job = resolve_job(packet, deck, WORKFLOW, "critique")
    for path in [job.role, *job.reads, *job.writes, *job.must_not_modify]:
        assert Path(path).is_absolute(), path


def test_structural_references_resolve(tmp_path: Path):
    packet, deck = build(tmp_path)
    job = resolve_job(packet, deck, WORKFLOW, "critique")
    assert str(packet / "writing-brief.md") in job.reads
    assert str(packet / "draft.md") in job.reads


def test_profile_reference_resolves_against_the_deck(tmp_path: Path):
    packet, deck = build(tmp_path)
    job = resolve_job(packet, deck, WORKFLOW, "critique")
    assert str(deck / "references" / "voice" / "portfolio.md") in job.reads


def test_writes_are_literal(tmp_path: Path):
    """Nothing is numbered, so nothing is templated."""
    packet, deck = build(tmp_path)
    job = resolve_job(packet, deck, WORKFLOW, "critique")
    assert job.writes == [str(packet / "findings.md")]


def test_a_file_named_twice_is_read_once(tmp_path: Path):
    packet, deck = build(tmp_path)
    wf = {**WORKFLOW}
    wf["nodes"] = {**WORKFLOW["nodes"]}
    wf["nodes"]["critique"] = {
        **WORKFLOW["nodes"]["critique"],
        "reads": ["@artifact", "draft.md"],
    }
    job = resolve_job(packet, deck, wf, "critique")
    assert job.reads.count(str(packet / "draft.md")) == 1


def test_double_star_expands_to_present_files_minus_declared_writes(tmp_path: Path):
    packet, deck = build(tmp_path)
    (packet / "findings.md").write_text("old findings")
    job = resolve_job(packet, deck, WORKFLOW, "critique")
    names = {Path(p).name for p in job.must_not_modify}
    assert names == {"writing-brief.md", "draft.md"}
    assert "runs.jsonl" not in names


def test_the_role_path_is_deck_relative(tmp_path: Path):
    packet, deck = build(tmp_path)
    job = resolve_job(packet, deck, WORKFLOW, "critique")
    assert job.role == str(deck / "references" / "roles" / "critic.md")


def test_declaration_fields_carry_through(tmp_path: Path):
    packet, deck = build(tmp_path)
    job = resolve_job(packet, deck, WORKFLOW, "critique")
    assert job.requires == {"interpreter": "not-the-producer"}
    assert job.human_review is True
    assert job.expect == "revise"
    assert job.profile == "portfolio"


def test_an_undeclared_node_is_an_error(tmp_path: Path):
    packet, deck = build(tmp_path)
    import pytest

    with pytest.raises(KeyError, match="nonesuch"):
        resolve_job(packet, deck, WORKFLOW, "nonesuch")
