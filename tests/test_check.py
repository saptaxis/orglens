"""The audit: what it reports, and the far longer list it deliberately does not."""

import pytest

from orglens import check
from orglens.grammar import Grammar
from orglens.topology import Topology


@pytest.fixture
def topo(docs_tree, grammar):
    return Topology(docs_tree, grammar)


class TestWhatItReports:
    def test_a_tree_holding_what_the_grammar_describes_is_quiet(self, topo):
        assert not check.run(topo)

    def test_a_missing_document_is_named(self, docs_tree, grammar):
        (docs_tree / "clients" / "itus-capital").mkdir()

        report = check.run(Topology(docs_tree, grammar))

        drift = next(d for d in report.drifted if d.entity == "itus-capital")
        assert [m.name for m in drift.missing] == ["overview.md"]

    def test_a_near_miss_is_pointed_at(self, docs_tree, grammar):
        """Two of four real cases are a rename away, not a writing job."""
        program = docs_tree / "research" / "llm-probing"
        program.mkdir()
        (program / "question.md").write_text("# Question\n")

        report = check.run(Topology(docs_tree, grammar))

        drift = next(d for d in report.drifted if d.entity == "llm-probing")
        hints = {m.name: m.resembles for m in drift.missing}
        assert hints["research-question.md"] == "question.md"

    def test_an_unrelated_file_is_not_offered_as_a_near_miss(self, docs_tree, grammar):
        bare = docs_tree / "projects" / "resume"
        bare.mkdir()
        (bare / "resume-May222026.md").write_text("# Resume\n")

        report = check.run(Topology(docs_tree, grammar))

        drift = next(d for d in report.drifted if d.entity == "resume")
        assert [m.resembles for m in drift.missing] == [None]


class TestWhatItLeavesAlone:
    def test_a_missing_directory_is_not_drift(self, docs_tree, grammar):
        """An absent `specs/` means nothing has been written there yet.

        Reporting directories turned four honest lines into fourteen on the
        real tree, most of them about projects with no design documents. The
        only way to silence that report is to scaffold empty directories,
        which is worse than the report.
        """
        (docs_tree / "projects" / "orglens" / "specs").rmdir()

        report = check.run(Topology(docs_tree, grammar))

        assert not any(d.entity == "orglens" for d in report.drifted)

    def test_document_names_are_never_judged(self, docs_tree, grammar):
        """88 real documents use two conventions the template does not describe."""
        (docs_tree / "projects" / "clipcompose" / "plans" / "wildly-off.md").write_text("x")

        assert not check.run(Topology(docs_tree, grammar))

    def test_nothing_it_finds_changes_what_is_visible(self, docs_tree, grammar):
        (docs_tree / "clients" / "itus-capital").mkdir()
        topo = Topology(docs_tree, grammar)

        assert check.run(topo).drifted
        assert "itus-capital" in {e.name for e in topo.list_entities()}


class TestSilentFailure:
    def test_a_pattern_matching_nothing_is_reported(self, docs_tree, tmp_path):
        """A mistyped glob finds nothing and raises nothing.

        This is the one new way the design can go wrong, so it is the one thing
        the audit looks for beyond missing documents.
        """
        path = tmp_path / "typo.yaml"
        path.write_text(
            "version: 2\ndriver: overview.md\nentities:\n  project: porjects/*\n"
        )

        report = check.run(Topology(docs_tree, Grammar.from_yaml(path)))

        assert report.barren == ["project: porjects/*"]

    def test_a_pattern_that_matches_is_not_reported(self, topo):
        assert check.run(topo).barren == []

    def test_a_document_kind_with_no_instances_is_reported(self, docs_tree, tmp_path):
        """The real bank declares three kinds it holds none of.

        A glob at the wrong depth looks exactly like this, which is how the
        capabilities grammar came to point `operators/*.md` at documents that
        actually live one directory lower.
        """
        path = tmp_path / "g.yaml"
        path.write_text(
            "version: 2\n"
            "driver: overview.md\n"
            "entities:\n"
            "  project: projects/*\n"
            "artifacts:\n"
            "  memo:\n"
            "    find: memos/*.md\n"
            "    means: Nothing writes these.\n"
        )

        report = check.run(Topology(docs_tree, Grammar.from_yaml(path)))

        assert report.barren == ["memo: memos/*.md"]
