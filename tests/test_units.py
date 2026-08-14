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


def test_a_matching_directory_inside_a_declared_home_is_not_a_candidate(two_root_tree, tmp_path):
    # `expt-*` is a single-segment pattern, so this directory matches it even
    # sitting inside a declared unit's home — Path.match's separator rule does
    # not save us here. Only excluding what is *under* a claimed home does,
    # which is what this test exists to hold in place.
    #
    # (`docs/projects/orglens/specs` was tried here first and looked right,
    # but it turned out to pass on the separator fix alone: `specs` sits two
    # segments below `projects`, so `Path.match('projects/*')` already
    # rejects it without the containment exclusion ever being exercised.
    # `expt-*` is one segment, so it matches regardless of nesting depth —
    # the containment exclusion is the only thing left that can stop it.)
    (tmp_path / "traitful-docs" / "docs" / "projects" / "orglens" / "expt-1").mkdir(
        parents=True, exist_ok=True
    )
    found = two_root_tree.candidates()
    assert not any(p.name == "expt-1" for p in found)


def test_a_grandchild_of_a_matched_directory_is_not_a_candidate(two_root_tree, tmp_path):
    """`fnmatch`'s `*` used to cross `/`, so `projects/*` matched two levels
    deep as readily as one. `reelmill` is undeclared and owned by nothing, so
    only `Path.match`'s right-anchoring — not the ownership exclusion — can
    be what keeps its subdirectory out.
    """
    nested = tmp_path / "traitful-docs" / "docs" / "projects" / "reelmill" / "subdir"
    nested.mkdir(parents=True)

    found = two_root_tree.candidates()

    assert any(p.name == "reelmill" for p in found)
    assert not any(p.name == "subdir" for p in found)


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


def _declare(root: Path, dirname: str, unit_name: str) -> None:
    """A minimal declared unit: one home, named after its own directory."""
    home = root / dirname
    home.mkdir(parents=True)
    (home / MARKER).write_text(
        f"home: {dirname}\nunit: {unit_name}\nkind: project\nhomes:\n  - {dirname}\n"
    )


class TestResolveFallbacks:
    """`resolve`'s three passes came across from the deleted `Topology.resolve`
    unchanged, and are live in `orglens where <name>` — an exact match always
    existed as its own test, but the prefix, substring, ambiguous and
    no-match branches never got one of their own once `test_topology.py`
    went with the module it was written against.
    """

    @pytest.fixture
    def registry(self, tmp_path, grammar):
        root = tmp_path / "root"
        _declare(root, "orglens", "orglens")
        _declare(root, "orglens-web", "orglens-web")
        return Registry([root], grammar)

    def test_exact_wins_over_a_longer_prefix_match(self, registry):
        assert registry.resolve("orglens").name == "orglens"

    def test_an_unambiguous_prefix_resolves(self, registry):
        assert registry.resolve("orglens-w").name == "orglens-web"

    def test_an_unambiguous_substring_resolves(self, tmp_path, grammar):
        root = tmp_path / "root"
        _declare(root, "the-orglens-thing", "the-orglens-thing")
        registry = Registry([root], grammar)

        assert registry.resolve("orglens").name == "the-orglens-thing"

    def test_an_ambiguous_prefix_names_every_match(self, tmp_path, grammar):
        root = tmp_path / "root"
        _declare(root, "web-app", "web-app")
        _declare(root, "web-api", "web-api")
        registry = Registry([root], grammar)

        with pytest.raises(ValueError) as excinfo:
            registry.resolve("web")

        assert "web-app" in str(excinfo.value)
        assert "web-api" in str(excinfo.value)

    def test_no_match_lists_what_is_available(self, registry):
        with pytest.raises(ValueError) as excinfo:
            registry.resolve("nothing-like-that")

        assert "orglens" in str(excinfo.value)
        assert "orglens-web" in str(excinfo.value)
