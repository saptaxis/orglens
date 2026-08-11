"""The commands, and what they refuse to know on their own."""

import pytest
from click.testing import CliRunner

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


@pytest.fixture
def deck_env(tmp_path, docs_tree):
    """A grammar with a kind the engine has never heard of."""
    grammar = tmp_path / "deck.yaml"
    grammar.write_text(
        "version: 2\n"
        "driver: DECK.md\n"
        "entities:\n"
        "  deck: capabilities/*\n"
        "artifacts:\n"
        "  card:\n"
        "    find: cards/*.md\n"
        "    means: One instruction to one model.\n"
    )
    (docs_tree / "capabilities" / "writing").mkdir(parents=True)
    (docs_tree / "capabilities" / "writing" / "cards").mkdir()
    (docs_tree / "capabilities" / "writing" / "cards" / "voice.md").write_text("# Voice\n")

    config_file = tmp_path / "deck-config.yaml"
    config_file.write_text(f"docs_root: {docs_tree}\ngrammar: {grammar}\n")
    return {"ORGLENS_CONFIG": str(config_file)}


class TestListCommand:
    def test_list_all(self, runner, cli_env):
        result = runner.invoke(cli, ["list"], env=cli_env)
        assert result.exit_code == 0
        assert "clipcompose" in result.output
        assert "physics-priors" in result.output

    def test_list_by_kind(self, runner, cli_env):
        result = runner.invoke(cli, ["list", "--type", "project"], env=cli_env)
        assert result.exit_code == 0
        assert "clipcompose" in result.output
        assert "physics-priors" not in result.output

    def test_a_nested_entity_shows_what_holds_it(self, runner, cli_env):
        result = runner.invoke(cli, ["list", "--type", "experiment"], env=cli_env)
        assert result.exit_code == 0
        assert "[physics-priors]" in result.output

    def test_an_unknown_kind_says_what_the_kinds_are(self, runner, cli_env):
        """This raised `KeyError: 'deck'` — the CLI never asked the grammar."""
        result = runner.invoke(cli, ["list", "--type", "deck"], env=cli_env)

        assert result.exit_code == 1
        assert result.exception is None or isinstance(result.exception, SystemExit)
        assert "Unknown kind: deck" in result.output
        assert "project" in result.output


class TestAKindTheEngineHasNeverHeardOf:
    def test_listing_it_needs_no_python_change(self, runner, deck_env):
        result = runner.invoke(cli, ["list", "--type", "deck"], env=deck_env)

        assert result.exit_code == 0
        assert "writing" in result.output

    def test_finding_its_documents_needs_no_python_change(self, runner, deck_env):
        result = runner.invoke(cli, ["find", "card"], env=deck_env)

        assert result.exit_code == 0
        assert "voice.md" in result.output

    def test_creating_one_needs_no_python_change(self, runner, deck_env, docs_tree):
        result = runner.invoke(cli, ["new", "deck", "interior"], env=deck_env)

        assert result.exit_code == 0
        assert (docs_tree / "capabilities" / "interior").is_dir()


class TestStatusCommand:
    def test_status_shows_entities(self, runner, cli_env):
        result = runner.invoke(cli, ["status"], env=cli_env)
        assert result.exit_code == 0
        assert "clipcompose" in result.output
        assert "Active" in result.output

    def test_the_authored_line_is_quoted_whole(self, runner, cli_env, docs_tree):
        """It is a sentence someone wrote, not a field to be trimmed."""
        overview = docs_tree / "projects" / "clipcompose" / "overview.md"
        overview.write_text(
            "# Overview\n\n"
            "> **Status:** Plans 01-04 complete; v2 plan on branch v2-plan1\n"
        )

        result = runner.invoke(cli, ["status"], env=cli_env)

        assert result.exit_code == 0
        assert "Plans 01-04 complete; v2 plan on branch v2-plan1" in result.output

    def test_the_line_is_shown_with_its_age(self, runner, cli_env):
        """Three real status lines are five months behind their trees."""
        result = runner.invoke(cli, ["status"], env=cli_env)

        assert result.exit_code == 0
        assert "old]" in result.output

    def test_the_author_s_case_survives(self, runner, cli_env):
        result = runner.invoke(cli, ["status"], env=cli_env)
        assert result.exit_code == 0
        assert "Active" in result.output


