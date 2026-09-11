"""The tutorial deck, and the walkthrough its DECK.md promises.

This deck is the only witness that the engine is generic: a bug-triage loop
sharing no vocabulary with an essay. A tutorial that lies is worse than no
tutorial, so the walkthrough's every step is held to here.
"""

from pathlib import Path

from click.testing import CliRunner

from orglens.chain.deck import load_deck
from orglens.cli import cli

DECK = Path(__file__).resolve().parents[2] / "capabilities" / "decks" / "tutorial"
CHAIN = DECK / "CHAIN.yaml"


def run(*argv):
    return CliRunner().invoke(cli, ["chain", *argv])


def test_the_shipped_deck_loads_and_every_card_resolves():
    deck = load_deck(CHAIN)
    assert [s.name for s in deck.stages] == ["reproduce", "fix", "verify"]
    assert [s.review for s in deck.stages] == [False, True, False]
    assert all(s.card.is_file() for s in deck.stages)


def test_the_deck_shares_no_vocabulary_with_a_writing_chain():
    writing = {"brief", "claim-sheet", "skeleton", "prose", "critique", "revise", "audit", "polish"}
    assert {s.name for s in load_deck(CHAIN).stages} & writing == set()


def test_the_walkthrough_in_deck_md(tmp_path):
    pkt = tmp_path / "bug-417"
    pkt.mkdir()
    (pkt / "report.md").write_text("Login fails with a space in the password.\n")

    # 1. Where am I?
    out = run("next", str(pkt), "--deck", str(CHAIN)).output
    assert "stage: reproduce" in out and "write: " in out

    # 2. Do the pass, record it.
    (pkt / "repro.md").write_text("Steps: log in with 'a b'.\n")
    assert run("done", str(pkt), "--stage", "reproduce", "--agent", "claude").exit_code == 0
    assert "stage: fix" in run("next", str(pkt)).output

    # 3. A gate.
    (pkt / "fix.md").write_text("Change: stop trimming.\n")
    run("done", str(pkt), "--stage", "fix", "--agent", "claude")
    out = run("next", str(pkt)).output
    assert "waiting on: review before verify" in out
    assert run("done", str(pkt), "--stage", "verify", "--agent", "claude").exit_code == 2
    run("note", str(pkt), "agreed, ship it")
    out = run("next", str(pkt)).output
    assert "stage: verify" in out and 'note:  "agreed, ship it"' in out

    # 4. The verdict fails: round again, by hand.
    (pkt / "verdict.md").write_text("FAILS\n")
    run("done", str(pkt), "--stage", "verify", "--agent", "codex")
    assert "complete" in run("next", str(pkt)).output
    run("goto", str(pkt), "--stage", "reproduce", "--why", "verdict FAILS on a trailing space")
    out = run("next", str(pkt)).output
    assert "stage: reproduce" in out and "trailing space" in out

    # 5. Round two, all the way through.
    run("done", str(pkt), "--stage", "reproduce", "--agent", "claude")
    run("done", str(pkt), "--stage", "fix", "--agent", "claude")
    run("note", str(pkt), "yes")
    run("done", str(pkt), "--stage", "verify", "--agent", "codex")
    assert "complete" in run("next", str(pkt)).output


def test_every_card_ends_by_telling_the_pass_how_to_record_itself():
    for stage in load_deck(CHAIN).stages:
        text = stage.card.read_text()
        assert f"--stage {stage.name}" in text, stage.name
        assert "orglens chain done" in text, stage.name
        assert "workflow record" not in text, stage.name
