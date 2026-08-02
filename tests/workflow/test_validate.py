from __future__ import annotations

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
