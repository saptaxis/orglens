"""Render a unit into the config scad wants for a container.

The `repos:` block *is* a unit's homes with machine paths attached — this is
the duplication the whole units model exists to delete. `render` is pure: it
never touches disk, so these tests build `Unit` objects directly rather than
going through a declaration.
"""

import yaml

from orglens.scadconfig import render


def test_homes_become_the_repos_block(unit_with_two_homes):
    got = yaml.safe_load(render(unit_with_two_homes))
    assert got["name"] == "orglens"
    assert set(got["repos"]) == {"orglens", "traitful-docs"}


def test_a_home_becomes_an_absolute_path(unit_with_two_homes):
    got = yaml.safe_load(render(unit_with_two_homes))
    for repo in got["repos"].values():
        assert repo["path"].startswith("/")


def test_exactly_one_repo_is_the_workdir(unit_with_two_homes):
    got = yaml.safe_load(render(unit_with_two_homes))
    marked = [n for n, r in got["repos"].items() if r.get("workdir")]
    assert len(marked) == 1


def test_the_named_workdir_wins(unit_with_two_homes):
    got = yaml.safe_load(render(unit_with_two_homes, workdir="traitful-docs"))
    assert got["repos"]["traitful-docs"]["workdir"] is True


def test_a_home_absent_from_this_machine_is_left_out(unit_with_an_absent_home):
    got = yaml.safe_load(render(unit_with_an_absent_home))
    # A container cannot mount what is not here. Omitting it is honest; a path
    # of `None` would fail inside the container instead of before it.
    assert "not-cloned-here" not in got["repos"]


def test_a_runtime_block_is_passed_through_verbatim(unit_with_runtime):
    got = yaml.safe_load(render(unit_with_runtime))
    assert got["python"] == {"version": "3.11", "pyproject": True}


def test_the_generated_file_says_not_to_edit_it(unit_with_two_homes):
    assert "do not edit" in render(unit_with_two_homes).lower()


def test_two_homes_in_one_repository_dedupe_to_the_first(unit_with_a_subpath_home):
    """A subpath home names the same repository as its parent. Keying by the
    repository segment alone would silently overwrite one mount with another
    — dedupe deliberately, and keep the first home's path.
    """
    got = yaml.safe_load(render(unit_with_a_subpath_home))
    assert list(got["repos"]) == ["traitful-docs"]
    assert got["repos"]["traitful-docs"]["path"].endswith("traitful-docs")


def test_workdir_is_marked_by_repo_key_not_by_the_subpath_homes_own_name(
    unit_whose_only_home_is_a_subpath,
):
    """`--workdir traitful-docs` names the repository, and this unit's only
    home for that repository is a subpath (`traitful-docs/docs/projects/x`).
    Comparing the chosen workdir against the home's own name would never
    match, so the entry rendered would carry no workdir at all.
    """
    got = yaml.safe_load(render(unit_whose_only_home_is_a_subpath, workdir="traitful-docs"))
    assert got["repos"]["traitful-docs"].get("workdir") is True


def test_runtime_cannot_clobber_the_generated_repos(unit_with_clobbering_runtime):
    """A declaration's `runtime:` block is scad's words, passed through
    verbatim — but it must not be able to overwrite what `render` generated.
    A `name` or `repos` key inside `runtime:` is silently dropped.
    """
    got = yaml.safe_load(render(unit_with_clobbering_runtime))
    assert got["name"] == "orglens"
    assert set(got["repos"]) == {"orglens"}
