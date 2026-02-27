"""Tests for CLI commands."""

import pytest
from click.testing import CliRunner
from pathlib import Path
from orglens.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def cli_env(tmp_path, docs_tree):
    """Set up config file and return env dict for CLI invocation."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text(f"docs_root: {docs_tree}\n")
    return {"ORGLENS_CONFIG": str(config_file)}


class TestListCommand:
    def test_list_all(self, runner, cli_env):
        result = runner.invoke(cli, ["list"], env=cli_env)
        assert result.exit_code == 0
        assert "clipcompose" in result.output
        assert "physics-priors" in result.output

    def test_list_projects(self, runner, cli_env):
        result = runner.invoke(cli, ["list", "--type", "project"], env=cli_env)
        assert result.exit_code == 0
        assert "clipcompose" in result.output
        assert "physics-priors" not in result.output

    def test_list_research_programs(self, runner, cli_env):
        result = runner.invoke(cli, ["list", "--type", "research-program"], env=cli_env)
        assert result.exit_code == 0
        assert "physics-priors" in result.output


class TestStatusCommand:
    def test_status_shows_entities(self, runner, cli_env):
        result = runner.invoke(cli, ["status"], env=cli_env)
        assert result.exit_code == 0
        assert "clipcompose" in result.output
        assert "active" in result.output.lower() or "Active" in result.output


class TestFindCommand:
    def test_find_plans(self, runner, cli_env):
        result = runner.invoke(cli, ["find", "plan"], env=cli_env)
        assert result.exit_code == 0
        assert "01-packaging-Feb252026.md" in result.output

    def test_find_plans_scoped(self, runner, cli_env):
        result = runner.invoke(cli, ["find", "plan", "physics-priors"], env=cli_env)
        assert result.exit_code == 0
        assert "01-testbed-Feb032026.md" in result.output

    def test_find_specs(self, runner, cli_env):
        result = runner.invoke(cli, ["find", "spec", "clipcompose"], env=cli_env)
        assert result.exit_code == 0
        assert "agent-integration.md" in result.output


class TestNewEntityCommand:
    def test_new_project(self, runner, cli_env, docs_tree):
        result = runner.invoke(cli, ["new", "project", "test-tool"], env=cli_env)
        assert result.exit_code == 0
        assert (docs_tree / "projects" / "test-tool" / "overview.md").exists()

    def test_new_experiment(self, runner, cli_env, docs_tree):
        result = runner.invoke(
            cli, ["new", "experiment", "world-model", "--parent", "physics-priors"],
            env=cli_env,
        )
        assert result.exit_code == 0
        expt_dir = docs_tree / "research" / "physics-priors" / "expt-2-world-model"
        assert expt_dir.exists()


class TestNewArtifactCommand:
    def test_new_plan(self, runner, cli_env, docs_tree):
        result = runner.invoke(
            cli, ["new", "plan", "clipcompose", "agent-integration"],
            env=cli_env,
        )
        assert result.exit_code == 0
        plans = list((docs_tree / "projects" / "clipcompose" / "plans").glob("02-*"))
        assert len(plans) == 1

    def test_new_spec(self, runner, cli_env, docs_tree):
        result = runner.invoke(
            cli, ["new", "spec", "orglens", "api-reference"],
            env=cli_env,
        )
        assert result.exit_code == 0
        assert (docs_tree / "projects" / "orglens" / "specs" / "api-reference.md").exists()


class TestSnapshotCommand:
    def test_snapshot_writes_file(self, runner, cli_env, tmp_path):
        result = runner.invoke(cli, ["snapshot"], env=cli_env)
        assert result.exit_code == 0
        assert "Snapshot written" in result.output or "snapshot" in result.output.lower()

    def test_snapshot_to_stdout(self, runner, cli_env):
        result = runner.invoke(cli, ["snapshot", "--stdout"], env=cli_env)
        assert result.exit_code == 0
        assert "Topology Snapshot" in result.output
