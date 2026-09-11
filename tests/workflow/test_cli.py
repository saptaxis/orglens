"""`orglens workflow next · done · note · goto`, on a tmp packet."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from orglens.workflow.session import read
from orglens.cli import cli


@pytest.fixture
def deck(tmp_path) -> Path:
    d = tmp_path / "deck"
    (d / "programs").mkdir(parents=True)
    for c in "abc":
        (d / "programs" / f"{c}.md").write_text("# program\n")
    (d / "WORKFLOW.yaml").write_text(
        "workflow: demo\nnodes:\n"
        "  - {name: one, program: programs/a.md, writes: one.md}\n"
        "  - {name: two, program: programs/b.md, writes: two.md, review: true}\n"
        "  - {name: three, program: programs/c.md, writes: three.md}\n"
    )
    return d / "WORKFLOW.yaml"


@pytest.fixture
def packet(tmp_path) -> Path:
    p = tmp_path / "packet"
    p.mkdir()
    return p


def run(*argv):
    return CliRunner().invoke(cli, ["workflow", *argv])


class TestNext:
    def test_an_unbound_packet_without_deck_is_exit_2(self, packet):
        r = run("next", str(packet))
        assert r.exit_code == 2
        assert "no deck bound" in r.output

    def test_deck_binds_the_packet_on_first_use(self, packet, deck):
        r = run("next", str(packet), "--deck", str(deck))
        assert r.exit_code == 0, r.output
        assert "node: one" in r.output
        assert f"program: {deck.parent / 'programs' / 'a.md'}" in r.output
        assert f"write: {packet / 'one.md'}" in r.output
        assert [f["type"] for f in read(packet)] == ["deck"]
        # And is remembered: no --deck needed from now on.
        assert "node: one" in run("next", str(packet)).output

    def test_json_carries_state_node_program_write_note(self, packet, deck):
        r = run("next", str(packet), "--deck", str(deck), "--json")
        got = json.loads(r.output)
        assert got == {
            "state": "runnable", "node": "one",
            "program": str(deck.parent / "programs" / "a.md"),
            "write": str(packet / "one.md"), "note": None,
        }

    def test_waiting_prints_the_question_and_exits_0(self, packet, deck):
        run("next", str(packet), "--deck", str(deck))
        run("done", str(packet), "--node", "one", "--agent", "claude")
        run("done", str(packet), "--node", "two", "--agent", "claude")
        r = run("next", str(packet))
        assert r.exit_code == 0
        assert "waiting on: review before three" in r.output
        assert "after node two" in r.output
        assert json.loads(run("next", str(packet), "--json").output)["state"] == "waiting"

    def test_complete(self, packet, deck):
        run("next", str(packet), "--deck", str(deck))
        run("done", str(packet), "--node", "one", "--agent", "claude")
        run("done", str(packet), "--node", "two", "--agent", "claude")
        run("note", str(packet), "fine")
        run("done", str(packet), "--node", "three", "--agent", "claude")
        r = run("next", str(packet))
        assert r.exit_code == 0 and "complete" in r.output

    def test_unknown_node_in_log_is_exit_1(self, packet, deck):
        run("goto", str(packet), "--node", "three", "--why", "x", "--deck", str(deck))
        (deck).write_text("workflow: demo\nnodes:\n  - {name: one, program: programs/a.md, writes: one.md}\n")
        r = run("next", str(packet))
        assert r.exit_code == 1
        assert "unknown node in session: three" in r.output

    def test_a_bad_deck_is_exit_2(self, packet, deck):
        deck.write_text("workflow: x\nnodes: []\n")
        r = run("next", str(packet), "--deck", str(deck))
        assert r.exit_code == 2
        assert "no nodes" in r.output

    def test_the_note_answering_the_gate_is_printed(self, packet, deck):
        run("next", str(packet), "--deck", str(deck))
        run("done", str(packet), "--node", "one", "--agent", "claude", "--question", "order?")
        run("note", str(packet), "swap them")
        r = run("next", str(packet))
        assert "node: two" in r.output
        assert 'note:  "swap them"' in r.output


class TestDone:
    def test_records_the_node_and_what_it_wrote(self, packet, deck):
        (packet / "one.md").write_text("x")
        r = run("done", str(packet), "--node", "one", "--agent", "codex", "--deck", str(deck))
        assert r.exit_code == 0, r.output
        [_, fact] = read(packet)
        assert (fact["type"], fact["node"], fact["agent"], fact["wrote"]) == (
            "done", "one", "codex", ["one.md"])

    def test_wrote_is_empty_when_the_file_is_absent(self, packet, deck):
        run("done", str(packet), "--node", "one", "--agent", "codex", "--deck", str(deck))
        [_, fact] = read(packet)
        assert fact["wrote"] == []

    def test_refuses_a_node_the_chain_is_not_on(self, packet, deck):
        r = run("done", str(packet), "--node", "three", "--agent", "codex", "--deck", str(deck))
        assert r.exit_code == 2
        assert "workflow is on one" in r.output
        assert [f["type"] for f in read(packet)] == ["deck"]

    def test_force_overrides_and_is_recorded(self, packet, deck):
        r = run("done", str(packet), "--node", "three", "--agent", "codex",
                "--deck", str(deck), "--force")
        assert r.exit_code == 0, r.output
        [_, fact] = read(packet)
        assert fact["node"] == "three" and fact["forced"] is True

    def test_refuses_while_a_gate_is_open(self, packet, deck):
        run("next", str(packet), "--deck", str(deck))
        run("done", str(packet), "--node", "one", "--agent", "claude", "--question", "q")
        r = run("done", str(packet), "--node", "two", "--agent", "claude")
        assert r.exit_code == 2
        assert "waiting" in r.output


class TestNote:
    def test_resolves_the_open_gate(self, packet, deck):
        run("next", str(packet), "--deck", str(deck))
        done = run("done", str(packet), "--node", "one", "--agent", "claude", "--question", "q")
        r = run("note", str(packet), "the answer")
        assert r.exit_code == 0, r.output
        facts = read(packet)
        assert facts[-1]["type"] == "note"
        assert facts[-1]["resolves"] == facts[-2]["id"]
        assert facts[-1]["text"] == "the answer"

    def test_refuses_when_no_gate_is_open(self, packet, deck):
        run("next", str(packet), "--deck", str(deck))
        r = run("note", str(packet), "nothing to answer")
        assert r.exit_code == 2
        assert "no gate" in r.output


class TestGoto:
    def test_points_the_cursor(self, packet, deck):
        r = run("goto", str(packet), "--node", "three", "--why", "entering late",
                "--deck", str(deck))
        assert r.exit_code == 0, r.output
        assert "node: three" in run("next", str(packet)).output

    def test_refuses_an_undeclared_node(self, packet, deck):
        r = run("goto", str(packet), "--node", "nope", "--why", "x", "--deck", str(deck))
        assert r.exit_code == 2
        assert "nope" in r.output


def test_the_chain_group_never_shipped_under_that_name():
    r = CliRunner().invoke(cli, ["chain", "--help"])
    assert r.exit_code != 0
