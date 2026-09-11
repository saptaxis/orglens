"""A deck is an ordered list of stages. Loading it is the whole validation."""

from pathlib import Path

import pytest

from orglens.chain.deck import DeckError, load_deck


def _deck(tmp_path: Path, text: str, cards=("a.md", "b.md")) -> Path:
    for c in cards:
        (tmp_path / "cards").mkdir(exist_ok=True)
        (tmp_path / "cards" / c).write_text("# card\n")
    path = tmp_path / "CHAIN.yaml"
    path.write_text(text)
    return path


GOOD = """\
deck: demo
stages:
  - name: first
    card: cards/a.md
    writes: one.md
  - name: second
    card: cards/b.md
    writes: two.md
    review: true
"""


def test_a_deck_loads_its_stages_in_order_with_cards_resolved(tmp_path):
    deck = load_deck(_deck(tmp_path, GOOD))
    assert deck.name == "demo"
    assert [s.name for s in deck.stages] == ["first", "second"]
    assert deck.stages[0].card == (tmp_path / "cards" / "a.md").resolve()
    assert deck.stages[0].writes == "one.md"
    assert deck.stages[0].review is False
    assert deck.stages[1].review is True
    assert deck.path == tmp_path / "CHAIN.yaml"


def test_stages_are_reachable_by_name_and_by_position(tmp_path):
    deck = load_deck(_deck(tmp_path, GOOD))
    assert deck.stage("second").writes == "two.md"
    assert deck.stage("nope") is None
    assert deck.after("first").name == "second"
    assert deck.after("second") is None


def test_empty_stages_are_refused(tmp_path):
    with pytest.raises(DeckError, match="no stages"):
        load_deck(_deck(tmp_path, "deck: x\nstages: []\n"))


def test_duplicate_names_are_refused(tmp_path):
    text = GOOD.replace("name: second", "name: first")
    with pytest.raises(DeckError, match="first"):
        load_deck(_deck(tmp_path, text))


def test_a_missing_card_is_refused_at_load(tmp_path):
    text = GOOD.replace("cards/b.md", "cards/missing.md")
    with pytest.raises(DeckError, match="missing.md"):
        load_deck(_deck(tmp_path, text))


def test_a_stage_without_writes_is_refused(tmp_path):
    text = GOOD.replace("    writes: two.md\n", "")
    with pytest.raises(DeckError, match="second"):
        load_deck(_deck(tmp_path, text))


def test_a_stage_without_a_name_is_refused(tmp_path):
    text = GOOD.replace("  - name: second\n", "  - ")
    with pytest.raises(DeckError, match="name"):
        load_deck(_deck(tmp_path, text))


def test_a_missing_file_is_a_deck_error_not_a_crash(tmp_path):
    with pytest.raises(DeckError, match="CHAIN.yaml"):
        load_deck(tmp_path / "CHAIN.yaml")
