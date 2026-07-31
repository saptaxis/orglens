from __future__ import annotations

import json
from pathlib import Path

import pytest

from orglens.workflow.runlog import append_fact, workflow_version


def test_appends_one_line(tmp_path: Path):
    append_fact(tmp_path, {"type": "node_completed", "node": "critique"})
    lines = (tmp_path / "runs.jsonl").read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["node"] == "critique"


def test_appends_without_rewriting(tmp_path: Path):
    append_fact(tmp_path, {"type": "node_completed", "node": "critique"})
    append_fact(tmp_path, {"type": "node_completed", "node": "revise"})
    lines = (tmp_path / "runs.jsonl").read_text().splitlines()
    assert [json.loads(line)["node"] for line in lines] == ["critique", "revise"]


def test_each_line_is_one_json_object(tmp_path: Path):
    append_fact(tmp_path, {"type": "node_completed", "node": "a", "note": "has\nnewline"})
    lines = (tmp_path / "runs.jsonl").read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["note"] == "has\nnewline"


def test_rejects_a_present_tense_projection(tmp_path: Path):
    """I1: past facts belong, projections of current state do not."""
    with pytest.raises(ValueError, match="current_state"):
        append_fact(tmp_path, {"type": "node_completed", "current_state": "waiting"})


def test_rejects_a_fact_with_no_type(tmp_path: Path):
    with pytest.raises(ValueError, match="type"):
        append_fact(tmp_path, {"node": "critique"})


def test_workflow_version_is_stable_and_content_addressed(tmp_path: Path):
    wf = tmp_path / "WORKFLOW.yaml"
    wf.write_text("workflow: article\n")
    first = workflow_version(wf)
    assert first.startswith("sha256:")
    assert first == workflow_version(wf)
    wf.write_text("workflow: article\nversion: 2\n")
    assert workflow_version(wf) != first
