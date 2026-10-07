"""`orglens hide`: units kept off the screen, each with its subtree, until
unhidden. What draws for a person leaves them out and says how many; what
agents and scripts read keeps them; naming one still shows it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from orglens.cli import cli
from orglens.config import Config
from tests.conftest import export_row, fake_scad
from tests.test_cli import _chain_tree


@pytest.fixture
def env(tmp_path):
    """a > b > c, and d beside them."""
    return _chain_tree(tmp_path)


def _run(env, *argv):
    return CliRunner().invoke(cli, list(argv), env=env)


def _config(env) -> Path:
    return Path(env["ORGLENS_CONFIG"])


def _names(output: str) -> set[str]:
    return {w for line in output.splitlines() for w in line.replace("›", " ").split()
            if w in {"a", "b", "c", "d"}}


class TestHideAndUnhide:
    def test_hide_writes_the_list_and_keeps_the_rest_of_the_config(self, env):
        config = _config(env)
        config.write_text("# my roots\n" + config.read_text())
        result = _run(env, "hide", "b")
        assert result.exit_code == 0, result.output
        assert "hidden: b, and 1 unit under them" in result.output
        assert config.read_text().startswith("# my roots\n")
        assert Config.from_yaml(config).hide == ("b",)

    def test_an_unknown_unit_is_refused(self, env):
        result = _run(env, "hide", "nope")
        assert result.exit_code == 1
        assert Config.from_yaml(_config(env)).hide == ()

    def test_unhide_one_and_all(self, env):
        _run(env, "hide", "b", "d")
        assert _run(env, "unhide", "d").exit_code == 0
        assert Config.from_yaml(_config(env)).hide == ("b",)
        assert _run(env, "unhide", "--all").exit_code == 0
        assert Config.from_yaml(_config(env)).hide == ()

    def test_hide_must_be_a_list(self, env):
        config = _config(env)
        config.write_text(config.read_text() + "hide: b\n")
        with pytest.raises(ValueError, match="hide must be a list"):
            Config.from_yaml(config)


class TestWhatDraws:
    def test_list_leaves_out_the_subtree_and_says_how_many(self, env):
        _run(env, "hide", "b")
        out = _run(env, "list").output
        assert _names(out) == {"a", "d"}
        assert "2 hidden" in out

    def test_show_hidden_shows_everything_for_one_run(self, env):
        _run(env, "hide", "b")
        out = _run(env, "list", "--show-hidden").output
        assert _names(out) == {"a", "b", "c", "d"}
        assert "hidden" not in out

    def test_naming_a_hidden_unit_shows_it(self, env):
        _run(env, "hide", "b")
        assert _names(_run(env, "list", "--under", "b").output) == {"b", "c"}
        assert "c" in _names(_run(env, "tree", "b").output)

    def test_tree_status_and_sessions_leave_it_out(self, env, monkeypatch, tmp_path):
        home = tmp_path / "docs" / "projects" / "d"
        monkeypatch.setattr("orglens.sessions.run_scad", fake_scad([
            export_row("sess-d", str(home), n_turns=3, name="d-work")]))
        _run(env, "hide", "d")
        assert "d" not in _names(_run(env, "tree").output)
        assert "d" not in _names(_run(env, "status").output)
        out = _run(env, "sessions").output
        assert "d-work" not in out and "1 hidden" in out
        assert "d-work" in _run(env, "sessions", "d").output

    def test_view_leaves_out_the_cards_and_says_how_many(self, env, tmp_path):
        _run(env, "hide", "b")
        page = tmp_path / "v.html"
        assert _run(env, "view", "--out", str(page), "--no-open").exit_code == 0
        html = page.read_text()
        assert "data-unit='b'" not in html and "data-unit='c'" not in html
        assert "data-unit='a'" in html and ">2 hidden<" in html


class TestWhatAgentsRead:
    def test_tree_json_and_find_keep_hidden_units(self, env):
        _run(env, "hide", "b")
        tree = json.dumps(json.loads(_run(env, "tree", "--json").output))
        assert '"b"' in tree and '"c"' in tree
        found = json.loads(_run(env, "find", "doc", "--json").output)
        assert {"b", "c"} <= {d["unit"] for d in found}
