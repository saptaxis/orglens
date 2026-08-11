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
