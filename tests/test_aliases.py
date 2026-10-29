"""A unit answers to other names: the marker's `aliases:`."""

import json

import pytest
from click.testing import CliRunner

from orglens import complete
from orglens.check import run as check
from orglens.cli import cli
from orglens.declaration import MARKER, read_marker
from orglens.units import Registry


def _unit(root, name, extra=""):
    home = root / "projects" / name
    home.mkdir(parents=True)
    (home / MARKER).write_text(f"home: {name}\nunit: {name}\nkind: project\n{extra}")
    (home / "overview.md").write_text("# Overview\n\n> **Status:** Going.\n")
    return home


@pytest.fixture
def tree(tmp_path, grammar):
    root = tmp_path / "docs"
    _unit(root, "scoped-agent-dispatch", "aliases: [scad]\n")
    _unit(root, "scaffold")
    return Registry([root], grammar)


@pytest.fixture
def env(tmp_path, tree):
    config = tmp_path / "config.yaml"
    config.write_text(f"roots:\n  - {tree.roots[0]}\n")
    return {"ORGLENS_CONFIG": str(config)}


def test_the_marker_reads_a_list_or_one_bare_name(tmp_path):
    (tmp_path / MARKER).write_text("unit: x\naliases: y\n")
    assert read_marker(tmp_path).aliases == ("y",)
    (tmp_path / MARKER).write_text("unit: x\naliases: [y, z]\n")
    assert read_marker(tmp_path).aliases == ("y", "z")
    (tmp_path / MARKER).write_text("unit: x\naliases: {y: 1}\n")
    assert read_marker(tmp_path).aliases == ()


def test_an_alias_resolves_exactly(tree):
    # `scad` is also a prefix of `scaffold`; the alias wins as an exact name.
    assert tree.resolve("scad").name == "scoped-agent-dispatch"


def test_the_units_own_name_wins_over_an_alias(tmp_path, grammar):
    root = tmp_path / "docs"
    _unit(root, "scad")
    _unit(root, "scoped-agent-dispatch", "aliases: [scad]\n")
    assert Registry([root], grammar).resolve("scad").name == "scad"


def test_an_alias_matches_by_prefix_as_a_name_does(tree):
    assert tree.resolve("scoped").name == "scoped-agent-dispatch"
    with pytest.raises(ValueError, match="multiple"):
        tree.resolve("sca")


def test_where_takes_an_alias_and_names_them(env):
    result = CliRunner().invoke(cli, ["where", "scad"], env=env)
    assert "unit:   scoped-agent-dispatch" in result.output
    assert "also:   scad" in result.output


def test_list_shows_them(env):
    result = CliRunner().invoke(cli, ["list"], env=env)
    assert "scoped-agent-dispatch [scad]" in result.output


def test_the_snapshot_carries_them(env):
    result = CliRunner().invoke(cli, ["snapshot", "--json"], env=env)
    units = {u["name"]: u for u in json.loads(result.output)["units"]}
    assert units["scoped-agent-dispatch"]["aliases"] == ["scad"]
    assert units["scaffold"]["aliases"] == []
    text = CliRunner().invoke(cli, ["snapshot", "--stdout"], env=env).output
    assert "Also: scad" in text


def test_completion_offers_an_alias_with_its_unit_as_the_hint(monkeypatch):
    monkeypatch.setattr(complete, "_snapshot_data", lambda: {"units": [
        {"name": "scoped-agent-dispatch", "aliases": ["scad"], "status": "Going"}]})
    offered = dict(complete.unit_names())
    assert offered["scad"] == "scoped-agent-dispatch: Going"
    assert complete._canonical("scad") == "scoped-agent-dispatch"


def test_check_reports_an_alias_claimed_twice(tmp_path, grammar):
    root = tmp_path / "docs"
    _unit(root, "a", "aliases: [x, b]\n")
    _unit(root, "b")
    _unit(root, "c", "aliases: [x]\n")
    _unit(root, "d", "aliases: [d]\n")
    assert check(Registry([root], grammar)).clashes == [
        ("b", ["a", "b"]), ("x", ["a", "c"])]
