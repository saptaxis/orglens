"""`orglens config` — the one command that writes under `~/.scad`, and only
a config file scad reads, never its index or launch records.
"""

from __future__ import annotations

import yaml
from click.testing import CliRunner

from orglens.cli import cli


def test_config_writes_to_out_when_given(tmp_path, two_root_tree_config):
    out = tmp_path / "rendered.yml"
    result = CliRunner().invoke(cli, ["config", "orglens", "--out", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    got = yaml.safe_load(out.read_text())
    assert got["name"] == "orglens"


def test_config_defaults_to_the_scad_configs_dir(tmp_path, monkeypatch,
                                                  two_root_tree_config):
    # No real `~/.scad` is touched: the destination is a module-level
    # constant, monkeypatched into tmp_path for this test.
    configs_dir = tmp_path / "scad-configs"
    monkeypatch.setattr("orglens.cli.SCAD_CONFIGS_DIR", configs_dir)

    result = CliRunner().invoke(cli, ["config", "orglens"])
    assert result.exit_code == 0

    written = configs_dir / "orglens.yml"
    assert written.exists()
    assert str(written) in result.output


def test_config_rejects_an_unknown_workdir(tmp_path, two_root_tree_config):
    # A `--workdir` naming a repository the unit does not have must fail
    # loudly, before anything is written — not render a config with no
    # workdir marked at all.
    out = tmp_path / "rendered.yml"
    result = CliRunner().invoke(
        cli, ["config", "orglens", "--workdir", "nonexistent-repo", "--out", str(out)]
    )
    assert result.exit_code != 0
    assert not out.exists()
    assert "nonexistent-repo" in result.output


def test_config_accepts_a_named_workdir(tmp_path, two_root_tree_config):
    out = tmp_path / "rendered.yml"
    result = CliRunner().invoke(
        cli, ["config", "orglens", "--workdir", "traitful-docs", "--out", str(out)]
    )
    assert result.exit_code == 0
    got = yaml.safe_load(out.read_text())
    assert got["repos"]["traitful-docs"]["workdir"] is True
