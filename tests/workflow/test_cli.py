from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml
from click.testing import CliRunner

from orglens.cli import cli
from tests.workflow.test_derive import WORKFLOW


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def write_workflow(root: Path) -> Path:
    path = root / "WORKFLOW.yaml"
    path.write_text(yaml.safe_dump(WORKFLOW))
    return path


def test_derive_reports_runnable_as_json(tmp_path: Path):
    packet = tmp_path / "packet"
    packet.mkdir()
    wf = write_workflow(tmp_path)

    result = CliRunner().invoke(
        cli, ["workflow", "derive", str(packet), "--workflow", str(wf), "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["outcome"] == "runnable"
    assert payload["node"] == "brief"


def test_derive_walks_the_pipeline(tmp_path: Path):
    """A completed node routes straight to the one that follows it —
    nothing else needs to happen first."""
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"brief","at":"t","event_id":"e1"}\n'
    )
    wf = write_workflow(tmp_path)

    result = CliRunner().invoke(
        cli, ["workflow", "derive", str(packet), "--workflow", str(wf), "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["outcome"] == "runnable"
    assert payload["node"] == "draft"


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


def test_derive_reports_a_block_before_a_node(tmp_path: Path):
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "runs.jsonl").write_text(
        '{"type":"needs_human","event_id":"n1","node":"brief",'
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
    """The substrate needs no scheduler, so any driver works. The driver is
    a command that receives the job on stdin and holds nothing."""
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


def test_record_raises_exactly_one_gate_even_when_the_node_also_declares_review(
    repo_packet,
):
    """`critique` declares `human_review: true` *and* the card passes
    `--question` — exactly one gate must be raised (the `--question` one),
    and a single `orglens workflow resolve` must clear it, nothing left
    blocking behind it."""
    packet, deck, wf = repo_packet

    result = CliRunner().invoke(
        cli,
        ["workflow", "record", str(packet), "--workflow", str(wf), "--deck", str(deck),
         "--node", "critique", "--question", "is finding 3 in scope?"],
    )
    assert result.exit_code == 0

    entries = [json.loads(line) for line in (packet / "runs.jsonl").read_text().splitlines()]
    needs_human = [e for e in entries if e["type"] == "needs_human"]
    assert len(needs_human) == 1
    assert needs_human[0]["raised_by"] == "node"
    assert "finding 3" in needs_human[0]["question"]

    resolved = CliRunner().invoke(
        cli, ["workflow", "resolve", str(packet), "--note", "yes, in scope"]
    )
    assert resolved.exit_code == 0

    derived = CliRunner().invoke(
        cli, ["workflow", "derive", str(packet), "--workflow", str(wf), "--json"]
    )
    payload = json.loads(derived.output)
    assert payload["blocked"] is False


def test_record_raises_the_declared_gate_when_no_question_is_given(repo_packet):
    packet, deck, wf = repo_packet
    result = CliRunner().invoke(
        cli,
        ["workflow", "record", str(packet), "--workflow", str(wf), "--deck", str(deck),
         "--node", "critique"],
    )
    assert result.exit_code == 0
    entries = [json.loads(line) for line in (packet / "runs.jsonl").read_text().splitlines()]
    gate = entries[-1]
    assert gate["type"] == "needs_human"
    assert gate["raised_by"] == "declaration"


def test_record_rejects_an_unknown_node(repo_packet):
    packet, deck, wf = repo_packet
    result = CliRunner().invoke(
        cli,
        ["workflow", "record", str(packet), "--workflow", str(wf), "--deck", str(deck),
         "--node", "nonesuch"],
    )
    assert result.exit_code == 2
    assert "nonesuch" in result.output


def test_job_reports_an_unknown_node_cleanly(repo_packet):
    """`--node ghost` must be reported the same clean way every other CLI
    path handles an unknown node, not a raw `KeyError` traceback."""
    packet, deck, wf = repo_packet
    result = CliRunner().invoke(
        cli,
        ["workflow", "job", str(packet), "--workflow", str(wf), "--deck", str(deck),
         "--node", "ghost"],
    )
    assert result.exit_code == 2
    assert "ghost" in result.output
    assert not isinstance(result.exception, KeyError)


def test_run_stops_after_max_turns_on_a_self_perpetuating_definition(tmp_path: Path):
    """A node whose guard does not depend on anything its own completion
    changes — no read of it ever gets consumed, a guard over a fact that
    stays true forever — derives to itself indefinitely, and would dispatch
    forever unattended without a bound."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")

    packet = tmp_path / "a-piece"
    packet.mkdir()
    (packet / "some-brief.md").write_text("# Brief")
    deck = tmp_path / "deck"
    deck.mkdir()

    workflow_path = tmp_path / "WORKFLOW.yaml"
    workflow_path.write_text(
        yaml.safe_dump(
            {
                "nodes": {
                    "loop": {
                        "role": "self",
                        "reads": [],
                        "writes": [],
                        "guard": {"all": ["exists:some-brief.md"]},
                    }
                },
            }
        )
    )

    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")

    script = tmp_path / "noop.sh"
    script.write_text("#!/bin/sh\ncat >/dev/null\n")
    script.chmod(0o755)

    result = CliRunner().invoke(
        cli,
        ["workflow", "run", str(packet), "--workflow", str(workflow_path),
         "--deck", str(deck), "--dispatch", str(script), "--max-turns", "5"],
    )
    assert result.exit_code == 1
    assert "5 turns" in result.output

    entries = [json.loads(line) for line in (packet / "runs.jsonl").read_text().splitlines()]
    assert len([e for e in entries if e["type"] == "node_completed"]) == 5


def test_record_no_longer_accepts_a_round(repo_packet):
    packet, deck, wf = repo_packet
    result = CliRunner().invoke(
        cli,
        ["workflow", "record", str(packet), "--workflow", str(wf), "--deck", str(deck),
         "--node", "critique", "--round", "1"],
    )
    assert result.exit_code != 0
    assert "no such option" in result.output.lower()


def test_goto_moves_the_cursor_forward(repo_packet):
    packet, deck, wf = repo_packet
    result = CliRunner().invoke(
        cli,
        ["workflow", "goto", str(packet), "--workflow", str(wf),
         "--node", "audit", "--note", "revise applied by hand"],
    )
    assert result.exit_code == 0
    entries = [json.loads(l) for l in (packet / "runs.jsonl").read_text().splitlines()]
    assert entries[-1]["type"] == "resumed_at"
    assert entries[-1]["node"] == "audit"
    assert entries[-1]["note"] == "revise applied by hand"


def test_goto_moves_the_cursor_backward(repo_packet):
    """Re-running a stage is a move, not a special mode."""
    packet, deck, wf = repo_packet
    CliRunner().invoke(cli, ["workflow", "goto", str(packet), "--workflow", str(wf),
                             "--node", "audit", "--note", "fwd"])
    CliRunner().invoke(cli, ["workflow", "goto", str(packet), "--workflow", str(wf),
                             "--node", "brief", "--note", "start over"])
    entries = [json.loads(l) for l in (packet / "runs.jsonl").read_text().splitlines()]
    assert entries[-1]["node"] == "brief"


def test_goto_rejects_an_undeclared_node(repo_packet):
    packet, deck, wf = repo_packet
    result = CliRunner().invoke(
        cli, ["workflow", "goto", str(packet), "--workflow", str(wf),
              "--node", "ghost", "--note", "x"],
    )
    assert result.exit_code != 0
    assert "ghost" in result.output


def test_job_reports_a_glob_that_matched_nothing(repo_packet):
    packet, deck, wf = repo_packet
    result = CliRunner().invoke(
        cli, ["workflow", "job", str(packet), "--workflow", str(wf),
              "--deck", str(deck), "--node", "critique"],
    )
    assert "(no match)" in result.output


def test_record_stores_what_was_read_and_written(repo_packet):
    packet, deck, wf = repo_packet
    (packet / "findings.md").write_text("f")
    CliRunner().invoke(
        cli, ["workflow", "record", str(packet), "--workflow", str(wf),
              "--deck", str(deck), "--node", "critique"],
    )
    fact = json.loads((packet / "runs.jsonl").read_text().splitlines()[0])
    assert fact["wrote"] == ["findings.md"]
    assert "read" in fact


# --- fix round 1 ------------------------------------------------------------
# Finding 1: the glob report matched declared globs against `Job.reads` with
# `fnmatch` on the basename alone, silently dropping any directory segment —
# a different, weaker algorithm than the one `resolve_job` actually used
# (`Path.glob`). A path-bearing glob that genuinely resolved was reported as
# `(no match)` and its file omitted entirely.
# Finding 3: `"read" in fact` is satisfied by `read: []`. Pin the content.


def test_job_reports_a_path_bearing_glob_that_did_resolve(tmp_path: Path):
    """Regression for the basename-only match: a glob naming a
    subdirectory, like a real deck's `references/smell-patterns.md`, must
    be reported by what `Job.unmatched` says, not recomputed and lost."""
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "references").mkdir()
    (packet / "references" / "smell-patterns.md").write_text("residues")

    deck = tmp_path / "deck"
    deck.mkdir()

    workflow_path = tmp_path / "WORKFLOW.yaml"
    workflow_path.write_text(
        yaml.safe_dump(
            {
                "nodes": {
                    "audit": {
                        "role": "self",
                        "reads": ["references/smell-patterns.md"],
                        "writes": [],
                        "guard": {"all": ["after:nothing"]},
                    }
                },
            }
        )
    )

    result = CliRunner().invoke(
        cli,
        ["workflow", "job", str(packet), "--workflow", str(workflow_path),
         "--deck", str(deck), "--node", "audit"],
    )
    assert result.exit_code == 0
    assert "(no match)" not in result.output
    assert "references/smell-patterns.md" in result.output


def test_record_names_exactly_what_it_read(repo_packet):
    packet, deck, wf = repo_packet
    (packet / "findings.md").write_text("f")
    CliRunner().invoke(
        cli, ["workflow", "record", str(packet), "--workflow", str(wf),
              "--deck", str(deck), "--node", "critique"],
    )
    fact = json.loads((packet / "runs.jsonl").read_text().splitlines()[0])
    assert fact["read"] == ["writing-brief.md"]
