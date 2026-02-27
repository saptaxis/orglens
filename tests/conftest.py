"""Shared test fixtures."""

import pytest
from pathlib import Path
from orglens.grammar import Grammar
from orglens.config import Config


@pytest.fixture
def grammar():
    grammar_path = Path(__file__).parent.parent / "orglens" / "grammars" / "default.yaml"
    return Grammar.from_yaml(grammar_path)


@pytest.fixture
def docs_tree(tmp_path):
    """Create a realistic docs directory tree for testing."""
    docs = tmp_path / "docs"

    # A project with plans and specs
    proj = docs / "projects" / "clipcompose"
    (proj / "specs").mkdir(parents=True)
    (proj / "plans").mkdir()
    (proj / "logs").mkdir()
    (proj / "overview.md").write_text(
        "# Overview\n\n> **Status:** Active\n"
    )
    (proj / "plans" / "01-packaging-Feb252026.md").write_text("# 01 — Packaging\n")
    (proj / "specs" / "agent-integration.md").write_text("# Agent Integration\n")

    # Another project (minimal)
    proj2 = docs / "projects" / "orglens"
    (proj2 / "specs").mkdir(parents=True)
    (proj2 / "plans").mkdir()
    (proj2 / "logs").mkdir()
    (proj2 / "overview.md").write_text(
        "# Overview\n\n> **Status:** Design complete\n"
    )

    # A research program with experiments
    rp = docs / "research" / "physics-priors"
    (rp / "specs").mkdir(parents=True)
    (rp / "literature").mkdir()
    (rp / "directions").mkdir()
    (rp / "brainstorms").mkdir()
    (rp / "research-question.md").write_text("# Research Question\n")
    (rp / "research-program-state.md").write_text(
        "# Research Program State\n\n"
        "| # | Name | Status |\n"
        "|---|------|--------|\n"
        "| 1 | Agent Behavior | **Complete** |\n"
        "| 2 | World Model Study | **Active** |\n"
    )

    # Experiment within the research program
    expt = rp / "expt-1-agent-behavior"
    (expt / "plans").mkdir(parents=True)
    (expt / "logs").mkdir()
    (expt / "findings").mkdir()
    (expt / "design.md").write_text("# Design\n")
    (expt / "plans" / "01-testbed-Feb032026.md").write_text("# 01 — Testbed\n")
    (expt / "plans" / "02-data-collection-Feb062026.md").write_text("# 02 — Data\n")
    (expt / "logs" / "01-testbed-Feb032026-log.md").write_text("# Log\n")

    # A client
    client = docs / "clients" / "freightify"
    client.mkdir(parents=True)
    (client / "overview.md").write_text("# Overview\n\n> **Status:** Active\n")

    return docs


@pytest.fixture
def config(tmp_path, docs_tree):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(f"docs_root: {docs_tree}\n")
    return Config.from_yaml(config_file)
