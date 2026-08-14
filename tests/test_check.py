"""The audit: what it reports, and the far longer list it deliberately does not."""

from pathlib import Path

import pytest

from orglens import check
from orglens.declaration import MARKER
from orglens.grammar import Grammar
from orglens.units import Registry


def _declare(path: Path, unit: str, kind: str) -> None:
    """Write a marker that declares `path` as its own unit, home named after it."""
    path.mkdir(parents=True, exist_ok=True)
    (path / MARKER).write_text(
        f"home: {unit}\nunit: {unit}\nkind: {kind}\nhomes:\n  - {unit}\n"
    )


@pytest.fixture
def declared_tree(tmp_path, grammar):
    """Two quiet, fully-declared units: enough to prove `check` stays silent
    on a tree that holds what the grammar describes, and still lets each test
    add exactly the drift it wants to see.

    clipcompose carries one real plan, log and spec so every artifact kind in
    the default grammar has at least one match somewhere in the tree — without
    that, the quiet tree would trip `unmatched` on kinds no test here is about.
    A directory nested inside a declared unit's home is owned by that unit,
    not undeclared work, so this does not add anything to `undeclared`.
    """
    docs = tmp_path / "docs"
    clipcompose = docs / "projects" / "clipcompose"
    _declare(clipcompose, "clipcompose", "project")
    (clipcompose / "overview.md").write_text("# Overview\n")
    (clipcompose / "plans").mkdir()
    (clipcompose / "plans" / "01-packaging-Feb252026.md").write_text("# 01 — Packaging\n")
    (clipcompose / "logs").mkdir()
    (clipcompose / "logs" / "01-packaging-Feb252026-log.md").write_text("# Log\n")
    (clipcompose / "specs").mkdir()
    (clipcompose / "specs" / "agent-integration.md").write_text("# Agent Integration\n")

    orglens = docs / "projects" / "orglens"
    _declare(orglens, "orglens", "project")
    (orglens / "overview.md").write_text("# Overview\n")

    return docs


@pytest.fixture
def registry(declared_tree, grammar):
    return Registry([declared_tree], grammar)


class TestWhatItReports:
    def test_a_tree_holding_what_the_grammar_describes_is_quiet(self, registry):
        assert not check.run(registry)

    def test_a_missing_document_is_named(self, declared_tree, grammar):
        _declare(declared_tree / "clients" / "itus-capital", "itus-capital", "client")

        report = check.run(Registry([declared_tree], grammar))

        drift = next(d for d in report.drifted if d.entity == "itus-capital")
        assert [m.name for m in drift.missing] == ["overview.md"]

    def test_a_near_miss_is_pointed_at(self, declared_tree, grammar):
        """Two of four real cases are a rename away, not a writing job."""
        program = declared_tree / "research" / "llm-probing"
        _declare(program, "llm-probing", "research-program")
        (program / "question.md").write_text("# Question\n")

        report = check.run(Registry([declared_tree], grammar))

        drift = next(d for d in report.drifted if d.entity == "llm-probing")
        hints = {m.name: m.resembles for m in drift.missing}
        assert hints["research-question.md"] == "question.md"

    def test_an_unrelated_file_is_not_offered_as_a_near_miss(self, declared_tree, grammar):
        bare = declared_tree / "projects" / "resume"
        _declare(bare, "resume", "project")
        (bare / "resume-May222026.md").write_text("# Resume\n")

        report = check.run(Registry([declared_tree], grammar))

        drift = next(d for d in report.drifted if d.entity == "resume")
        assert [m.resembles for m in drift.missing] == [None]


