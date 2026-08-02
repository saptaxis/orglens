from __future__ import annotations

import pytest

from orglens.workflow.validate import validate_definition

BASE = {
    "nodes": {
        "critique": {
            "diagnoses": True,
            "must_not_modify": ["**"],
            "guard": {"all": ["brief_exists"]},
            "expect": "revise",
        },
        "revise": {"mutates": True, "guard": {"all": ["awaiting_mutation"]}},
    }
}


def test_a_sound_definition_has_no_problems():
    assert validate_definition(BASE) == []


def test_a_node_without_a_guard_is_reported():
    broken = {"nodes": {**BASE["nodes"], "x": {"mutates": True}}}
    assert any("guard" in p for p in validate_definition(broken))


def test_an_unknown_predicate_is_reported():
    broken = {"nodes": {**BASE["nodes"], "revise": {"guard": {"all": ["invented"]}}}}
    assert any("invented" in p for p in validate_definition(broken))


def test_a_generated_predicate_is_known():
    """last_diagnostic_is_critique exists because critique declares diagnoses."""
    ok = {
        "nodes": {
            **BASE["nodes"],
            "audit": {
                "diagnoses": True,
                "must_not_modify": ["**"],
                "guard": {"all": ["last_diagnostic_is_critique"]},
            },
        }
    }
    assert validate_definition(ok) == []


def test_a_glob_in_writes_is_reported():
    """Rule 4: reads loose, writes exact. A `writes` entry is a literal
    filename decided before the pass runs, never a pattern resolved after."""
    broken = {
        "nodes": {**BASE["nodes"], "revise": {**BASE["nodes"]["revise"], "writes": ["draft-*.md"]}}
    }
    assert any("glob" in p for p in validate_definition(broken))


@pytest.mark.parametrize("entry", ["draft-*.md", "draft?.md", "draft-[0-9].md"])
def test_every_glob_character_in_writes_is_reported(entry: str):
    broken = {"nodes": {**BASE["nodes"], "revise": {**BASE["nodes"]["revise"], "writes": [entry]}}}
    assert any("glob" in p for p in validate_definition(broken))


def test_a_literal_write_is_not_reported():
    ok = {"nodes": {**BASE["nodes"], "revise": {**BASE["nodes"]["revise"], "writes": ["draft.md"]}}}
    assert validate_definition(ok) == []


def test_an_expect_list_names_every_acceptable_successor():
    """I1: `expect` may be a single node name or a list of them — a node
    with two legitimate successors (revise, reachable from either a
    critique or an audit cycle) cannot be pinned to just one."""
    ok = {
        "nodes": {
            **BASE["nodes"],
            "revise": {**BASE["nodes"]["revise"], "expect": ["critique", "revise"]},
        }
    }
    # "revise" names itself — every entry in the list is checked, not just
    # the first.
    assert any("itself" in p for p in validate_definition(ok))

    sound = {
        "nodes": {
            **BASE["nodes"],
            "revise": {**BASE["nodes"]["revise"], "expect": ["critique"]},
        }
    }
    assert validate_definition(sound) == []


def test_a_node_that_expects_itself_is_reported():
    """The livelock check. adopt declared expect: adoptable and ran forever."""
    broken = {
        "nodes": {**BASE["nodes"], "revise": {**BASE["nodes"]["revise"], "expect": "revise"}}
    }
    assert any("itself" in p for p in validate_definition(broken))


def test_an_expect_naming_no_declared_node_is_reported():
    broken = {
        "nodes": {**BASE["nodes"], "critique": {**BASE["nodes"]["critique"], "expect": "ghost"}}
    }
    assert any("ghost" in p for p in validate_definition(broken))


def test_an_unknown_terminal_predicate_is_reported():
    broken = {**BASE, "terminal": {"published": "invented"}}
    assert any("invented" in p for p in validate_definition(broken))


def test_a_node_cannot_both_mutate_and_diagnose():
    broken = {
        "nodes": {
            **BASE["nodes"],
            "revise": {**BASE["nodes"]["revise"], "diagnoses": True},
        }
    }
    assert any("both" in p for p in validate_definition(broken))


def test_a_diagnostic_must_protect_the_artifact():
    broken = {
        "nodes": {
            **BASE["nodes"],
            "critique": {
                "diagnoses": True,
                "guard": {"all": ["brief_exists"]},
                "expect": "revise",
            },
        }
    }
    assert any("must_not_modify" in p for p in validate_definition(broken))


# `derive_next_node` does not catch the KeyError guard evaluation raises for
# an unknown predicate; `validate_definition` is the only gate against a
# malformed definition, so it must survive every shape below without
# raising rather than crashing the caller it exists to protect.
MALFORMED_SHAPES = [
    pytest.param({}, id="empty workflow"),
    pytest.param({"nodes": {}}, id="empty nodes"),
    pytest.param({"nodes": None}, id="nodes is None"),
    pytest.param({"nodes": {"x": "not-a-dict"}}, id="node value is a string"),
    pytest.param({"nodes": {"x": None}}, id="node value is None"),
    pytest.param({"nodes": {"x": {"guard": "not-a-dict"}}}, id="guard is a string"),
    pytest.param({"nodes": {"x": {"guard": None}}}, id="guard is None"),
    pytest.param(
        {"nodes": {"x": {"guard": {"all": "brief_exists"}}}},
        id="guard clause value is a string",
    ),
    pytest.param(
        {"nodes": {}, "terminal": "not-a-dict"}, id="terminal present but not a dict"
    ),
    pytest.param(
        {
            "nodes": {
                "x": "not-a-dict",
                "y": {"guard": {"all": "brief_exists"}},
                "z": {"mutates": True, "diagnoses": True, "guard": {"all": []}},
            },
            "terminal": "not-a-dict",
        },
        id="several distinct problems at once",
    ),
]


@pytest.mark.parametrize("workflow", MALFORMED_SHAPES)
def test_malformed_shapes_are_reported_not_raised(workflow):
    problems = validate_definition(workflow)
    assert isinstance(problems, list)


def test_a_node_that_is_not_a_mapping_is_reported():
    broken = {"nodes": {"x": "not-a-dict"}}
    assert any("x" in p for p in validate_definition(broken))


def test_a_guard_clause_that_is_not_a_list_is_reported():
    broken = {"nodes": {"x": {"guard": {"all": "brief_exists"}}}}
    assert validate_definition(broken) != []


def test_a_terminal_that_is_not_a_mapping_is_reported():
    broken = {"nodes": {}, "terminal": "not-a-dict"}
    assert any("terminal" in p for p in validate_definition(broken))


def test_several_distinct_problems_are_all_returned():
    broken = {
        "nodes": {
            "x": "not-a-dict",
            "y": {"guard": {"all": "brief_exists"}},
            "z": {"mutates": True, "diagnoses": True, "guard": {"all": []}},
        },
        "terminal": "not-a-dict",
    }
    problems = validate_definition(broken)
    assert len(problems) >= 4
