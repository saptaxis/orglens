import pytest

from orglens.declaration import MARKER
from orglens.propose import propose
from orglens.units import Registry


@pytest.fixture
def tree(tmp_path, grammar):
    docs = tmp_path / "docs"
    for p in ("projects/parametric-lunar-lander",
              "research/physics-priors/expt-1-agent-behavior",
              "clients/acme"):
        (docs / p).mkdir(parents=True)
    # The docs root is itself a repository, as the real tree's is. A bare
    # `mkdir` is enough: `scan_roots` only shells out to git for children it
    # walks, never for a root itself, so nothing runs git against this.
    (docs / ".git").mkdir()
    (tmp_path / "code" / "parametric-lunar-lander").mkdir(parents=True)
    # A declared unit for `physics-priors`, so `registry.at()` has a marker to
    # find walking up from something it contains — `part_of` names a unit
    # that exists, never a bare directory name.
    (docs / "research" / "physics-priors" / MARKER).write_text(
        "home: physics-priors\n"
        "unit: physics-priors\n"
        "kind: research-program\n"
        "homes:\n  - physics-priors\n"
    )
    return Registry([docs, tmp_path / "code"], grammar)


def test_kind_comes_from_where_the_folder_sits(tree, tmp_path):
    got = propose(tmp_path / "docs" / "projects" / "parametric-lunar-lander", tree)
    assert got.unit == "parametric-lunar-lander"
    assert got.kind == "project"


def test_a_same_named_repository_becomes_a_code_home(tree, tmp_path):
    got = propose(tmp_path / "docs" / "projects" / "parametric-lunar-lander", tree)
    assert "parametric-lunar-lander" in got.homes
    # and the folder itself is always a home
    assert any("projects/parametric-lunar-lander" in h for h in got.homes)


def test_part_of_comes_from_what_contains_it(tree, tmp_path):
    got = propose(
        tmp_path / "docs" / "research" / "physics-priors" / "expt-1-agent-behavior",
        tree,
    )
    assert got.part_of == "physics-priors"
    assert got.kind == "experiment"


def test_no_containing_unit_means_no_part_of(tree, tmp_path):
    assert propose(tmp_path / "docs" / "clients" / "acme", tree).part_of is None


def test_every_guess_says_what_it_was_inferred_from(tree, tmp_path):
    got = propose(tmp_path / "docs" / "clients" / "acme", tree)
    assert "kind" in got.why
    assert "clients" in got.why["kind"]


def test_a_folder_matching_no_pattern_still_proposes_something(tree, tmp_path):
    loose = tmp_path / "docs" / "loose-thing"
    loose.mkdir()
    got = propose(loose, tree)
    assert got.unit == "loose-thing"
    assert got.kind == ""            # unknown, not invented
    assert "kind" in got.why         # and it says so
