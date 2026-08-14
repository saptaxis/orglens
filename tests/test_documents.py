from pathlib import Path

import pytest

from orglens import documents
from orglens.declaration import MARKER
from orglens.units import Registry


@pytest.fixture
def nested_docs(tmp_path, grammar):
    """A programme whose plans all sit in subfolders — the real shape."""
    docs = tmp_path / "docs"
    prog = docs / "research" / "physics-priors"
    prog.mkdir(parents=True)
    (prog / MARKER).write_text(
        "home: p\nunit: physics-priors\nkind: research-program\nhomes:\n  - p\n"
    )
    (tmp_path / "p").mkdir()

    for folder, count in (("expt-1", 3), ("expt-2", 2), ("infrastructure", 1)):
        plans = prog / folder / "plans"
        plans.mkdir(parents=True)
        for i in range(count):
            (plans / f"0{i + 1}-thing-Feb0{i + 1}2026.md").write_text("# plan\n")
    # one level deeper still — the archive case
    archive = prog / "expt-1" / "plans" / "archive"
    archive.mkdir()
    (archive / "00-old-Jan012026.md").write_text("# old\n")

    return Registry([docs, tmp_path], grammar)


def test_plans_are_found_at_any_depth(nested_docs):
    found = documents.find(nested_docs, "plan", "physics-priors")
    assert len(found) == 7  # 3 + 2 + 1 + 1 archived


def test_a_folder_matching_no_pattern_still_yields_its_documents(nested_docs):
    found = documents.find(nested_docs, "plan", "physics-priors")
    assert any("infrastructure" in str(d.path) for d in found)


def test_documents_are_attributed_to_the_owning_unit(nested_docs):
    found = documents.find(nested_docs, "plan", "physics-priors")
    assert {d.unit for d in found} == {"physics-priors"}


def test_a_nested_unit_claims_its_own_documents(tmp_path, grammar):
    docs = tmp_path / "docs"
    prog = docs / "research" / "physics-priors"
    expt = prog / "expt-1"
    (expt / "plans").mkdir(parents=True)
    (expt / "plans" / "01-a-Feb012026.md").write_text("# a\n")
    (prog / "plans").mkdir()
    (prog / "plans" / "01-b-Feb012026.md").write_text("# b\n")
    (prog / MARKER).write_text(
        "home: p\nunit: physics-priors\nkind: research-program\nhomes:\n  - p\n"
    )
    (expt / MARKER).write_text(
        "home: e\nunit: expt-1\nkind: experiment\n"
        "part_of: physics-priors\nhomes:\n  - e\n"
    )
    (tmp_path / "p").mkdir()
    (tmp_path / "e").mkdir()
    registry = Registry([docs, tmp_path], grammar)

    prog_plans = documents.find(registry, "plan", "physics-priors")
    assert [p.name for p in prog_plans] == ["01-b-Feb012026.md"]

    expt_plans = documents.find(registry, "plan", "expt-1")
    assert [p.name for p in expt_plans] == ["01-a-Feb012026.md"]


def test_find_without_a_unit_returns_everything(nested_docs):
    assert len(documents.find(nested_docs, "plan")) == 7


def test_a_container_nested_inside_itself_is_not_double_counted(tmp_path, grammar):
    """An archived experiment's own `plans/` folder, preserved under the
    parent's `plans/archive/`, is a `plans/` inside a `plans/` — plausible,
    not contrived. Matching the container by name at any depth means both
    the outer and the inner directory match, and without dedup the same
    file is yielded once per container that reaches it.
    """
    docs = tmp_path / "docs"
    prog = docs / "research" / "physics-priors"
    prog.mkdir(parents=True)
    (prog / MARKER).write_text(
        "home: p\nunit: physics-priors\nkind: research-program\nhomes:\n  - p\n"
    )
    (tmp_path / "p").mkdir()

    nested = prog / "plans" / "archive" / "plans"
    nested.mkdir(parents=True)
    (nested / "01-old-Jan012026.md").write_text("# old\n")

    registry = Registry([docs, tmp_path], grammar)
    found = documents.find(registry, "plan", "physics-priors")

    assert len(found) == 1
