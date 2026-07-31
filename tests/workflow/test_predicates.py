from __future__ import annotations

from pathlib import Path

from orglens.workflow.predicates import PREDICATE_NAMES, evaluate
from orglens.workflow.snapshot import read_packet

WORKFLOW = {
    "artifact": {"family": "draft", "canonical": "draft.md", "history": "git"},
    "rounds": {"record": "decisions-{NN}.md"},
}


def facts(tmp_path: Path) -> dict[str, bool]:
    return evaluate(read_packet(tmp_path, WORKFLOW))


def test_empty_packet(tmp_path: Path):
    f = facts(tmp_path)
    assert f["brief_exists"] is False
    assert f["artifact_exists"] is False
    assert f["no_rounds"] is True
    assert f["no_open_round"] is True
    assert f["open_round"] is False


def test_brief_and_artifact_present(tmp_path: Path):
    (tmp_path / "writing-brief.md").write_text("# Brief")
    (tmp_path / "draft.md").write_text("prose")
    f = facts(tmp_path)
    assert f["brief_exists"] is True
    assert f["artifact_exists"] is True
    assert f["brief_published"] is False


def test_published_frontmatter(tmp_path: Path):
    (tmp_path / "writing-brief.md").write_text(
        "---\npublished: https://example.com/x\n---\n"
    )
    assert facts(tmp_path)["brief_published"] is True


def test_unresolved_round_is_open_and_not_actionable(tmp_path: Path):
    (tmp_path / "decisions-01.md").write_text("## Proposed\n- a\n")
    f = facts(tmp_path)
    assert f["open_round"] is True
    assert f["round_unresolved"] is True
    assert f["round_actionable"] is False


def test_ratified_round_is_actionable(tmp_path: Path):
    (tmp_path / "decisions-01.md").write_text("## Proposed\n\n## Accept\n- a\n")
    f = facts(tmp_path)
    assert f["round_unresolved"] is False
    assert f["round_actionable"] is True
    assert f["open_round"] is True


def test_reject_only_round_closes_itself(tmp_path: Path):
    """The dead state that wedged the first design. Reject-only must close."""
    (tmp_path / "decisions-01.md").write_text("## Proposed\n\n## Reject\n- a\n")
    f = facts(tmp_path)
    assert f["round_unresolved"] is False
    assert f["round_actionable"] is False
    assert f["open_round"] is False
    assert f["no_open_round"] is True


def test_revised_round_is_closed(tmp_path: Path):
    (tmp_path / "decisions-01.md").write_text("## Accept\n- a\n")
    (tmp_path / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"revise","round":1}\n'
    )
    f = facts(tmp_path)
    assert f["open_round"] is False


def test_last_round_critiqued_and_audited(tmp_path: Path):
    (tmp_path / "decisions-01.md").write_text("## Reject\n- a\n")
    (tmp_path / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"critique","round":1}\n'
    )
    f = facts(tmp_path)
    assert f["last_round_critiqued"] is True
    assert f["last_round_audited"] is False


def test_adoption_unresolved(tmp_path: Path):
    (tmp_path / "adoption.md").write_text("## Proposed\n- classify\n")
    assert facts(tmp_path)["adoption_unresolved"] is True


def test_every_declared_predicate_is_returned(tmp_path: Path):
    assert set(facts(tmp_path)) == set(PREDICATE_NAMES)
