from __future__ import annotations

import copy
import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from orglens.cli import cli
from tests.workflow.conftest import ORCHESTRATOR_WORKFLOW
from tests.workflow.test_derive import WORKFLOW


def write_workflow(root: Path) -> Path:
    # `expect` is what `record` checks a pass against. The deriver ignores it,
    # so declaring one for `critique` here leaves every other test in this
    # module unchanged. A completed critique leaves the packet awaiting a
    # mutation, which routes straight to `revise`.
    definition = copy.deepcopy(WORKFLOW)
    definition["nodes"]["critique"]["expect"] = "revise"
    definition["nodes"]["critique"]["must_not_modify"] = ["**"]
    definition["nodes"]["audit"]["must_not_modify"] = ["**"]

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
    """A diagnostic that already completed routes straight to the mutation
    that resolves it — nothing else needs to happen first."""
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "writing-brief.md").write_text("# Brief")
    (packet / "draft.md").write_text("prose")
    (packet / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"critique","at":"t","event_id":"e1"}\n'
    )
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
    (packet / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"critique","wrote":["findings.md"],'
        '"at":"t","event_id":"e1"}\n'
    )
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


def test_record_appends_a_fact_and_confirms_expect(repo_packet):
    packet, deck, wf = repo_packet
    (packet / "findings.md").write_text("## Findings\n- something\n")

    result = CliRunner().invoke(
        cli,
        ["workflow", "record", str(packet), "--workflow", str(wf), "--deck", str(deck),
         "--node", "critique", "--agent", "codex"],
    )
    assert result.exit_code == 0

    lines = (packet / "runs.jsonl").read_text().splitlines()
    fact = json.loads(lines[-1])
    assert fact["type"] == "node_completed"
    assert fact["node"] == "critique"
    assert fact["agent"] == "codex"
    assert fact["wrote"] == ["findings.md"]
    assert fact["workflow_version"].startswith("sha256:")


def test_record_fails_when_the_packet_does_not_match_expect(repo_packet):
    """critique declares it expects `audit` next; nothing else about the
    packet changed, so it actually derives to `revise` — the postcondition
    disagrees with what the pass claimed."""
    packet, deck, wf = repo_packet
    broken = copy.deepcopy(ORCHESTRATOR_WORKFLOW)
    broken["nodes"]["critique"]["expect"] = "audit"
    wf.write_text(yaml.safe_dump(broken))

    result = CliRunner().invoke(
        cli,
        ["workflow", "record", str(packet), "--workflow", str(wf), "--deck", str(deck),
         "--node", "critique"],
    )
    assert result.exit_code == 1
    assert "expected audit" in result.output
    assert "revise" in result.output


def test_record_rejects_an_unknown_node(repo_packet):
    packet, deck, wf = repo_packet
    result = CliRunner().invoke(
        cli,
        ["workflow", "record", str(packet), "--workflow", str(wf), "--deck", str(deck),
         "--node", "nonesuch"],
    )
    assert result.exit_code == 2
    assert "nonesuch" in result.output


def test_a_failed_postcondition_is_itself_recorded(repo_packet):
    """Append-only means the log must explain itself. A missed postcondition
    is not a fourth kind of fact — it is a needs_human, like any other gate."""
    packet, deck, wf = repo_packet
    broken = copy.deepcopy(ORCHESTRATOR_WORKFLOW)
    broken["nodes"]["critique"]["expect"] = "audit"
    wf.write_text(yaml.safe_dump(broken))

    result = CliRunner().invoke(
        cli,
        ["workflow", "record", str(packet), "--workflow", str(wf), "--deck", str(deck),
         "--node", "critique"],
    )
    assert result.exit_code == 1

    facts = [json.loads(line) for line in (packet / "runs.jsonl").read_text().splitlines()]
    assert [f["type"] for f in facts] == ["node_completed", "needs_human"]
    assert "audit" in facts[-1]["question"]
    assert "revise" in facts[-1]["question"]


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


def test_run_dispatches_through_a_command(tmp_path: Path, repo_packet):
    """I6: the substrate needs no scheduler, so any driver works. The driver
    is a command that receives the job on stdin and holds nothing."""
    packet, deck, wf = repo_packet
    script = tmp_path / "driver.sh"
    script.write_text(
        "#!/bin/sh\n"
        "python -c \"import json,sys,pathlib;"
        "j=json.load(sys.stdin);"
        "pathlib.Path(j['writes'][0]).write_text('## Findings\\n')\"\n"
    )
    script.chmod(0o755)

    result = CliRunner().invoke(
        cli,
        ["workflow", "run", str(packet), "--workflow", str(wf),
         "--deck", str(deck), "--dispatch", str(script), "--once"],
    )
    assert result.exit_code == 0
    assert "critique" in result.output
    assert (packet / "findings.md").exists()


def test_run_without_a_dispatcher_prints_the_job_and_stops(repo_packet):
    packet, deck, wf = repo_packet
    result = CliRunner().invoke(
        cli, ["workflow", "run", str(packet), "--workflow", str(wf), "--deck", str(deck)]
    )
    assert result.exit_code == 0
    assert "no dispatcher" in result.output
    assert not (packet / "runs.jsonl").exists()


def test_record_raises_a_gate_with_a_question(repo_packet):
    """How a stuck pass blocks itself without an orchestrator."""
    packet, deck, wf = repo_packet
    result = CliRunner().invoke(
        cli,
        ["workflow", "record", str(packet), "--workflow", str(wf), "--deck", str(deck),
         "--node", "critique", "--question", "is finding 3 in scope?"],
    )
    assert result.exit_code == 0
    entries = [json.loads(line) for line in (packet / "runs.jsonl").read_text().splitlines()]
    assert entries[0]["type"] == "node_completed"
    assert entries[-1]["type"] == "needs_human"
    assert "finding 3" in entries[-1]["question"]


def test_record_no_longer_accepts_a_round(repo_packet):
    packet, deck, wf = repo_packet
    result = CliRunner().invoke(
        cli,
        ["workflow", "record", str(packet), "--workflow", str(wf), "--deck", str(deck),
         "--node", "critique", "--round", "1"],
    )
    assert result.exit_code != 0
    assert "no such option" in result.output.lower()
