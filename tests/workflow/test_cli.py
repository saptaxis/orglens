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
    # so declaring one for `critique` here leaves every other test in this
    # module unchanged. A critique opens a round, and an open round routes to
    # the node that closes it.
    definition = copy.deepcopy(WORKFLOW)
    definition["nodes"]["critique"]["expect"] = "revise"

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


def test_derive_reports_an_open_round_as_runnable(tmp_path: Path):
    """An open round is a node to run, not a state to sit in."""
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "writing-brief.md").write_text("# Brief")
    (packet / "draft.md").write_text("prose")
    (packet / "decisions-01.md").write_text("anything at all")
    wf = write_workflow(tmp_path)

    result = CliRunner().invoke(
        cli, ["workflow", "derive", str(packet), "--workflow", str(wf), "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["outcome"] == "runnable"
    assert payload["node"] == "revise"


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
    (packet / "decisions-01.md").write_text("anything at all")
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
    """critique expects `revise`. A pass that recorded itself without opening
    a round leaves the packet deriving back to critique, which means the pass
    wrote nothing the workflow can see."""
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "writing-brief.md").write_text("# Brief")
    (packet / "draft.md").write_text("prose")
    wf = write_workflow(tmp_path)

    result = CliRunner().invoke(
        cli,
        ["workflow", "record", str(packet), "--workflow", str(wf), "--node", "critique"],
    )
    assert result.exit_code == 1
    assert "expected revise" in result.output
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


def test_a_failed_postcondition_is_itself_recorded(tmp_path: Path):
    """Append-only means the log must explain itself. Two identical
    node_completed facts cannot distinguish a retry from a double-run."""
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "writing-brief.md").write_text("# Brief")
    (packet / "draft.md").write_text("prose")
    wf = write_workflow(tmp_path)

    result = CliRunner().invoke(
        cli,
        ["workflow", "record", str(packet), "--workflow", str(wf), "--node", "critique"],
    )
    assert result.exit_code == 1

    facts = [json.loads(line) for line in (packet / "runs.jsonl").read_text().splitlines()]
    assert [f["type"] for f in facts] == ["node_completed", "postcondition_failed"]
    assert facts[-1]["expected"] == "revise"
    assert facts[-1]["derived"] == "critique"


def test_derive_reports_a_block_before_a_node(tmp_path: Path):
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "writing-brief.md").write_text("# Brief")
    (packet / "draft.md").write_text("prose")
    (packet / "runs.jsonl").write_text(
        '{"type":"needs_human","event_id":"n1","node":"critique",'
        '"raised_by":"node","question":"does finding 3 count?","at":"t"}\n'
    )
    wf = write_workflow(tmp_path)
    result = CliRunner().invoke(
        cli, ["workflow", "derive", str(packet), "--workflow", str(wf), "--json"]
    )
    payload = json.loads(result.output)
    assert payload["blocked"] is True
    assert "finding 3" in payload["block"]["question"]


def test_resolve_unblocks_and_appends(tmp_path: Path):
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "runs.jsonl").write_text(
        '{"type":"needs_human","event_id":"n1","node":"critique",'
        '"raised_by":"node","question":"q","at":"t"}\n'
    )
    result = CliRunner().invoke(
        cli, ["workflow", "resolve", str(packet), "--note", "yes, keep it"]
    )
    assert result.exit_code == 0
    entries = [
        json.loads(line)
        for line in (packet / "runs.jsonl").read_text().splitlines()
    ]
    assert entries[-1]["type"] == "human_resolved"
    assert entries[-1]["resolves"] == "n1"
    assert entries[-1]["note"] == "yes, keep it"


def test_resolve_with_nothing_outstanding_is_an_error(tmp_path: Path):
    packet = tmp_path / "packet"
    packet.mkdir()
    result = CliRunner().invoke(
        cli, ["workflow", "resolve", str(packet), "--note", "x"]
    )
    assert result.exit_code == 1
    assert "nothing outstanding" in result.output