class TestWhatItLeavesAlone:
    def test_a_missing_directory_is_not_drift(self, declared_tree, grammar):
        """An absent `specs/` means nothing has been written there yet.

        Reporting directories turned four honest lines into fourteen on the
        real tree, most of them about projects with no design documents. The
        only way to silence that report is to scaffold empty directories,
        which is worse than the report.
        """
        specs = declared_tree / "projects" / "orglens" / "specs"
        specs.mkdir()
        specs.rmdir()

        report = check.run(Registry([declared_tree], grammar))

        assert not any(d.entity == "orglens" for d in report.drifted)

    def test_document_names_are_never_judged(self, declared_tree, registry):
        """88 real documents use two conventions the template does not describe."""
        # Living directly in the home, not in a nested plans/ folder — nesting
        # is exactly what test_document_names_are_never_judged does not need
        # to prove, and it happens to trip a coarser fnmatch elsewhere.
        (declared_tree / "projects" / "clipcompose" / "wildly-off.md").write_text("x")

        assert not check.run(registry)

    def test_nothing_it_finds_changes_what_is_visible(self, declared_tree, grammar):
        # No marker: an ordinary undeclared folder, not a unit.
        (declared_tree / "clients" / "itus-capital").mkdir(parents=True)
        registry = Registry([declared_tree], grammar)

        assert check.run(registry).undeclared
        assert "itus-capital" in {p.name for p in registry.candidates()}


class TestSilentFailure:
    def test_a_pattern_matching_nothing_produces_no_candidates(self, declared_tree, tmp_path):
        """A mistyped glob finds nothing and raises nothing.

        `barren` used to say so explicitly. Now the absence says it directly:
        nothing matched, so nothing is offered as a migration candidate — the
        one thing the design still owes the reader is that this stays visible
        rather than looking identical to "nothing to migrate here."
        """
        path = tmp_path / "typo.yaml"
        path.write_text(
            "version: 2\ndriver: overview.md\nentities:\n  project: porjects/*\n"
        )

        report = check.run(Registry([declared_tree], Grammar.from_yaml(path)))

        assert report.undeclared == []

    def test_a_pattern_that_matches_produces_a_candidate(self, declared_tree, grammar):
        (declared_tree / "projects" / "resume").mkdir()  # no marker

        report = check.run(Registry([declared_tree], grammar))

        assert any(p.name == "resume" for p in report.undeclared)

    def test_a_document_kind_with_no_instances_is_reported(self, declared_tree, tmp_path):
        """The real bank declares three kinds it holds none of.

        A glob at the wrong depth looks exactly like this, which is how the
        capabilities grammar came to point `operators/*.md` at documents that
        actually live one directory lower. `candidates()` only ever iterates
        `entity_types`, so this failure mode is not the one `undeclared`
        superseded — it needs its own field.
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

        report = check.run(Registry([declared_tree], Grammar.from_yaml(path)))

        assert report.unmatched == ["memo"]

    def test_a_document_kind_that_matches_somewhere_is_not_reported(self, registry):
        assert check.run(registry).unmatched == []

    def test_a_document_reachable_only_at_depth_is_not_reported_unmatched(
        self, declared_tree, tmp_path
    ):
        """`plans/archive/x.md` is real work, one level below where the
        pattern's text literally reaches. A shallow check of the raw glob
        text treats that as "no plan documents anywhere" and reports a
        working kind as unmatched — worse than not checking at all, since
        `unmatched` exists to catch a *mistyped* glob, not a working one.
        """
        path = tmp_path / "g.yaml"
        path.write_text(
            "version: 2\n"
            "driver: overview.md\n"
            "entities:\n"
            "  project: projects/*\n"
            "artifacts:\n"
            "  plan:\n"
            "    find: plans/*.md\n"
            "    means: Numbered units of work.\n"
        )
        clipcompose = declared_tree / "projects" / "clipcompose"
        # Only an archived plan remains — nothing at the depth the pattern's
        # text literally names.
        (clipcompose / "plans" / "01-packaging-Feb252026.md").unlink()
        archive = clipcompose / "plans" / "archive"
        archive.mkdir()
        (archive / "00-old-Jan012026.md").write_text("# old\n")

        report = check.run(Registry([declared_tree], Grammar.from_yaml(path)))

        assert "plan" not in report.unmatched


def test_undeclared_candidates_are_reported(two_root_tree):
    report = check.run(two_root_tree)
    assert any(p.name == "reelmill" for p in report.undeclared)


def test_a_home_resolved_by_name_only_is_reported_as_weak(two_root_tree):
    report = check.run(two_root_tree)
    # `orglens` in the code root has no marker and no git remote, so it can
    # only have resolved by directory name — renaming it detaches silently.
    assert ("orglens", "orglens") in report.weak


def test_a_report_with_only_undeclared_rows_is_still_truthy(two_root_tree):
    assert bool(check.run(two_root_tree))
