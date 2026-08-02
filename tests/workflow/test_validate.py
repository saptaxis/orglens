from __future__ import annotations

from orglens.workflow.validate import validate_definition

BASE = {
    "nodes": {
        "brief": {"guard": {"all": ["after:nothing"]}, "writes": ["brief.md"]},
        "draft": {"guard": {"all": ["after:brief"]}, "writes": ["draft.md"]},
    }
}


def test_a_sound_definition_has_no_problems():
    assert validate_definition(BASE) == []


def test_a_node_without_a_guard_is_reported():
    broken = {"nodes": {**BASE["nodes"], "x": {"writes": []}}}
    assert any("guard" in p for p in validate_definition(broken))


def test_an_unknown_prefix_is_reported():
    broken = {"nodes": {**BASE["nodes"], "draft": {"guard": {"all": ["invented"]}}}}
    assert any("invented" in p for p in validate_definition(broken))


def test_after_naming_an_undeclared_node_is_reported():
    broken = {"nodes": {**BASE["nodes"], "draft": {"guard": {"all": ["after:ghost"]}}}}
    assert any("ghost" in p for p in validate_definition(broken))


def test_after_nothing_is_accepted():
    assert validate_definition(BASE) == []


def test_a_node_named_nothing_is_reported():
    broken = {"nodes": {**BASE["nodes"], "nothing": {"guard": {"all": ["after:brief"]}}}}
    assert any("nothing" in p for p in validate_definition(broken))


def test_a_glob_in_writes_is_reported():
    broken = {
        "nodes": {**BASE["nodes"], "draft": {**BASE["nodes"]["draft"], "writes": ["*.md"]}}
    }
    assert any("*.md" in p for p in validate_definition(broken))


def test_two_nodes_claiming_the_same_cursor_are_reported():
    """Decidable without fixtures: only one after: predicate is ever true."""
    broken = {
        "nodes": {
            **BASE["nodes"],
            "other": {"guard": {"all": ["after:brief"]}, "writes": ["x.md"]},
        }
    }
    problems = validate_definition(broken)
    assert any("draft" in p and "other" in p and "after:brief" in p for p in problems)


def test_a_loop_back_edge_is_not_ambiguous():
    """`any` over two cursors is normal — it is how a pipeline repeats."""
    ok = {
        "nodes": {
            "brief": {"guard": {"all": ["after:nothing"]}, "writes": ["b.md"]},
            "draft": {"guard": {"all": ["after:brief"]}, "writes": ["d.md"]},
            "critique": {
                "guard": {"any": ["after:draft", "after:polish"]},
                "writes": ["c.md"],
            },
            "polish": {"guard": {"all": ["after:critique"]}, "writes": ["p.md"]},
        }
    }
    assert validate_definition(ok) == []


def test_a_terminal_literal_is_checked():
    broken = {**BASE, "terminal": {"done": "invented"}}
    assert any("invented" in p for p in validate_definition(broken))


def test_roots_must_be_a_list():
    broken = {**BASE, "roots": "../shared"}
    assert any("roots" in p for p in validate_definition(broken))


def test_every_problem_is_reported_not_just_the_first():
    broken = {
        "nodes": {
            "a": {"guard": {"all": ["after:ghost"]}, "writes": ["*.md"]},
            "nothing": {"guard": "not-a-dict"},
        }
    }
    assert len(validate_definition(broken)) >= 3


def test_malformed_shapes_never_raise():
    for shape in (
        {},
        {"nodes": {}},
        {"nodes": None},
        {"nodes": {"a": "string"}},
        {"nodes": {"a": None}},
        {"nodes": {"a": {"guard": "s"}}},
        {"nodes": {"a": {"guard": {"all": "s"}}}},
        {"terminal": "s", "nodes": {}},
        {"roots": 3, "nodes": {}},
    ):
        assert isinstance(validate_definition(shape), list), shape


# --- fix round 1 ---


def test_a_guard_with_no_recognized_clause_is_reported():
    """A misspelled clause key (`al` for `all`) leaves the guard dict with
    none of `all`/`any`/`none` present. `guards.matches` returns True
    unconditionally for such a dict, so it fires on every packet — check 1
    exists to catch exactly this."""
    broken = {
        "nodes": {"brief": {"guard": {"al": ["after:nothing"]}, "writes": ["brief.md"]}}
    }
    problems = validate_definition(broken)
    assert any("brief" in p and "guard" in p for p in problems)
