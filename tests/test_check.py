"""The audit: what it reports, and the far longer list it deliberately does not."""

import subprocess
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


def _run_git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True)


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


def test_a_file_present_in_one_home_is_not_drift_in_another(two_root_tree):
    """`orglens` in `two_root_tree` is exactly the live bug: the docs home
    carries `overview.md`, the code home never should. Reporting the code
    home for a file that belongs in the docs home misleads about where the
    fix belongs, so a unit with the file in *any* home must stay quiet.
    """
    report = check.run(two_root_tree)

    assert not any(d.entity == "orglens" for d in report.drifted)


def test_a_file_missing_from_every_home_is_reported_once_naming_the_unit(
    tmp_path, grammar
):
    """Two distinctly-named homes, both real, both lacking `overview.md` —
    unlike a same-named pair, both actually resolve into `unit.homes` rather
    than the ladder picking one and losing the other.
    """
    docs_root = tmp_path / "docs-root"
    code_root = tmp_path / "code-root"
    docs_home = docs_root / "projects" / "gizmo-docs"
    code_home = code_root / "gizmo"
    docs_home.mkdir(parents=True)
    code_home.mkdir(parents=True)
    (docs_home / MARKER).write_text(
        "unit: gizmo\nkind: project\nhomes:\n  - gizmo-docs\n  - gizmo\n"
    )

    report = check.run(Registry([docs_root, code_root], grammar))

    rows = [d for d in report.drifted if d.entity == "gizmo"]
    assert len(rows) == 1
    assert [m.name for m in rows[0].missing] == ["overview.md"]


def test_near_miss_hint_searches_every_home_not_only_the_first(tmp_path, grammar):
    """The near-miss that resembles `research-question.md` lives in the
    second home, not the declaring one checked first — the hint must not
    stop looking after the first home comes up empty.
    """
    root_a = tmp_path / "root-a"
    root_b = tmp_path / "root-b"
    home_a = root_a / "research" / "llm-probing"
    home_b = root_b / "llm-probing-code"
    home_a.mkdir(parents=True)
    home_b.mkdir(parents=True)
    (home_a / MARKER).write_text(
        "unit: llm-probing\nkind: research-program\n"
        "homes:\n  - llm-probing\n  - llm-probing-code\n"
    )
    (home_b / "question.md").write_text("# Question\n")

    report = check.run(Registry([root_a, root_b], grammar))

    drift = next(d for d in report.drifted if d.entity == "llm-probing")
    hints = {m.name: m.resembles for m in drift.missing}
    assert hints["research-question.md"] == "question.md"


def test_undeclared_candidates_are_reported(two_root_tree):
    report = check.run(two_root_tree)
    assert any(p.name == "reelmill" for p in report.undeclared)


def test_a_home_resolved_by_name_only_is_reported_as_weak(two_root_tree):
    report = check.run(two_root_tree)
    # `orglens` in the code root has no marker and no git remote, so it can
    # only have resolved by directory name — renaming it detaches silently.
    assert ("orglens", "orglens", "name") in report.weak


def test_a_report_with_only_undeclared_rows_is_still_truthy(two_root_tree):
    assert bool(check.run(two_root_tree))


def test_a_duplicated_unit_name_is_reported_with_both_declaring_paths(
    declared_tree, grammar
):
    """Two markers saying the same `unit:` used to make `Registry.resolve`
    raise out of a loop that iterated every unit and re-resolved each one by
    its own already-known name — taking `status`, `view` and `snapshot` down
    for every unit, not only the duplicated one. `check` is where this must
    surface instead.
    """
    a = declared_tree / "projects" / "dup-a"
    b = declared_tree / "projects" / "dup-b"
    _declare(a, "dup", "project")
    _declare(b, "dup", "project")

    report = check.run(Registry([declared_tree], grammar))

    dup = next(d for d in report.duplicates if d.name == "dup")
    assert set(dup.paths) == {a, b}


