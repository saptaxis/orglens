from __future__ import annotations

from pathlib import Path

from orglens.view import doc_url

ROOT = Path("/docs")
BASE = "http://localhost:8000"


def test_a_page_becomes_a_directory_url():
    """mkdocs directory_urls: a/b.md is served at /a/b/."""
    assert doc_url(ROOT / "projects/interview-prep/working-plan.md", ROOT, BASE) == (
        "http://localhost:8000/projects/interview-prep/working-plan/"
    )


def test_index_collapses_to_its_directory():
    assert doc_url(ROOT / "projects/gasco/index.md", ROOT, BASE) == (
        "http://localhost:8000/projects/gasco/"
    )


def test_a_directory_keeps_its_trailing_slash():
    assert doc_url(ROOT / "projects/orglens/plans", ROOT, BASE) == (
        "http://localhost:8000/projects/orglens/plans/"
    )


def test_the_docs_root_itself_is_the_base():
    assert doc_url(ROOT, ROOT, BASE) == "http://localhost:8000/"


def test_a_path_outside_the_tree_falls_back_to_the_filesystem():
    """A deck card or a sandbox packet is real but not served."""
    assert doc_url(Path("/elsewhere/card.md"), ROOT, BASE).startswith("file://")


def test_the_base_is_configurable():
    assert doc_url(ROOT / "a/b.md", ROOT, "https://docs.example.com") == (
        "https://docs.example.com/a/b/"
    )


def test_a_document_under_the_second_root_still_gets_a_served_url():
    """A unit can span more than one root — a document under the second one
    must not silently fall back to a `file://` link just because only the
    first root was checked."""
    other = Path("/code")
    assert doc_url(other / "notes.md", [ROOT, other], BASE) == (
        "http://localhost:8000/notes/"
    )


def test_a_document_under_neither_root_falls_back_to_the_filesystem():
    assert doc_url(
        Path("/elsewhere/notes.md"), [ROOT, Path("/code")], BASE
    ).startswith("file://")