class TestFindCommand:
    def test_find_across_the_tree(self, runner, cli_env):
        result = runner.invoke(cli, ["find", "plan"], env=cli_env)
        assert result.exit_code == 0
        assert "01-packaging-Feb252026.md" in result.output

    def test_find_scoped_reaches_children(self, runner, cli_env):
        result = runner.invoke(cli, ["find", "plan", "physics-priors"], env=cli_env)
        assert result.exit_code == 0
        assert "01-testbed-Feb032026.md" in result.output

    def test_find_specs(self, runner, cli_env):
        result = runner.invoke(cli, ["find", "spec", "clipcompose"], env=cli_env)
        assert result.exit_code == 0
        assert "agent-integration.md" in result.output

    def test_a_document_with_no_recognisable_name_is_still_found(
        self, runner, cli_env, docs_tree
    ):
        (docs_tree / "projects" / "clipcompose" / "plans" / "02-stg-setup.md").write_text("x")

        result = runner.invoke(cli, ["find", "plan", "clipcompose"], env=cli_env)

        assert "02-stg-setup.md" in result.output

    def test_an_unknown_document_kind_says_what_the_kinds_are(self, runner, cli_env):
        result = runner.invoke(cli, ["find", "memo"], env=cli_env)

        assert result.exit_code == 1
        assert "Unknown document kind: memo" in result.output


class TestNewCommand:
    def test_new_project(self, runner, cli_env, docs_tree):
        result = runner.invoke(cli, ["new", "project", "test-tool"], env=cli_env)
        assert result.exit_code == 0
        assert (docs_tree / "projects" / "test-tool" / "overview.md").exists()

    def test_new_entity_inside_a_parent(self, runner, cli_env, docs_tree):
        """The full name is given — nothing numbers a directory any more."""
        result = runner.invoke(
            cli,
            ["new", "experiment", "expt-2-world-model", "--parent", "physics-priors"],
            env=cli_env,
        )

        assert result.exit_code == 0
        assert (
            docs_tree / "research" / "physics-priors" / "expt-2-world-model" / "design.md"
        ).exists()

    def test_a_name_the_pattern_would_not_find_is_refused(self, runner, cli_env):
        result = runner.invoke(
            cli, ["new", "experiment", "world-model", "--parent", "physics-priors"],
            env=cli_env,
        )

        assert result.exit_code == 1
        assert "would not be found" in result.output

    def test_documents_are_not_created_by_the_cli(self, runner, cli_env):
        """`new plan` is gone: nothing computes a filename, so nothing can."""
        result = runner.invoke(cli, ["new", "plan", "clipcompose"], env=cli_env)

        assert result.exit_code == 1
        assert "Unknown kind: plan" in result.output


class TestCheckCommand:
    def test_a_clean_tree_reports_nothing(self, runner, cli_env, docs_tree):
        (docs_tree / "clients" / "freightify" / "overview.md").write_text("# Overview\n")

        result = runner.invoke(cli, ["check"], env=cli_env)

        assert result.exit_code == 0

    def test_drift_is_reported_and_nothing_is_hidden(self, runner, cli_env, docs_tree):
        bare = docs_tree / "projects" / "resume"
        bare.mkdir()

        check = runner.invoke(cli, ["check"], env=cli_env)
        listing = runner.invoke(cli, ["list"], env=cli_env)

        assert check.exit_code == 0
        assert "resume" in check.output
        assert "overview.md" in check.output
        assert "resume" in listing.output  # reported, never gated

    def test_a_near_miss_is_named(self, runner, cli_env, docs_tree):
        near = docs_tree / "research" / "llm-probing"
        near.mkdir()
        (near / "question.md").write_text("# Question\n")

        result = runner.invoke(cli, ["check"], env=cli_env)

        assert "likely the same thing" in result.output
        assert "question.md" in result.output

    def test_a_pattern_that_matches_nothing_is_reported(self, runner, tmp_path, docs_tree):
        """A mistyped glob finds nothing and raises nothing — the silent failure."""
        grammar = tmp_path / "typo.yaml"
        grammar.write_text(
            "version: 2\ndriver: overview.md\nentities:\n  project: porjects/*\n"
        )
        config_file = tmp_path / "typo-config.yaml"
        config_file.write_text(f"docs_root: {docs_tree}\ngrammar: {grammar}\n")

        result = runner.invoke(cli, ["check"], env={"ORGLENS_CONFIG": str(config_file)})

        assert "matches nothing" in result.output
        assert "porjects/*" in result.output


class TestSnapshotCommand:
    def test_snapshot_writes_file(self, runner, cli_env):
        result = runner.invoke(cli, ["snapshot"], env=cli_env)
        assert result.exit_code == 0
        assert "Snapshot written" in result.output

    def test_snapshot_to_stdout(self, runner, cli_env):
        result = runner.invoke(cli, ["snapshot", "--stdout"], env=cli_env)
        assert result.exit_code == 0
        assert "Topology Snapshot" in result.output


class TestReferenceCommand:
    def test_it_renders_the_grammar(self, runner, cli_env):
        result = runner.invoke(cli, ["reference"], env=cli_env)

        assert result.exit_code == 0
        assert "research-program" in result.output
        assert "do not edit" in result.output

    def test_it_can_be_written_out(self, runner, cli_env, tmp_path):
        out = tmp_path / "generated" / "grammar-reference.md"

        result = runner.invoke(cli, ["reference", "--out", str(out)], env=cli_env)

        assert result.exit_code == 0
        assert out.read_text().startswith("<!-- generated")
