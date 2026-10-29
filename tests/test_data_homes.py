"""A home marked `data` is the unit's, but holds no documents to search."""

import json
import os
import time

import pytest
from click.testing import CliRunner

from orglens import documents
from orglens.check import run as check
from orglens.cli import cli
from orglens.declaration import MARKER, read_marker
from orglens.units import Registry
from tests.test_cli import _roots_config


@pytest.fixture
def tree(tmp_path):
    docs = tmp_path / "docs" / "projects" / "papers"
    docs.mkdir(parents=True)
    (docs / MARKER).write_text(
        "home: papers-docs\nunit: papers\nkind: project\n"
        "homes:\n  - papers-docs\n  - papers-data: data\n")
    (docs / "overview.md").write_text("# Papers\n\n> **Status:** Going.\n")
    (docs / "notes.md").write_text("# Notes\n")
    data = tmp_path / "data" / "papers-data"
    (data / "runs").mkdir(parents=True)
    (data / "runs" / "out.md").write_text("# A run\n")
    (data / "README.md").write_text("# Data\n")
    return tmp_path


@pytest.fixture
def env(tree):
    return _roots_config(tree, [tree / "docs", tree / "data"])


def test_the_marker_reads_names_data_and_what_it_cannot(tmp_path):
    (tmp_path / MARKER).write_text(
        "unit: x\nhomes:\n  - a\n  - b: data\n  - c: other\n  - [d]\n")
    marker = read_marker(tmp_path)
    assert marker.homes == ("a", "b")
    assert marker.data_homes == ("b",)
    assert marker.bad_homes == ("{'c': 'other'}", "['d']")


def test_a_data_home_is_the_units_but_not_searched(tree, grammar):
    unit = Registry([tree / "docs", tree / "data"], grammar).resolve("papers")
    data = tree / "data" / "papers-data"
    assert [h.name for h in unit.homes if h.data] == ["papers-data"]
    assert data in unit.every_path and data not in unit.paths
    assert all(data not in p.parents for p in documents.loose(unit))


def test_where_marks_it(env):
    out = CliRunner().invoke(cli, ["where", "papers"], env=env).output
    assert "papers-data" in out and ", data)" in out


def test_the_snapshot_lists_it_as_a_home_and_none_of_its_files(env, tree):
    out = CliRunner().invoke(cli, ["snapshot", "--json"], env=env).output
    unit = next(u for u in json.loads(out)["units"] if u["name"] == "papers")
    assert str((tree / "data" / "papers-data").resolve()) in unit["homes"]
    listed = [f["path"] for held in unit["files"].values() for f in held]
    assert listed and not any("papers-data" in p for p in listed)


def test_a_change_inside_it_leaves_the_snapshot_fresh(env, tree):
    past = time.time() - 60
    for path in [tree, *tree.rglob("*")]:
        os.utime(path, (past, past))
    CliRunner().invoke(cli, ["snapshot"], env=env)
    (tree / "data" / "papers-data" / "runs" / "new.md").write_text("# New\n")
    assert CliRunner().invoke(cli, ["snapshot", "--check"], env=env).exit_code == 0


def test_check_reports_an_entry_that_is_not_a_home(tmp_path, grammar):
    home = tmp_path / "docs" / "x"
    home.mkdir(parents=True)
    (home / MARKER).write_text("home: x\nunit: x\nkind: project\nhomes:\n  - x: skip\n")
    assert check(Registry([tmp_path / "docs"], grammar)).bad_homes == [("x", "{'x': 'skip'}")]
