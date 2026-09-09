"""`orglens declare` — turning a proposal into a declaration, plus `start`
offering it when a name looks like a candidate but is not yet declared.

Position is a good suggestion and a bad fact: the difference is whether a
person says yes. So every path here goes through the fixture's real docs
root (`two_root_tree_config.roots[0]`) — `registry.candidates()` matches
against the sweep of the roots, and a target outside them is invisible to
that sweep no matter how plausible its name looks.
"""

from __future__ import annotations

import yaml
from click.testing import CliRunner

from orglens.cli import cli
from orglens.declaration import MARKER
from orglens.units import Registry


def test_declare_writes_what_it_proposed(tmp_path, two_root_tree_config):
    target = two_root_tree_config.roots[0] / "projects" / "reelmill"
    target.mkdir(parents=True, exist_ok=True)
    result = CliRunner().invoke(cli, ["declare", str(target), "--yes"])
    assert result.exit_code == 0
    written = yaml.safe_load((target / MARKER).read_text())
    assert written["unit"] == "reelmill"
    assert written["kind"] == "project"


def test_declare_shows_its_reasoning_before_asking(tmp_path, two_root_tree_config):
    target = two_root_tree_config.roots[0] / "projects" / "reelmill"
    target.mkdir(parents=True, exist_ok=True)
    result = CliRunner().invoke(cli, ["declare", str(target)], input="n\n")
    # The human is confirming an inference, so the inference has to be visible.
    assert "matches" in result.output
    assert not (target / MARKER).exists()


def test_declare_refuses_to_overwrite_an_existing_declaration(tmp_path,
                                                             two_root_tree_config):
    target = two_root_tree_config.roots[0] / "projects" / "already"
    target.mkdir(parents=True, exist_ok=True)
    (target / MARKER).write_text("unit: already\nkind: project\nhomes:\n  - x\n")
    result = CliRunner().invoke(cli, ["declare", str(target), "--yes"])
    assert result.exit_code != 0
    assert "already declared" in result.output.lower()


def test_start_on_an_undeclared_name_offers_to_declare(tmp_path, monkeypatch,
                                                       two_root_tree_config):
    monkeypatch.setattr("orglens.cli.EVENTS_DIR", tmp_path / "events")
    (two_root_tree_config.roots[0] / "projects" / "newthing").mkdir(
        parents=True, exist_ok=True
    )
    result = CliRunner().invoke(cli, ["start", "newthing"], input="n\n")
    assert "not declared" in result.output.lower()
    assert "declare it and start?" in result.output


def test_start_on_a_name_matching_nothing_says_so_plainly(tmp_path, monkeypatch,
                                                          two_root_tree_config):
    result = CliRunner().invoke(cli, ["start", "no-such-thing-anywhere"])
    assert result.exit_code != 0
    assert "no unit" in result.output.lower()


def test_declared_home_resolves_by_marker_not_by_a_shadowed_name(tmp_path, grammar,
                                                                 monkeypatch):
    """`_home_name` computes a repository-relative name for the declaring
    directory — a fact, not a guess. If `_write_declaration` drops it, the
    marker carries no `home:` key, and the declaring directory (named the
    same as the unit) is free to win the `name` rung of `resolve_home` for
    its *sibling* code home too, collapsing both proposed homes onto the
    docs directory and losing the actual code repository.

    The declaring directory sits under a repository (`traitful-docs`, marked
    only by a bare `.git`) so its own home name is the repo-relative form
    `traitful-docs/docs/projects/myunit`, distinct from the bare `myunit`
    the sibling code repository is named — the exact shape `propose` builds
    when a same-named code home is found.
    """
    docs_repo = tmp_path / "traitful-docs"
    (docs_repo / ".git").mkdir(parents=True)
    docs_root = docs_repo / "docs"
    target = docs_root / "projects" / "myunit"
    target.mkdir(parents=True)

    code_root = tmp_path / "code"
    code_home = code_root / "myunit"
    (code_home / ".git").mkdir(parents=True)

    config = tmp_path / "config.yaml"
    config.write_text(f"roots:\n  - {docs_root}\n  - {code_root}\n")
    monkeypatch.setenv("ORGLENS_CONFIG", str(config))

    result = CliRunner().invoke(cli, ["declare", str(target), "--yes"])
    assert result.exit_code == 0

    registry = Registry([docs_root, code_root], grammar)
    unit = registry.resolve("myunit")
    by_name = {h.name: h for h in unit.homes}
    assert by_name["myunit"].path == code_home
