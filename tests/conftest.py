"""Shared test fixtures."""

import pytest
from pathlib import Path
from orglens.declaration import MARKER
from orglens.grammar import Grammar
from orglens.config import Config
from orglens.homes import Home
from orglens.units import Registry, Unit


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
    (rp / "overview.md").write_text(
        "# Overview\n\n> **Status:** Design complete\n"
    )
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
    (expt / "overview.md").write_text("# Overview\n\n> **Status:** Running\n")
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


@pytest.fixture
def two_root_tree(tmp_path, grammar):
    """A docs root and a code root, with one unit spanning both."""
    docs = tmp_path / "traitful-docs" / "docs"
    code = tmp_path / "code"

    unit_docs = docs / "projects" / "orglens"
    unit_docs.mkdir(parents=True)
    (unit_docs / MARKER).write_text(
        "home: traitful-docs/docs/projects/orglens\n"
        "unit: orglens\nkind: project\n"
        "homes:\n  - orglens\n  - traitful-docs/docs/projects/orglens\n"
    )
    (unit_docs / "overview.md").write_text("# Overview\n")

    (code / "orglens").mkdir(parents=True)
    (code / "traitful-docs").mkdir(parents=True)
    # the docs repo, so the subpath home resolves
    (code / "traitful-docs" / "docs" / "projects" / "orglens").mkdir(parents=True)

    # an undeclared folder that matches the grammar's project pattern
    (docs / "projects" / "reelmill").mkdir(parents=True)

    return Registry([docs, code], grammar)


@pytest.fixture
def two_root_tree_config(tmp_path, two_root_tree, monkeypatch):
    """Point the CLI at the two-root fixture tree.

    `two_root_tree` builds a Registry directly; the CLI cannot be handed one,
    so this writes the config that produces the same roots and exports it.
    """
    config = tmp_path / "config.yaml"
    config.write_text(
        "roots:\n" + "".join(f"  - {r}\n" for r in two_root_tree.roots)
    )
    monkeypatch.setenv("ORGLENS_CONFIG", str(config))
    return two_root_tree


# ── scadconfig fixtures ─────────────────────────────────────────────────
#
# `render` is pure and never touches disk, so these build `Unit` objects
# directly rather than going through a declaration and a `Registry` sweep.


@pytest.fixture
def unit_with_two_homes(tmp_path):
    """A unit spanning two repositories, both present on this machine."""
    return Unit(
        name="orglens",
        kind="project",
        homes=(
            Home(name="orglens", path=tmp_path / "orglens", how="marker"),
            Home(name="traitful-docs", path=tmp_path / "traitful-docs", how="marker"),
        ),
        part_of=None,
        declared_at=tmp_path / "orglens",
    )


@pytest.fixture
def unit_with_an_absent_home(tmp_path):
    """A unit with one home present and one not cloned on this machine."""
    return Unit(
        name="orglens",
        kind="project",
        homes=(
            Home(name="orglens", path=tmp_path / "orglens", how="marker"),
            Home(name="not-cloned-here", path=None, how="absent"),
        ),
        part_of=None,
        declared_at=tmp_path / "orglens",
    )


@pytest.fixture
def unit_with_runtime(tmp_path):
    """A unit whose declaration carries a `runtime:` block, passed through
    verbatim rather than modelled — scad's words, not orglens's.
    """
    return Unit(
        name="orglens",
        kind="project",
        homes=(Home(name="orglens", path=tmp_path / "orglens", how="marker"),),
        part_of=None,
        declared_at=tmp_path / "orglens",
        runtime={"python": {"version": "3.11", "pyproject": True}},
    )


@pytest.fixture
def unit_with_a_subpath_home(tmp_path):
    """Two homes naming the same repository — one at its root, one inside a
    subpath. Keying by the repository segment alone collides; the first
    home's path must win, not be silently overwritten by the second.
    """
    return Unit(
        name="orglens",
        kind="project",
        homes=(
            Home(name="traitful-docs", path=tmp_path / "traitful-docs", how="marker"),
            Home(
                name="traitful-docs/docs/projects/x",
                path=tmp_path / "traitful-docs" / "docs" / "projects" / "x",
                how="declaring",
            ),
        ),
        part_of=None,
        declared_at=tmp_path / "traitful-docs",
    )


@pytest.fixture
def unit_whose_only_home_is_a_subpath(tmp_path):
    """A unit whose sole home names a subpath inside a repository, not the
    repository itself. `--workdir` (and the default choice) name a
    *repository*, not a home — so marking the workdir by comparing against
    `home.name` directly would compare a subpath home name like
    `traitful-docs/docs/projects/x` against `traitful-docs` and never match.
    """
    return Unit(
        name="orglens",
        kind="project",
        homes=(
            Home(
                name="traitful-docs/docs/projects/x",
                path=tmp_path / "traitful-docs" / "docs" / "projects" / "x",
                how="declaring",
            ),
        ),
        part_of=None,
        declared_at=tmp_path / "traitful-docs" / "docs" / "projects" / "x",
    )


@pytest.fixture
def unit_with_clobbering_runtime(tmp_path):
    """A `runtime:` block that tries to overwrite the generated `name` and
    `repos` keys. Generated keys must win.
    """
    return Unit(
        name="orglens",
        kind="project",
        homes=(Home(name="orglens", path=tmp_path / "orglens", how="marker"),),
        part_of=None,
        declared_at=tmp_path / "orglens",
        runtime={"name": "hijacked", "repos": {"evil": {"path": "/nope"}}},
    )
