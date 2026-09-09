"""The snapshot: what is in the tree, so agents read instead of scan."""

import pytest

from orglens.config import Config
from orglens.declaration import MARKER
from orglens.snapshot import generate_snapshot
from orglens.units import Registry


def _declare(path, unit: str, kind: str, part_of: str | None = None) -> None:
    """Write a marker that declares `path` as its own unit, home named after it."""
    path.mkdir(parents=True, exist_ok=True)
    lines = [f"home: {unit}", f"unit: {unit}", f"kind: {kind}"]
    if part_of:
        lines.append(f"part_of: {part_of}")
    lines.append(f"homes:\n  - {unit}")
    (path / MARKER).write_text("\n".join(lines) + "\n")


@pytest.fixture
def units_tree(tmp_path):
    """A one-root tree of declared units, mirroring the shape the old
    positional `docs_tree` fixture built."""
    docs = tmp_path / "docs"

    clipcompose = docs / "projects" / "clipcompose"
    _declare(clipcompose, "clipcompose", "project")
    (clipcompose / "plans").mkdir()
    (clipcompose / "plans" / "01-packaging-Feb252026.md").write_text("# 01 — Packaging\n")
    (clipcompose / "overview.md").write_text("# Overview\n\n> **Status:** Active\n")

    freightify = docs / "clients" / "freightify"
    _declare(freightify, "freightify", "client")
    (freightify / "overview.md").write_text("# Overview\n\n> **Status:** Active\n")

    physics = docs / "research" / "physics-priors"
    _declare(physics, "physics-priors", "research-program")
    (physics / "overview.md").write_text("# Overview\n\n> **Status:** Design complete\n")

    expt = physics / "expt-1-agent-behavior"
    _declare(expt, "expt-1-agent-behavior", "experiment", part_of="physics-priors")
    (expt / "plans").mkdir()
    (expt / "plans" / "01-testbed-Feb032026.md").write_text("# 01 — Testbed\n")
    (expt / "plans" / "02-data-collection-Feb062026.md").write_text("# 02 — Data\n")
    (expt / "overview.md").write_text("# Overview\n\n> **Status:** Running\n")

    return docs


@pytest.fixture
def registry(units_tree, grammar):
    return Registry([units_tree], grammar)


@pytest.fixture
def config(tmp_path, units_tree):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(f"docs_root: {units_tree}\n")
    return Config.from_yaml(config_file)


@pytest.fixture
def snapshot(registry, config):
    return generate_snapshot(registry, config)


class TestWhatItContains:
    def test_it_names_the_kinds_the_grammar_declares(self, snapshot):
        assert "research-program (`research/*`)" in snapshot
        assert "plan (`plans/*.md`)" in snapshot

    def test_every_unit_appears_under_its_kind(self, snapshot):
        assert "## Projects" in snapshot
        assert "## Research programs" in snapshot
        assert "### clipcompose" in snapshot
        assert "### freightify" in snapshot

    def test_the_authored_line_is_carried(self, snapshot):
        assert "### clipcompose — Active" in snapshot

    def test_a_part_names_what_it_belongs_to(self, snapshot):
        assert "In: physics-priors" in snapshot

    def test_a_part_gets_its_own_section(self, snapshot):
        """A part is a unit in its own right, not a footnote on what it is
        declared part of."""
        assert "### expt-1-agent-behavior" in snapshot

    def test_a_unit_lists_what_is_declared_part_of_it(self, snapshot):
        program = snapshot.split("### physics-priors")[1].split("### expt")[0]
        assert "**Contains:**" in program
        assert "- expt-1-agent-behavior (experiment)" in program

    def test_documents_are_counted_against_the_unit_holding_them(self, snapshot):
        expt = snapshot.split("### expt-1-agent-behavior")[1]
        assert "**Plans:** 2" in expt
        assert "01-testbed-Feb032026.md" in expt


class TestWhatOnlyTheTreeKnows:
    def test_undeclared_directories_are_listed(self, units_tree, registry, config):
        """`archive/` and `presentation/` are real and in no grammar.

        An agent navigating by the declared structure alone would miss them,
        which is the whole reason the snapshot lists what is there.
        """
        (units_tree / "research" / "physics-priors" / "archive").mkdir()

        snapshot = generate_snapshot(registry, config)

        assert "`archive/`" in snapshot

    def test_top_level_documents_are_listed(self, units_tree, registry, config):
        (units_tree / "projects" / "clipcompose" / "backlog.md").write_text("# Backlog\n")

        snapshot = generate_snapshot(registry, config)

        assert "`backlog.md`" in snapshot

    def test_an_undeclared_directory_is_not_a_unit(self, units_tree, registry, config):
        (units_tree / "clients" / "itus-capital").mkdir()

        snapshot = generate_snapshot(registry, config)

        assert "### itus-capital" not in snapshot


class TestWriting:
    def test_it_writes_where_told(self, registry, config, tmp_path):
        out = tmp_path / "cache" / "snapshot.md"

        generate_snapshot(registry, config, output_path=out)

        assert out.read_text().startswith("# Topology Snapshot")
