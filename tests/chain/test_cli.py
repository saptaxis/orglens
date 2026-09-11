"""`orglens chain next · done · note · goto`, on a tmp packet."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from orglens.chain.session import read
from orglens.cli import cli


@pytest.fixture
def deck(tmp_path) -> Path:
    d = tmp_path / "deck"
    (d / "cards").mkdir(parents=True)
    for c in "abc":
        (d / "cards" / f"{c}.md").write_text("# card\n")
    (d / "CHAIN.yaml").write_text(
        "deck: demo\nstages:\n"
        "  - {name: one, card: cards/a.md, writes: one.md}\n"
        "  - {name: two, card: cards/b.md, writes: two.md, review: true}\n"
        "  - {name: three, card: cards/c.md, writes: three.md}\n"
    )
    return d / "CHAIN.yaml"


@pytest.fixture
def packet(tmp_path) -> Path:
    p = tmp_path / "packet"
    p.mkdir()
    return p


def run(*argv):
    return CliRunner().invoke(cli, ["chain", *argv])


class TestNext:
    def test_an_unbound_packet_without_deck_is_exit_2(self, packet):
        r = run("next", str(packet))
        assert r.exit_code == 2
        assert "no deck bound" in r.output

    def test_deck_binds_the_packet_on_first_use(self, packet, deck):
        r = run("next", str(packet), "--deck", str(deck))
        assert r.exit_code == 0, r.output
        assert "stage: one" in r.output
        assert f"card:  {deck.parent / 'cards' / 'a.md'}" in r.output
        assert f"write: {packet / 'one.md'}" in r.output
        assert [f["type"] for f in read(packet)] == ["deck"]
        # And is remembered: no --deck needed from now on.
        assert "stage: one" in run("next", str(packet)).output

    def test_json_carries_state_stage_card_write_note(self, packet, deck):
        r = run("next", str(packet), "--deck", str(deck), "--json")
        got = json.loads(r.output)
        assert got == {
            "state": "runnable", "stage": "one",
            "card": str(deck.parent / "cards" / "a.md"),
            "write": str(packet / "one.md"), "note": None,
        }

    def test_waiting_prints_the_question_and_exits_0(self, packet, deck):
        run("next", str(packet), "--deck", str(deck))
        run("done", str(packet), "--stage", "one", "--agent", "claude")
        run("done", str(packet), "--stage", "two", "--agent", "claude")
        r = run("next", str(packet))
        assert r.exit_code == 0
        assert "waiting on: review before three" in r.output
        assert "after stage two" in r.output
        assert json.loads(run("next", str(packet), "--json").output)["state"] == "waiting"

    def test_complete(self, packet, deck):
        run("next", str(packet), "--deck", str(deck))
        run("done", str(packet), "--stage", "one", "--agent", "claude")
        run("done", str(packet), "--stage", "two", "--agent", "claude")
        run("note", str(packet), "fine")
        run("done", str(packet), "--stage", "three", "--agent", "claude")
        r = run("next", str(packet))
        assert r.exit_code == 0 and "complete" in r.output

    def test_unknown_stage_in_log_is_exit_1(self, packet, deck):
        run("goto", str(packet), "--stage", "three", "--why", "x", "--deck", str(deck))
        (deck).write_text("deck: demo\nstages:\n  - {name: one, card: cards/a.md, writes: one.md}\n")
        r = run("next", str(packet))
        assert r.exit_code == 1
        assert "unknown stage in session: three" in r.output

    def test_a_bad_deck_is_exit_2(self, packet, deck):
        deck.write_text("deck: x\nstages: []\n")
        r = run("next", str(packet), "--deck", str(deck))
        assert r.exit_code == 2
        assert "no stages" in r.output

    def test_the_note_answering_the_gate_is_printed(self, packet, deck):
        run("next", str(packet), "--deck", str(deck))
        run("done", str(packet), "--stage", "one", "--agent", "claude", "--question", "order?")
        run("note", str(packet), "swap them")
        r = run("next", str(packet))
        assert "stage: two" in r.output
        assert 'note:  "swap them"' in r.output


class TestDone:
    def test_records_the_stage_and_what_it_wrote(self, packet, deck):
        (packet / "one.md").write_text("x")
        r = run("done", str(packet), "--stage", "one", "--agent", "codex", "--deck", str(deck))
        assert r.exit_code == 0, r.output
        [_, fact] = read(packet)
        assert (fact["type"], fact["stage"], fact["agent"], fact["wrote"]) == (
            "done", "one", "codex", ["one.md"])

    def test_wrote_is_empty_when_the_file_is_absent(self, packet, deck):
        run("done", str(packet), "--stage", "one", "--agent", "codex", "--deck", str(deck))
        [_, fact] = read(packet)
        assert fact["wrote"] == []

    def test_refuses_a_stage_the_chain_is_not_on(self, packet, deck):
        r = run("done", str(packet), "--stage", "three", "--agent", "codex", "--deck", str(deck))
        assert r.exit_code == 2
        assert "chain is on one" in r.output
        assert [f["type"] for f in read(packet)] == ["deck"]

    def test_force_overrides_and_is_recorded(self, packet, deck):
        r = run("done", str(packet), "--stage", "three", "--agent", "codex",
                "--deck", str(deck), "--force")
        assert r.exit_code == 0, r.output
        [_, fact] = read(packet)
        assert fact["stage"] == "three" and fact["forced"] is True

    def test_refuses_while_a_gate_is_open(self, packet, deck):
        run("next", str(packet), "--deck", str(deck))
        run("done", str(packet), "--stage", "one", "--agent", "claude", "--question", "q")
        r = run("done", str(packet), "--stage", "two", "--agent", "claude")
        assert r.exit_code == 2
        assert "waiting" in r.output


class TestNote:
    def test_resolves_the_open_gate(self, packet, deck):
        run("next", str(packet), "--deck", str(deck))
        done = run("done", str(packet), "--stage", "one", "--agent", "claude", "--question", "q")
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
        r = run("goto", str(packet), "--stage", "three", "--why", "entering late",
                "--deck", str(deck))
        assert r.exit_code == 0, r.output
        assert "stage: three" in run("next", str(packet)).output

    def test_refuses_an_undeclared_stage(self, packet, deck):
        r = run("goto", str(packet), "--stage", "nope", "--why", "x", "--deck", str(deck))
        assert r.exit_code == 2
        assert "nope" in r.output


def test_the_workflow_group_is_gone():
    r = CliRunner().invoke(cli, ["workflow", "--help"])
    assert r.exit_code != 0
