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


KINDS = {"personal": "organization", "traitful": "organization",
         "lwp": "research", "e1": "experiment", "e2": "experiment", "lander": "project",
         "orglens": "project", "dotfiles": "project", "acme": "client", "gasco": "project"}
SHAPE = {"personal": None, "traitful": None, "lwp": "personal", "e1": "lwp", "e2": "lwp",
         "lander": "lwp", "orglens": "personal", "dotfiles": "personal",
         "acme": "traitful", "gasco": "traitful"}


def test_draw_groups_each_top_nodes_units_by_kind_with_lines_and_spacing():
    t = tree.build(SHAPE)
    assert tree.draw(t, kind=KINDS.get) == [
        "personal",
        "├── project",
        "│   ├── dotfiles",
        "│   └── orglens",
        "│",
        "└── research",
        "    └── lwp",
        "        ├── experiment",
        "        │   ├── e1",
        "        │   └── e2",
        "        └── project",
        "            └── lander",
        "",
        "traitful",
        "├── client",
        "│   └── acme",
        "│",
        "└── project",
        "    └── gasco",
    ]


def test_below_the_top_one_kind_needs_no_heading():
    t = tree.build({"org": None, "prog": "org", "e1": "prog", "e2": "prog"})
    kinds = {"org": "organization", "prog": "research", "e1": "experiment", "e2": "experiment"}
    assert tree.draw(t, kind=kinds.get) == [
        "org", "└── research", "    └── prog", "        ├── e1", "        └── e2",
    ]


def test_a_status_follows_the_name_after_a_separator():
    t = tree.build({"org": None, "p": "org"})
    kinds = {"org": "organization", "p": "project"}
    statuses = {"org": "Opened", "p": "Plan 02 complete"}
    assert tree.draw(t, kind=kinds.get, status=statuses.get) == [
        "org — Opened", "└── project", "    └── p — Plan 02 complete",
    ]


def test_draw_from_one_unit_is_its_subtree():
    t = tree.build(SHAPE)
    assert tree.draw(t, kind=KINDS.get, start="lwp") == [
        "lwp", "├── experiment", "│   ├── e1", "│   └── e2", "│", "└── project", "    └── lander",
    ]


def test_draw_marks_an_unknown_parent_and_a_cycle():
    t = tree.build({"a": "nosuch", "b": "c", "c": "b"})
    assert tree.draw(t, kind=lambda n: "project") == [
        "a  (part of nosuch: no such unit)",
        "",
        "b  (in a cycle: b > c > b)",
        "",
        "c  (in a cycle: b > c > b)",
    ]
