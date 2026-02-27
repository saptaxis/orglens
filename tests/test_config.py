"""Tests for config loading."""

import pytest
from pathlib import Path
from orglens.config import Config


@pytest.fixture
def config_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "docs_root: /tmp/test-docs\n"
        "grammar: default\n"
    )
    return config_file


@pytest.fixture
def config(config_yaml):
    return Config.from_yaml(config_yaml)


class TestConfigLoading:
    def test_loads_docs_root(self, config):
        assert config.docs_root == Path("/tmp/test-docs")

    def test_loads_grammar_name(self, config):
        assert config.grammar_name == "default"

    def test_default_grammar_name(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("docs_root: /tmp/test-docs\n")
        config = Config.from_yaml(config_file)
        assert config.grammar_name == "default"

    def test_missing_docs_root_raises(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("grammar: default\n")
        with pytest.raises(ValueError, match="docs_root"):
            Config.from_yaml(config_file)

    def test_expands_tilde(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("docs_root: ~/some/path\n")
        config = Config.from_yaml(config_file)
        assert "~" not in str(config.docs_root)

    def test_loads_grammar(self, config):
        grammar = config.load_grammar()
        assert grammar.version == 1
        assert "project" in grammar.entity_types

    def test_snapshot_path(self, config):
        assert config.snapshot_path.name == "snapshot.md"
