from __future__ import annotations

import pytest

from orglens.workflow.guards import matches
from orglens.workflow.result import DerivationResult, Outcome

FACTS = {"a": True, "b": True, "c": False}


def test_all_requires_every_member():
    assert matches({"all": ["a", "b"]}, FACTS) is True
    assert matches({"all": ["a", "c"]}, FACTS) is False


def test_any_requires_one_member():
    assert matches({"any": ["a", "c"]}, FACTS) is True
    assert matches({"any": ["c"]}, FACTS) is False


def test_none_requires_no_member():
    assert matches({"none": ["c"]}, FACTS) is True
    assert matches({"none": ["a"]}, FACTS) is False


def test_clauses_combine_conjunctively():
    assert matches({"all": ["a"], "any": ["b", "c"], "none": ["c"]}, FACTS) is True
    assert matches({"all": ["a"], "none": ["b"]}, FACTS) is False


def test_empty_guard_never_matches():
    assert matches({}, FACTS) is False


def test_fallback_string_never_matches_directly():
    """`fallback` is positional, resolved by precedence, not by evaluation."""
    assert matches("fallback", FACTS) is False


def test_unknown_predicate_raises():
    with pytest.raises(KeyError):
        matches({"all": ["nonexistent"]}, FACTS)


def test_result_defaults():
    r = DerivationResult(outcome=Outcome.WAITING, node=None, reason="gate")
    assert r.outcome == "waiting"
    assert r.matched == []
