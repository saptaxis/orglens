from __future__ import annotations

from orglens.workflow.predicates import PREDICATE_NAMES
from orglens.workflow.validate import validate_definition, validate_edges
from tests.workflow.test_derive import WORKFLOW


def test_valid_definition_has_no_problems():
    assert validate_definition(WORKFLOW) == []


def test_unknown_predicate_is_reported():
    broken = {
        **WORKFLOW,
        "nodes": {"x": {"guard": {"all": ["not_a_predicate"]}}},
    }
    problems = validate_definition(broken)
    assert any("not_a_predicate" in p for p in problems)


def test_edge_to_undeclared_node_is_reported():
    broken = {**WORKFLOW, "edges": ["brief -> nowhere"]}
    problems = validate_definition(broken)
    assert any("nowhere" in p for p in problems)


def test_predicate_names_are_the_closed_vocabulary():
    for spec in WORKFLOW["nodes"].values():
        guard = spec.get("guard")
        if not isinstance(guard, dict):
            continue
        for clause in ("all", "any", "none"):
            for name in guard.get(clause, []):
                assert name in PREDICATE_NAMES


def test_edges_are_checked_against_fixtures():
    fixtures = [
        ({"writing-brief.md": "# Brief", "draft.md": "prose"}, "critique"),
        (
            {
                "writing-brief.md": "# Brief",
                "draft.md": "prose",
                "decisions-01.md": "## Accept\n- a\n",
            },
            "revise",
        ),
    ]
    assert validate_edges(WORKFLOW, fixtures) == []


def test_a_fixture_that_derives_the_wrong_node_is_reported():
    fixtures = [({"writing-brief.md": "# Brief"}, "critique")]
    problems = validate_edges(WORKFLOW, fixtures)
    assert len(problems) == 1
    assert "expected critique" in problems[0]
    assert "got draft" in problems[0]
