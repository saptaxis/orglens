from pathlib import Path

import pytest

from orglens.declaration import MARKER
from orglens.units import Registry


def test_a_declaration_makes_a_unit(two_root_tree):
    units = two_root_tree.units()
    assert [u.name for u in units] == ["orglens"]
    assert units[0].kind == "project"


def test_a_unit_carries_all_its_homes(two_root_tree):
    unit = two_root_tree.resolve("orglens")
    assert {h.name for h in unit.homes} == {
        "orglens", "traitful-docs/docs/projects/orglens"
    }
    assert all(h.path is not None for h in unit.homes)


def test_resolution_walks_up_from_any_home(two_root_tree, tmp_path):
    inside_code = tmp_path / "code" / "orglens"
    assert two_root_tree.at(inside_code).name == "orglens"


def test_resolution_walks_up_from_a_subdirectory(two_root_tree, tmp_path):
    deep = tmp_path / "traitful-docs" / "docs" / "projects" / "orglens"
    assert two_root_tree.at(deep).name == "orglens"


def test_a_directory_in_no_home_resolves_to_nothing(two_root_tree, tmp_path):
    assert two_root_tree.at(tmp_path) is None


def test_undeclared_folders_matching_a_pattern_are_candidates(two_root_tree, tmp_path):
    found = two_root_tree.candidates()
    assert any(p.name == "reelmill" for p in found)
    assert not any(p.name == "orglens" for p in found)


def test_part_of_replaces_folder_nesting(tmp_path, grammar):
    docs = tmp_path / "docs"
    parent = docs / "research" / "physics-priors"
    child = docs / "projects" / "expt-5"     # deliberately NOT nested inside
    for d, body in (
        (parent, "home: p\nunit: physics-priors\nkind: research-program\nhomes:\n  - p\n"),
        (child, "home: c\nunit: expt-5\nkind: experiment\n"
                "part_of: physics-priors\nhomes:\n  - c\n"),
    ):
        d.mkdir(parents=True)
        (d / MARKER).write_text(body)
    (tmp_path / "p").mkdir()
    (tmp_path / "c").mkdir()

    registry = Registry([docs, tmp_path], grammar)
    parent_unit = registry.resolve("physics-priors")
    assert [u.name for u in registry.parts_of(parent_unit)] == ["expt-5"]


def test_a_missing_declaration_never_hides_a_directory(two_root_tree, tmp_path):
    # reelmill has no declaration and is not a unit — and is still reported.
    assert not any(u.name == "reelmill" for u in two_root_tree.units())
    assert any(p.name == "reelmill" for p in two_root_tree.candidates())
