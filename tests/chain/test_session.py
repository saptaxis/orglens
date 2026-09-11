"""Position and gate, derived from the log's last routing fact."""

from pathlib import Path

import pytest

from orglens.chain.deck import load_deck
from orglens.chain.session import (
    SessionError, append, bind, deck_path, next_stage, read, State,
)


@pytest.fixture
def deck(tmp_path):
    (tmp_path / "deck" / "cards").mkdir(parents=True)
    for c in "abc":
        (tmp_path / "deck" / "cards" / f"{c}.md").write_text("# card\n")
    (tmp_path / "deck" / "CHAIN.yaml").write_text(
        "deck: demo\nstages:\n"
        "  - {name: one, card: cards/a.md, writes: one.md}\n"
        "  - {name: two, card: cards/b.md, writes: two.md, review: true}\n"
        "  - {name: three, card: cards/c.md, writes: three.md}\n"
    )
    return load_deck(tmp_path / "deck" / "CHAIN.yaml")


@pytest.fixture
def packet(tmp_path):
    p = tmp_path / "packet"
    p.mkdir()
    return p


def test_an_empty_log_starts_at_the_first_stage(deck, packet):
    pos = next_stage(deck, read(packet))
    assert pos.state == State.RUNNABLE
    assert pos.stage.name == "one"
    assert pos.note is None


def test_done_moves_to_the_stage_after(deck, packet):
    append(packet, {"type": "done", "stage": "one", "agent": "claude"})
    pos = next_stage(deck, read(packet))
    assert (pos.state, pos.stage.name) == (State.RUNNABLE, "two")


def test_done_on_the_last_stage_is_complete(deck, packet):
    for s in ("one", "two", "three"):
        append(packet, {"type": "done", "stage": s, "agent": "claude"})
    pos = next_stage(deck, read(packet))
    assert pos.state == State.COMPLETE
    assert pos.stage is None


def test_a_review_on_the_last_stage_waits_before_complete(tmp_path, packet):
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "c.md").write_text("#\n")
    (tmp_path / "d" / "CHAIN.yaml").write_text(
        "deck: x\nstages:\n  - {name: only, card: c.md, writes: o.md, review: true}\n")
    deck = load_deck(tmp_path / "d" / "CHAIN.yaml")
    done = append(packet, {"type": "done", "stage": "only", "agent": "claude"})
    pos = next_stage(deck, read(packet))
    assert (pos.state, pos.question) == (State.WAITING, "review before complete")
    append(packet, {"type": "note", "resolves": done["id"], "text": "fine"})
    assert next_stage(deck, read(packet)).state == State.COMPLETE


def test_done_on_a_review_stage_waits(deck, packet):
    append(packet, {"type": "done", "stage": "one", "agent": "claude"})
    append(packet, {"type": "done", "stage": "two", "agent": "claude"})
    pos = next_stage(deck, read(packet))
    assert pos.state == State.WAITING
    assert pos.stage.name == "three"
    assert pos.question == "review before three"
    assert pos.after == "two"


def test_done_with_a_question_waits_on_any_stage(deck, packet):
    append(packet, {"type": "done", "stage": "one", "agent": "claude",
                    "question": "which order?"})
    pos = next_stage(deck, read(packet))
    assert pos.state == State.WAITING
    assert pos.question == "which order?"


def test_a_note_resolving_the_gate_makes_the_next_stage_runnable_with_the_note(deck, packet):
    done = append(packet, {"type": "done", "stage": "one", "agent": "claude",
                           "question": "which order?"})
    append(packet, {"type": "note", "resolves": done["id"], "text": "swap them"})
    pos = next_stage(deck, read(packet))
    assert pos.state == State.RUNNABLE
    assert pos.stage.name == "two"
    assert pos.note == "swap them"


def test_a_note_for_an_older_fact_does_not_resolve_the_open_gate(deck, packet):
    first = append(packet, {"type": "done", "stage": "one", "agent": "claude",
                            "question": "q1"})
    append(packet, {"type": "note", "resolves": first["id"], "text": "a1"})
    append(packet, {"type": "done", "stage": "two", "agent": "claude"})
    pos = next_stage(deck, read(packet))
    assert pos.state == State.WAITING


def test_goto_names_the_stage_to_run_next(deck, packet):
    append(packet, {"type": "goto", "stage": "three", "why": "entering late"})
    pos = next_stage(deck, read(packet))
    assert (pos.state, pos.stage.name) == (State.RUNNABLE, "three")
    assert pos.note == "entering late"


def test_goto_over_an_open_gate_clears_it(deck, packet):
    append(packet, {"type": "done", "stage": "one", "agent": "claude", "question": "q"})
    append(packet, {"type": "goto", "stage": "one", "why": "again"})
    pos = next_stage(deck, read(packet))
    assert (pos.state, pos.stage.name) == (State.RUNNABLE, "one")


def test_a_log_naming_a_stage_the_deck_lacks_is_unknown(deck, packet):
    append(packet, {"type": "done", "stage": "gone", "agent": "claude"})
    pos = next_stage(deck, read(packet))
    assert pos.state == State.UNKNOWN
    assert pos.after == "gone"


def test_every_fact_is_stamped_with_time_and_id(packet):
    fact = append(packet, {"type": "goto", "stage": "one", "why": "x"})
    assert len(fact["id"]) == 12 and int(fact["id"], 16) >= 0
    assert "T" in fact["at"]
    [back] = read(packet)
    assert back == fact


def test_a_malformed_fact_is_refused_before_writing(packet):
    with pytest.raises(SessionError, match="stage"):
        append(packet, {"type": "done", "agent": "claude"})
    with pytest.raises(SessionError, match="type"):
        append(packet, {"type": "wat"})
    assert not (packet / "session.jsonl").exists()


def test_the_deck_binding_is_the_first_line_and_read_back(packet, deck):
    assert deck_path(read(packet)) is None
    bind(packet, deck.path)
    assert deck_path(read(packet)) == deck.path
    # Binding twice is refused: one deck per packet.
    with pytest.raises(SessionError, match="already bound"):
        bind(packet, deck.path)


def test_a_broken_line_is_skipped_not_fatal(packet):
    append(packet, {"type": "goto", "stage": "one", "why": "x"})
    with (packet / "session.jsonl").open("a") as h:
        h.write("not json\n")
    assert len(read(packet)) == 1
