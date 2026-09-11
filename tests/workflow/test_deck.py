"""A deck is an ordered list of nodes. Loading it is the whole validation."""

from pathlib import Path

import pytest

from orglens.workflow.deck import DeckError, load_deck


def _deck(tmp_path: Path, text: str, programs=("a.md", "b.md")) -> Path:
    for c in programs:
        (tmp_path / "programs").mkdir(exist_ok=True)
        (tmp_path / "programs" / c).write_text("# program\n")
    path = tmp_path / "WORKFLOW.yaml"
    path.write_text(text)
    return path


GOOD = """\
workflow: demo
nodes:
  - name: first
    program: programs/a.md
    writes: one.md
  - name: second
    program: programs/b.md
    writes: two.md
    review: true
"""


def test_a_deck_loads_its_nodes_in_order_with_programs_resolved(tmp_path):
    deck = load_deck(_deck(tmp_path, GOOD))
    assert deck.name == "demo"
    assert [s.name for s in deck.nodes] == ["first", "second"]
    assert deck.nodes[0].program == (tmp_path / "programs" / "a.md").resolve()
    assert deck.nodes[0].writes == "one.md"
    assert deck.nodes[0].review is False
    assert deck.nodes[1].review is True
    assert deck.path == tmp_path / "WORKFLOW.yaml"


def test_nodes_are_reachable_by_name_and_by_position(tmp_path):
    deck = load_deck(_deck(tmp_path, GOOD))
    assert deck.node("second").writes == "two.md"
    assert deck.node("nope") is None
    assert deck.after("first").name == "second"
    assert deck.after("second") is None


def test_empty_nodes_are_refused(tmp_path):
    with pytest.raises(DeckError, match="no nodes"):
        load_deck(_deck(tmp_path, "workflow: x\nnodes: []\n"))


def test_duplicate_names_are_refused(tmp_path):
    text = GOOD.replace("name: second", "name: first")
    with pytest.raises(DeckError, match="first"):
        load_deck(_deck(tmp_path, text))


def test_a_missing_program_is_refused_at_load(tmp_path):
    text = GOOD.replace("programs/b.md", "programs/missing.md")
    with pytest.raises(DeckError, match="missing.md"):
        load_deck(_deck(tmp_path, text))


def test_a_node_without_writes_is_refused(tmp_path):
    text = GOOD.replace("    writes: two.md\n", "")
    with pytest.raises(DeckError, match="second"):
        load_deck(_deck(tmp_path, text))


def test_a_node_without_a_name_is_refused(tmp_path):
    text = GOOD.replace("  - name: second\n", "  - ")
    with pytest.raises(DeckError, match="name"):
        load_deck(_deck(tmp_path, text))


def test_a_missing_file_is_a_deck_error_not_a_crash(tmp_path):
    with pytest.raises(DeckError, match="WORKFLOW.yaml"):
        load_deck(tmp_path / "WORKFLOW.yaml")
