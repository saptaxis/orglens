"""Tests for grammar loading and resolution."""

import pytest
from pathlib import Path
from orglens.grammar import Grammar


@pytest.fixture
def grammar():
    grammar_path = Path(__file__).parent.parent / "orglens" / "grammars" / "default.yaml"
    return Grammar.from_yaml(grammar_path)


class TestGrammarLoading:
    def test_loads_default_grammar(self, grammar):
        assert grammar.version == 1

    def test_has_entity_types(self, grammar):
        assert set(grammar.entity_types.keys()) == {
            "research-program", "experiment", "project", "client"
        }

    def test_has_artifact_types(self, grammar):
        assert set(grammar.artifact_types.keys()) == {"plan", "log", "spec"}


class TestEntityType:
    def test_project_parent_dir(self, grammar):
        project = grammar.entity_types["project"]
        assert project.parent_dir == "projects"

    def test_project_required_files(self, grammar):
        project = grammar.entity_types["project"]
        assert "overview.md" in project.required_files

    def test_project_directories(self, grammar):
        project = grammar.entity_types["project"]
        assert set(project.directories) == {"specs", "plans", "logs"}

    def test_project_state_file(self, grammar):
        project = grammar.entity_types["project"]
        assert project.state_file == "overview.md"

    def test_experiment_has_dir_pattern(self, grammar):
        expt = grammar.entity_types["experiment"]
        assert expt.dir_pattern == "expt-{n}-{name}"

    def test_experiment_parent_of(self, grammar):
        expt = grammar.entity_types["experiment"]
        assert expt.parent_of == "research-program"

    def test_research_program_children(self, grammar):
        rp = grammar.entity_types["research-program"]
        assert rp.children == ["experiment"]


class TestArtifactType:
    def test_plan_pattern(self, grammar):
        assert grammar.artifact_types["plan"].pattern == "{NN}-{topic}-{MonDDYYYY}.md"

    def test_plan_directory(self, grammar):
        assert grammar.artifact_types["plan"].directory == "plans"

    def test_log_pattern(self, grammar):
        assert grammar.artifact_types["log"].pattern == "{NN}-{topic}-{MonDDYYYY}-log.md"


class TestArtifactNaming:
    def test_generate_plan_name(self, grammar):
        name = grammar.artifact_types["plan"].generate_name(
            nn=5, topic="data-collection", date_str="Feb272026"
        )
        assert name == "05-data-collection-Feb272026.md"

    def test_generate_log_name(self, grammar):
        name = grammar.artifact_types["log"].generate_name(
            nn=5, topic="data-collection", date_str="Feb272026"
        )
        assert name == "05-data-collection-Feb272026-log.md"

    def test_generate_spec_name(self, grammar):
        name = grammar.artifact_types["spec"].generate_name(
            nn=None, topic="system-design-v2", date_str=None
        )
        assert name == "system-design-v2.md"

    def test_nn_zero_padded(self, grammar):
        name = grammar.artifact_types["plan"].generate_name(
            nn=1, topic="setup", date_str="Feb272026"
        )
        assert name == "01-setup-Feb272026.md"

    def test_parse_plan_name(self, grammar):
        parsed = grammar.artifact_types["plan"].parse_name("05-data-collection-Feb272026.md")
        assert parsed["nn"] == 5
        assert parsed["topic"] == "data-collection"
        assert parsed["date"] == "Feb272026"

    def test_parse_log_name(self, grammar):
        parsed = grammar.artifact_types["log"].parse_name("05-data-collection-Feb272026-log.md")
        assert parsed["nn"] == 5
        assert parsed["topic"] == "data-collection"
