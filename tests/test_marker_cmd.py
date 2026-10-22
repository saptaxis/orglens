"""`marker` prints a unit's marker, or opens it and checks what was saved."""

import click
import pytest
from click.testing import CliRunner

from orglens.cli import cli
from tests.test_cli import cli_env, units_tree  # noqa: F401


@pytest.fixture
def runner():
    return CliRunner()


class TestMarker:
    def test_it_prints_the_path_and_the_file(self, runner, cli_env, units_tree):  # noqa: F811
        out = runner.invoke(cli, ["marker", "clipcompose"], env=cli_env).output
        assert out.splitlines()[0] == f"# {units_tree / 'projects/clipcompose/.orglens.yml'}"
        assert "unit: clipcompose\n" in out

    def test_with_no_name_it_takes_the_unit_here(
        self, runner, cli_env, units_tree, monkeypatch  # noqa: F811
    ):
        monkeypatch.chdir(units_tree / "projects" / "clipcompose" / "specs")
        assert "unit: clipcompose" in runner.invoke(cli, ["marker"], env=cli_env).output
        monkeypatch.chdir(units_tree.parent)
        assert runner.invoke(cli, ["marker"], env=cli_env).exit_code == 1

    def _edit_to(self, monkeypatch, text):
        def edit(filename=None, **kw):
            open(filename, "w").write(text)
        monkeypatch.setattr(click, "edit", edit)

    def test_edit_saves_and_shows_the_unit(self, runner, cli_env, monkeypatch):  # noqa: F811
        self._edit_to(monkeypatch, "unit: clipcompose\nkind: project\naliases: [clip]\n"
                                   "homes:\n  - clipcompose\n")
        result = runner.invoke(cli, ["marker", "clipcompose", "--edit"], env=cli_env)
        assert result.exit_code == 0
        assert "also:   clip" in result.output

    def test_edit_says_when_it_no_longer_parses(self, runner, cli_env, monkeypatch):  # noqa: F811
        self._edit_to(monkeypatch, "unit: [clipcompose\n")
        result = runner.invoke(cli, ["marker", "clipcompose", "--edit"], env=cli_env)
        assert result.exit_code == 1
        assert "does not parse, so its unit is gone from the tree" in result.output

    def test_edit_says_when_part_of_names_no_unit(self, runner, cli_env, monkeypatch):  # noqa: F811
        self._edit_to(monkeypatch, "unit: clipcompose\nkind: project\npart_of: nobody\n")
        result = runner.invoke(cli, ["marker", "clipcompose", "--edit"], env=cli_env)
        assert result.exit_code == 1
        assert "part_of: nobody names no unit" in result.output
