"""The tree `part_of` builds: one reading of it, used by everything."""

from orglens import tree


def test_units_with_no_parent_are_all_top_level():
    t = tree.build({"a": None, "b": None})
    assert t.top == ["a", "b"]
    assert t.parent == {}


def test_a_chain_hangs_each_unit_under_the_one_it_names():
    t = tree.build({"a": "b", "b": "c", "c": None})
    assert t.top == ["c"]
    assert t.parent == {"a": "b", "b": "c"}
    assert t.children == {"c": ["b"], "b": ["a"]}
    assert tree.below(t, "c") == ["c", "b", "a"]
    assert tree.below(t, "b") == ["b", "a"]


def test_below_is_depth_first_and_sorted_at_each_level():
    t = tree.build({"org": None, "z": "org", "a": "org", "a1": "a"})
    assert tree.below(t, "org") == ["org", "a", "a1", "z"]


def test_a_parent_that_is_no_unit_leaves_the_unit_top_level_and_named():
    t = tree.build({"a": "nosuch"})
    assert t.top == ["a"]
    assert t.unknown == {"a": "nosuch"}
    assert t.parent == {}


def test_a_cycle_is_top_level_and_listed_once():
    t = tree.build({"a": "b", "b": "a"})
    assert t.top == ["a", "b"]
    assert t.cycles == [["a", "b"]]
    assert t.parent == {}


def test_a_unit_naming_itself_is_a_cycle_of_one():
    t = tree.build({"a": "a"})
    assert t.top == ["a"]
    assert t.cycles == [["a"]]


def test_a_chain_leading_into_a_cycle_keeps_its_parent():
    t = tree.build({"a": "b", "b": "a", "d": "a"})
    assert t.parent == {"d": "a"}
    assert "d" not in t.top
    assert tree.below(t, "a") == ["a", "d"]


def test_draw_gives_every_top_node_and_its_subtree_with_branches():
    t = tree.build({"org": None, "prog": "org", "e1": "prog", "e2": "prog",
                    "client": "org", "solo": None})
    lines = tree.draw(t, label=lambda n: n.upper())
    assert lines == [
        "ORG",
        "├── CLIENT",
        "└── PROG",
        "    ├── E1",
        "    └── E2",
        "SOLO",
    ]


def test_draw_from_one_unit_is_its_subtree():
    t = tree.build({"org": None, "prog": "org", "e1": "prog"})
    assert tree.draw(t, label=str, start="prog") == ["prog", "└── e1"]


def test_draw_marks_an_unknown_parent_and_a_cycle():
    t = tree.build({"a": "nosuch", "b": "c", "c": "b"})
    assert tree.draw(t, label=str) == [
        "a  (part of nosuch: no such unit)",
        "b  (in a cycle: b > c > b)",
        "c  (in a cycle: b > c > b)",
    ]
