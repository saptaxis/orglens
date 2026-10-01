"""The authored line: how it is read, which document it comes from, and its age."""

import time

from orglens.state import extract_status, read_status


class TestStatusExtraction:
    def test_extract_status_badge(self):
        content = '# Overview\n\n> **Status:** Active\n'
        assert extract_status(content) == "Active"

    def test_extract_status_with_parens(self):
        content = '> **Status:** Packaged and shipped (Plan 01 complete)\n'
        assert extract_status(content) == "Packaged and shipped"

    def test_extract_design_complete(self):
        content = '> **Status:** Design complete, implementation pending\n'
        assert extract_status(content) == "Design complete"

    def test_no_status_returns_none(self):
        content = "# Overview\n\nJust some text.\n"
        assert extract_status(content) is None

    def test_the_author_s_case_is_preserved(self):
        """Folding here turned POC into Poc and PhysicsX into Physicsx."""
        assert extract_status('> **Status:** POC working end to end\n') == (
            "POC working end to end"
        )
        assert extract_status('> **Status:** Prep for PhysicsX\n') == (
            "Prep for PhysicsX"
        )


class TestWhichDocumentTheLineComesFrom:
    def test_a_declared_document_outranks_an_ad_hoc_one(self, tmp_path):
        """Scanning by filename picks backlog.md over overview.md.

        Measured on the real tree: plain alphabetical order chose `backlog.md`
        for one entity and `geocoding-results-Jun092026.md` for another. The
        grammar already says which documents it can describe; that is the rank.
        """
        (tmp_path / "backlog.md").write_text("> **Status:** 14 open rows\n")
        (tmp_path / "overview.md").write_text("> **Status:** Active\n")

        found = read_status(tmp_path, ["overview.md"])

        assert found.text == "Active"
        assert found.source.name == "overview.md"

    def test_an_undeclared_document_is_used_when_nothing_declared_has_one(self, tmp_path):
        """`question.md` where the grammar says `research-question.md`.

        Two real research programs are shaped exactly this way. Nothing is
        declared as a state file, so the line is found wherever it lives.
        """
        (tmp_path / "question.md").write_text("> **Status:** Scoping\n")

        found = read_status(tmp_path, ["research-question.md"])

        assert found.text == "Scoping"
        assert found.source.name == "question.md"

    def test_declared_order_is_honoured(self, tmp_path):
        (tmp_path / "design.md").write_text("> **Status:** Second\n")
        (tmp_path / "overview.md").write_text("> **Status:** First\n")

        assert read_status(tmp_path, ["overview.md", "design.md"]).text == "First"
        assert read_status(tmp_path, ["design.md", "overview.md"]).text == "Second"

    def test_no_line_anywhere_is_not_an_error(self, tmp_path):
        (tmp_path / "overview.md").write_text("# Overview\n\nNothing to declare.\n")
        assert read_status(tmp_path, ["overview.md"]) is None

    def test_an_empty_directory_is_not_an_error(self, tmp_path):
        assert read_status(tmp_path, ["overview.md"]) is None

    def test_the_line_carries_its_age(self, tmp_path):
        """A five-month-old line is a dated quote, not a claim about today."""
        (tmp_path / "overview.md").write_text("> **Status:** Active\n")

        found = read_status(tmp_path, ["overview.md"])

        assert found.edited is not None
        assert found.age_days < 1
        assert found.edited <= int(time.time()) + 1

    def test_a_directory_is_never_read_as_a_document(self, tmp_path):
        (tmp_path / "specs").mkdir()
        (tmp_path / "overview.md").write_text("> **Status:** Active\n")

        assert read_status(tmp_path, ["specs/", "overview.md"]).text == "Active"


def test_status_is_read_from_an_org_driver(tmp_path):
    (tmp_path / "overview.org").write_text("#+TITLE: X\n#+STATUS: Active\n")
    status = read_status(tmp_path, ["overview"])
    assert status.text == "Active"
    assert status.source.name == "overview.org"


def test_the_grammars_format_wins_when_the_driver_exists_twice(tmp_path):
    (tmp_path / "overview.md").write_text("> **Status:** Old\n")
    (tmp_path / "overview.org").write_text("#+STATUS: New\n")
    assert read_status(tmp_path, ["overview"], prefer="org").text == "New"
    assert read_status(tmp_path, ["overview"], prefer="md").text == "Old"


def test_a_driver_declared_with_a_suffix_still_finds_an_org_file(tmp_path):
    (tmp_path / "overview.org").write_text("#+STATUS: Active\n")
    assert read_status(tmp_path, ["overview.md"]).text == "Active"


def test_other_documents_are_scanned_in_every_format(tmp_path):
    (tmp_path / "notes.org").write_text("#+STATUS: From notes\n")
    assert read_status(tmp_path, ["overview"]).text == "From notes"


def test_the_backlog_is_not_preferred_over_the_driver_by_name(tmp_path):
    (tmp_path / "backlog.org").write_text("#+STATUS: Backlog\n")
    (tmp_path / "overview.org").write_text("#+STATUS: Driver\n")
    assert read_status(tmp_path, ["overview"]).text == "Driver"


def test_a_unit_reads_a_driver_in_any_home_before_other_documents_in_the_first(tmp_path):
    from orglens.state import unit_status
    code, docs = tmp_path / "code", tmp_path / "docs"
    code.mkdir(); docs.mkdir()
    (code / "CHANGELOG.md").write_text("In markdown it is still `> **Status:**`.\n")
    (docs / "overview.org").write_text("#+TITLE: X\n#+STATUS: Real\n")
    status = unit_status([code, docs], ["overview"], "org")
    assert status.text == "Real" and status.source.name == "overview.org"


def test_a_unit_with_no_driver_anywhere_still_finds_a_status_in_other_documents(tmp_path):
    from orglens.state import unit_status
    code, docs = tmp_path / "code", tmp_path / "docs"
    code.mkdir(); docs.mkdir()
    (docs / "notes.md").write_text("> **Status:** From notes\n")
    assert unit_status([code, docs], ["overview"], "md").text == "From notes"
