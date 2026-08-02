from __future__ import annotations

from pathlib import Path

from orglens.workflow.job import resolve_job

WORKFLOW = {
    "marker": "writing.yaml",
    "artifact": {"family": "draft", "canonical": "draft.md"},
    "rounds": {"record": "decisions-{NN}.md", "closed_by": ["revise"]},
    "nodes": {
        "critique": {
            "role": "references/roles/critic.md",
            "reads": ["@brief", "@artifact", "@profile.voice"],
            "writes": ["decisions-{next}.md"],
            "must_not_modify": ["**"],
            "requires": {"interpreter": "not-the-producer"},
            "human_review": True,
            "expect": "revise",
        }
    },
}


def build(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / "writing.yaml").write_text(
        "default: portfolio\nprofiles:\n  portfolio: {voice: references/voice/portfolio.md}\n"
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


def test_the_next_round_number_is_resolved(tmp_path: Path):
    packet, deck = build(tmp_path)
    job = resolve_job(packet, deck, WORKFLOW, "critique")
    assert job.writes == [str(packet / "decisions-01.md")]
    assert "{next}" not in job.writes[0]


def test_the_next_round_number_increments(tmp_path: Path):
    packet, deck = build(tmp_path)
    (packet / "decisions-01.md").write_text("x")
    job = resolve_job(packet, deck, WORKFLOW, "critique")
    assert job.writes == [str(packet / "decisions-02.md")]


def test_double_star_expands_to_actual_files_minus_declared_writes(tmp_path: Path):
    packet, deck = build(tmp_path)
    job = resolve_job(packet, deck, WORKFLOW, "critique")
    names = {Path(p).name for p in job.must_not_modify}
    assert names == {"writing-brief.md", "draft.md"}
    assert "decisions-01.md" not in names


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


def test_rounds_resolves_to_declared_round_records_only(tmp_path: Path):
    """@rounds meant 'everything that is not the brief or artifact', which
    swept up adoption.md, stray drafts, and the run log."""
    packet, deck = build(tmp_path)
    (packet / "decisions-01.md").write_text("x")
    (packet / "adoption.md").write_text("x")
    (packet / "draft-v1.md").write_text("superseded")
    wf = {**WORKFLOW, "nodes": {"n": {"reads": ["@rounds"], "writes": []}}}
    job = resolve_job(packet, deck, wf, "n")
    assert [Path(p).name for p in job.reads] == ["decisions-01.md"]


def test_a_file_named_twice_is_read_once(tmp_path: Path):
    packet, deck = build(tmp_path)
    wf = {**WORKFLOW, "nodes": {"n": {"reads": ["@brief", "@brief"], "writes": []}}}
    job = resolve_job(packet, deck, wf, "n")
    assert len(job.reads) == 1
