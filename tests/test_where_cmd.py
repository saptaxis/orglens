"""`where` named answers only the unit, with its marker and each home's commit state."""

import pytest
from click.testing import CliRunner

from orglens.cli import cli
from tests.test_cli import _declare, _git, _roots_config, cli_env, units_tree  # noqa: F401


@pytest.fixture
def runner():
    return CliRunner()


class TestWhere:
    def test_a_named_unit_skips_the_roots_and_here(self, runner, cli_env, units_tree):  # noqa: F811
        out = runner.invoke(cli, ["where", "clipcompose"], env=cli_env).output
        assert "roots:" not in out and "here:" not in out
        assert out.startswith("unit:   clipcompose  (project)")
        assert f"marker: {units_tree / 'projects/clipcompose/.orglens.yml'}" in out

    def test_bare_with_many_roots_counts_them_and_roots_lists_them(self, runner, tmp_path):
        roots = []
        for name in ("a", "b"):
            _declare(tmp_path / name / name, name, "project")
            roots.append(tmp_path / name)
        env = _roots_config(tmp_path, roots)
        assert "roots:  2, --roots lists them" in runner.invoke(cli, ["where"], env=env).output
        listed = runner.invoke(cli, ["where", "a", "--roots"], env=env).output
        assert str(roots[1]) in listed
        assert "unit:   a  (project)" in listed

    def test_a_home_inside_a_larger_repo_names_it(self, runner, tmp_path):
        docs = tmp_path / "docs"
        _declare(docs / "projects" / "clip", "clip", "project")
        _git("init", "-q", cwd=docs)
        out = runner.invoke(cli, ["where", "clip"], env=_roots_config(tmp_path, [docs])).output
        assert "1 uncommitted, in the docs repo" in out
