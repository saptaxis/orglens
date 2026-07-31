from __future__ import annotations

from pathlib import Path

from orglens.workflow.malformed import detect
from orglens.workflow.snapshot import read_packet

WORKFLOW = {
    "artifact": {"family": "draft", "canonical": "draft.md", "history": "git"},
    "rounds": {"record": "decisions-{NN}.md"},
}


def snap(tmp_path: Path):
    return read_packet(tmp_path, WORKFLOW)


def test_clean_packet_is_not_malformed(tmp_path: Path):
    (tmp_path / "writing-brief.md").write_text("# Brief")
    (tmp_path / "draft.md").write_text("prose")
    assert detect(snap(tmp_path)) is None


def test_log_naming_a_missing_file(tmp_path: Path):
    (tmp_path / "draft.md").write_text("prose")
    (tmp_path / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"critique","round":1,'
        '"wrote":{"decisions-01.md":"sha256:x"}}\n'
    )
    assert detect(snap(tmp_path)) == "log_names_missing_file"


def test_round_both_critiqued_and_audited(tmp_path: Path):
    (tmp_path / "draft.md").write_text("prose")
    (tmp_path / "decisions-01.md").write_text("## Reject\n- a\n")
    (tmp_path / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"critique","round":1}\n'
        '{"type":"node_completed","node":"audit","round":1}\n'
    )
    assert detect(snap(tmp_path)) == "round_both_critiqued_and_audited"


def test_rounds_without_artifact(tmp_path: Path):
    (tmp_path / "decisions-01.md").write_text("## Proposed\n- a\n")
    assert detect(snap(tmp_path)) == "rounds_without_artifact"


def test_round_number_gap(tmp_path: Path):
    (tmp_path / "draft.md").write_text("prose")
    (tmp_path / "decisions-01.md").write_text("## Reject\n- a\n")
    (tmp_path / "decisions-03.md").write_text("## Proposed\n- a\n")
    assert detect(snap(tmp_path)) == "round_number_gap"
