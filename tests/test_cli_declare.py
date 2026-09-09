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
    assert "declare" in result.output.lower()


def test_start_on_a_name_matching_nothing_says_so_plainly(tmp_path, monkeypatch,
                                                          two_root_tree_config):
    result = CliRunner().invoke(cli, ["start", "no-such-thing-anywhere"])
    assert result.exit_code != 0
    assert "no unit" in result.output.lower()
