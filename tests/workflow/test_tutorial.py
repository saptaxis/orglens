"""The tutorial workflow, and the walkthrough its README.md promises.

This workflow is the only witness that the engine is generic: a bug-triage loop
sharing no vocabulary with an essay. A tutorial that lies is worse than no
tutorial, so the walkthrough's every step is held to here.
"""

from pathlib import Path

from click.testing import CliRunner

from orglens.workflow.definition import load_workflow
from orglens.cli import cli

TUTORIAL = Path(__file__).resolve().parents[2] / "capabilities" / "tutorial"
CHAIN = TUTORIAL / "WORKFLOW.yaml"


def run(*argv):
    return CliRunner().invoke(cli, ["workflow", *argv])


def test_the_shipped_workflow_loads_and_every_program_resolves():
    workflow = load_workflow(CHAIN)
    assert [s.name for s in workflow.nodes] == ["reproduce", "fix", "verify"]
    assert [s.review for s in workflow.nodes] == [False, True, False]
    assert all(s.program.is_file() for s in workflow.nodes)


def test_the_tutorial_shares_no_vocabulary_with_a_writing_chain():
    writing = {"brief", "claim-sheet", "skeleton", "prose", "critique", "revise", "audit", "polish"}
    assert {s.name for s in load_workflow(CHAIN).nodes} & writing == set()


def test_the_walkthrough_in_readme(tmp_path):
    pkt = tmp_path / "bug-417"
    pkt.mkdir()
    (pkt / "report.md").write_text("Login fails with a space in the password.\n")

    # 1. Where am I?
    out = run("next", str(pkt), "--workflow", str(CHAIN)).output
    assert "node: reproduce" in out and "write: " in out

    # 2. Do the pass, record it.
    (pkt / "repro.md").write_text("Steps: log in with 'a b'.\n")
    assert run("done", str(pkt), "--node", "reproduce", "--agent", "claude").exit_code == 0
    assert "node: fix" in run("next", str(pkt)).output

    # 3. A gate.
    (pkt / "fix.md").write_text("Change: stop trimming.\n")
    run("done", str(pkt), "--node", "fix", "--agent", "claude")
    out = run("next", str(pkt)).output
    assert "waiting on: review before verify" in out
    assert run("done", str(pkt), "--node", "verify", "--agent", "claude").exit_code == 2
    run("note", str(pkt), "agreed, ship it")
    out = run("next", str(pkt)).output
    assert "node: verify" in out and 'note:  "agreed, ship it"' in out

    # 4. The verdict fails: round again, by hand.
    (pkt / "verdict.md").write_text("FAILS\n")
    run("done", str(pkt), "--node", "verify", "--agent", "codex")
    assert "complete" in run("next", str(pkt)).output
    run("goto", str(pkt), "--node", "reproduce", "--why", "verdict FAILS on a trailing space")
    out = run("next", str(pkt)).output
    assert "node: reproduce" in out and "trailing space" in out

    # 5. Round two, all the way through.
    run("done", str(pkt), "--node", "reproduce", "--agent", "claude")
    run("done", str(pkt), "--node", "fix", "--agent", "claude")
    run("note", str(pkt), "yes")
    run("done", str(pkt), "--node", "verify", "--agent", "codex")
    assert "complete" in run("next", str(pkt)).output


def test_every_program_ends_by_telling_the_pass_how_to_record_itself():
    for node in load_workflow(CHAIN).nodes:
        text = node.program.read_text()
        assert f"--node {node.name}" in text, node.name
        assert "orglens workflow done" in text, node.name
        assert "workflow record" not in text, node.name
