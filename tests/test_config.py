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
        assert config.roots[0] == Path("/tmp/test-docs")

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
        assert "~" not in str(config.roots[0])

    def test_loads_grammar(self, config):
        grammar = config.load_grammar()
        assert grammar.version == 2
        assert "project" in grammar.entity_types

    def test_a_second_tree_names_its_own_grammar(self, tmp_path):
        """Config, not the engine, decides which grammar governs which root."""
        grammar = tmp_path / "deck.yaml"
        grammar.write_text(
            "version: 2\ndriver: DECK.md\nentities:\n  deck: capabilities/*\n"
        )
        config_file = tmp_path / "config.yaml"
        config_file.write_text(f"docs_root: {tmp_path}\ngrammar: {grammar}\n")

        loaded = Config.from_yaml(config_file).load_grammar()

        assert set(loaded.entity_types) == {"deck"}

    def test_snapshot_path(self, config):
        assert config.snapshot_path.name == "snapshot.md"


def test_roots_accepts_a_list(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    cfg = tmp_path / "config.yaml"
    cfg.write_text(f"roots:\n  - {tmp_path / 'a'}\n  - {tmp_path / 'b'}\n")
    config = Config.from_yaml(cfg)
    assert config.roots == [tmp_path / "a", tmp_path / "b"]


def test_docs_root_still_works_and_becomes_the_first_root(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(f"docs_root: {tmp_path / 'docs'}\n")
    config = Config.from_yaml(cfg)
    assert config.roots == [tmp_path / "docs"]


def test_neither_key_is_an_error(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("grammar: default\n")
    try:
        Config.from_yaml(cfg)
    except ValueError as exc:
        assert "roots" in str(exc)
    else:
        raise AssertionError("expected a ValueError naming `roots`")
