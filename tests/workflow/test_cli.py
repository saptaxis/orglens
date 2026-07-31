from __future__ import annotations

import copy
import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from orglens.cli import cli
from tests.workflow.test_derive import WORKFLOW


def write_workflow(root: Path) -> Path:
    # `expect` is what `record` checks a pass against. The deriver ignores it,
    # so carrying the deck's value for `critique` here leaves every other test
    # in this module unchanged.
    definition = copy.deepcopy(WORKFLOW)
    definition["nodes"]["critique"]["expect"] = "waiting"

    path = root / "WORKFLOW.yaml"
    path.write_text(yaml.safe_dump(definition))
    return path


def test_derive_reports_runnable_as_json(tmp_path: Path):
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "writing-brief.md").write_text("# Brief")
    (packet / "draft.md").write_text("prose")
    wf = write_workflow(tmp_path)

    result = CliRunner().invoke(
        cli, ["workflow", "derive", str(packet), "--workflow", str(wf), "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["outcome"] == "runnable"
    assert payload["node"] == "critique"


def test_derive_reports_waiting(tmp_path: Path):
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "writing-brief.md").write_text("# Brief")
    (packet / "draft.md").write_text("prose")
    (packet / "decisions-01.md").write_text("## Proposed\n- a\n")
    wf = write_workflow(tmp_path)

    result = CliRunner().invoke(
        cli, ["workflow", "derive", str(packet), "--workflow", str(wf), "--json"]
    )
    assert result.exit_code == 0
    assert json.loads(result.output)["outcome"] == "waiting"


def test_malformed_exits_nonzero(tmp_path: Path):
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "decisions-01.md").write_text("## Proposed\n- a\n")
    wf = write_workflow(tmp_path)

    result = CliRunner().invoke(
        cli, ["workflow", "derive", str(packet), "--workflow", str(wf), "--json"]
    )
    assert result.exit_code == 1
    assert json.loads(result.output)["outcome"] == "malformed"


def test_missing_workflow_fails_loudly(tmp_path: Path):
    packet = tmp_path / "packet"
    packet.mkdir()
    result = CliRunner().invoke(
        cli,
        ["workflow", "derive", str(packet), "--workflow", str(tmp_path / "nope.yaml")],
    )
    assert result.exit_code == 2
    assert "no workflow definition" in result.output


def test_check_validates_a_definition(tmp_path: Path):
    wf = write_workflow(tmp_path)
    result = CliRunner().invoke(cli, ["workflow", "check", "--workflow", str(wf)])
    assert result.exit_code == 0
    assert "no problems" in result.output.lower()


def test_check_reports_an_unknown_predicate(tmp_path: Path):
    broken = {**WORKFLOW, "nodes": {"x": {"guard": {"all": ["bogus"]}}}}
    wf = tmp_path / "WORKFLOW.yaml"
    wf.write_text(yaml.safe_dump(broken))
    result = CliRunner().invoke(cli, ["workflow", "check", "--workflow", str(wf)])
    assert result.exit_code == 1
    assert "bogus" in result.output


def test_record_appends_a_fact_and_confirms_expect(tmp_path: Path):
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "writing-brief.md").write_text("# Brief")
    (packet / "draft.md").write_text("prose")
    (packet / "decisions-01.md").write_text("## Proposed\n- a\n")
    wf = write_workflow(tmp_path)

    result = CliRunner().invoke(
        cli,
        ["workflow", "record", str(packet), "--workflow", str(wf),
         "--node", "critique", "--agent", "codex"],
    )
    assert result.exit_code == 0

    lines = (packet / "runs.jsonl").read_text().splitlines()
    fact = json.loads(lines[-1])
    assert fact["type"] == "node_completed"
    assert fact["node"] == "critique"
    assert fact["agent"] == "codex"
    assert fact["workflow_version"].startswith("sha256:")


def test_record_fails_when_the_packet_does_not_match_expect(tmp_path: Path):
    """critique expects `waiting`. A round with nothing proposed derives
    elsewhere, which means the pass wrote something malformed."""
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "writing-brief.md").write_text("# Brief")
    (packet / "draft.md").write_text("prose")
    (packet / "decisions-01.md").write_text("## Accept\n- a\n")
    wf = write_workflow(tmp_path)

    result = CliRunner().invoke(
        cli,
        ["workflow", "record", str(packet), "--workflow", str(wf), "--node", "critique"],
    )
    assert result.exit_code == 1
    assert "expected waiting" in result.output
    assert "runnable" in result.output


def test_record_rejects_an_unknown_node(tmp_path: Path):
    packet = tmp_path / "packet"
    packet.mkdir()
    wf = write_workflow(tmp_path)
    result = CliRunner().invoke(
        cli,
        ["workflow", "record", str(packet), "--workflow", str(wf), "--node", "nonesuch"],
    )
    assert result.exit_code == 2
    assert "nonesuch" in result.output