def test_a_unique_unit_name_is_never_reported_as_duplicate(registry):
    report = check.run(registry)
    assert report.duplicates == []


def test_a_unique_remote_tail_is_not_reported_as_weak(tmp_path, grammar):
    """The remote rung matches on the repository-name tail alone, discarding
    the host and owner — a real looseness, but only a live hazard when some
    other scanned candidate shares that tail. On a tree where nothing else
    has the same tail, there is no owner to collide with, so flagging it
    unconditionally (as `weak` used to) reports a risk that is not present.
    """
    d = tmp_path / "renamed-locally"
    d.mkdir()
    _run_git("init", "-q", cwd=d)
    _run_git(
        "remote", "add", "origin",
        "git@github.com:saptaxis/world-model-ladder.git", cwd=d,
    )
    (d / MARKER).write_text(
        "unit: world-model-ladder\nkind: project\n"
        "homes:\n  - world-model-ladder\n"
    )

    report = check.run(Registry([tmp_path], grammar))

    assert not any(row[2] == "remote" for row in report.weak)


def test_a_remote_tail_shared_across_owners_is_reported_as_weak(tmp_path, grammar):
    """Two repositories from different owners can share a repository-name
    tail — the exact ambiguity the remote rung cannot see, since it discards
    the owner. When one of them is a declared home, the collision is real
    and `weak` must say so.
    """
    owner_a = tmp_path / "owner-a-checkout"
    owner_a.mkdir()
    _run_git("init", "-q", cwd=owner_a)
    _run_git(
        "remote", "add", "origin", "git@github.com:owner-a/thing.git", cwd=owner_a,
    )
    (owner_a / MARKER).write_text(
        "unit: thing\nkind: project\nhomes:\n  - thing\n"
    )

    owner_b = tmp_path / "owner-b-checkout"
    owner_b.mkdir()
    _run_git("init", "-q", cwd=owner_b)
    _run_git(
        "remote", "add", "origin", "git@github.com:owner-b/thing.git", cwd=owner_b,
    )

    report = check.run(Registry([tmp_path], grammar))

    assert ("thing", "thing", "remote") in report.weak


def test_two_candidates_claiming_one_home_name_are_named(tmp_path, grammar):
    """Confirmed live: in a two-root tree a home named `alpha` resolved to a
    docs folder of that name because it came first in scan order, making the
    real code home's plans invisible, with only a `weak` row as a clue.
    """
    docs_root = tmp_path / "docs-root"
    code_root = tmp_path / "code-root"
    decoy = docs_root / "alpha"
    real = code_root / "alpha"
    decoy.mkdir(parents=True)
    real.mkdir(parents=True)
    unit_dir = docs_root / "projects" / "widget"
    unit_dir.mkdir(parents=True)
    (unit_dir / MARKER).write_text(
        "unit: widget\nkind: project\nhomes:\n  - alpha\n"
    )

    report = check.run(Registry([docs_root, code_root], grammar))

    collision = next(c for c in report.collisions if c.home == "alpha")
    assert set(collision.paths) == {decoy, real}


def test_a_synthetic_declaring_home_is_never_reported_as_a_collision(tmp_path, grammar):
    """A subfolder declaration with no `home:` key — the spec's normal case,
    and what the real markers use — pins its own directory directly rather
    than resolving it through the ladder. An unrelated directory elsewhere
    sharing that basename must not be reported as a contest that never
    happened. "A docs folder named after its code repo" is the archetypal
    layout in this tree, so this would otherwise fire on most units.
    """
    docs_root = tmp_path / "docs-root"
    code_root = tmp_path / "code-root"
    eps = docs_root / "projects" / "eps"
    eps.mkdir(parents=True)
    (eps / MARKER).write_text("unit: eps\nkind: project\n")
    (code_root / "eps").mkdir(parents=True)  # unrelated, shares the basename only

    report = check.run(Registry([docs_root, code_root], grammar))

    assert not any(c.home == "eps" for c in report.collisions)
