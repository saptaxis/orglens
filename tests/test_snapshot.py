"""The snapshot: what is in the tree, so agents read instead of scan."""

import pytest

from orglens.snapshot import generate_snapshot
from orglens.topology import Topology


@pytest.fixture
def snapshot(docs_tree, grammar, config):
    return generate_snapshot(Topology(docs_tree, grammar), config)


class TestWhatItContains:
    def test_it_names_the_kinds_the_grammar_declares(self, snapshot):
        assert "research-program (`research/*`)" in snapshot
        assert "plan (`plans/*.md`)" in snapshot

    def test_every_entity_appears_under_its_kind(self, snapshot):
        assert "## Projects" in snapshot
        assert "## Research programs" in snapshot
        assert "### clipcompose" in snapshot
        assert "### freightify" in snapshot

    def test_the_authored_line_is_carried(self, snapshot):
        assert "### clipcompose — Active" in snapshot

    def test_a_nested_entity_is_listed_under_what_holds_it(self, snapshot):
        assert "**Contains:**" in snapshot
        assert "- expt-1-agent-behavior (experiment)" in snapshot

    def test_a_nested_entity_gets_its_own_section(self, snapshot):
        """Experiments are entities, not a footnote on a research program."""
        assert "### expt-1-agent-behavior" in snapshot
        assert "In: physics-priors" in snapshot

    def test_documents_are_counted_against_the_entity_holding_them(self, snapshot):
        expt = snapshot.split("### expt-1-agent-behavior")[1]
        assert "**Plans:** 2" in expt
        assert "01-testbed-Feb032026.md" in expt


class TestWhatOnlyTheTreeKnows:
    def test_undeclared_directories_are_listed(self, docs_tree, grammar, config):
        """`archive/` and `presentation/` are real and in no grammar.

        An agent navigating by the declared structure alone would miss them,
        which is the whole reason the snapshot lists what is there.
        """
        (docs_tree / "research" / "physics-priors" / "archive").mkdir()

        snapshot = generate_snapshot(Topology(docs_tree, grammar), config)

        assert "`archive/`" in snapshot

    def test_top_level_documents_are_listed(self, docs_tree, grammar, config):
        (docs_tree / "projects" / "clipcompose" / "backlog.md").write_text("# Backlog\n")

        snapshot = generate_snapshot(Topology(docs_tree, grammar), config)

        assert "`backlog.md`" in snapshot

    def test_an_incomplete_entity_still_appears(self, docs_tree, grammar, config):
        (docs_tree / "clients" / "itus-capital").mkdir()

        snapshot = generate_snapshot(Topology(docs_tree, grammar), config)

        assert "### itus-capital" in snapshot


class TestWriting:
    def test_it_writes_where_told(self, docs_tree, grammar, config, tmp_path):
        out = tmp_path / "cache" / "snapshot.md"

        generate_snapshot(Topology(docs_tree, grammar), config, output_path=out)

        assert out.read_text().startswith("# Topology Snapshot")
