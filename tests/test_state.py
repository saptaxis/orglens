"""Tests for markdown state aggregation."""

import pytest
from pathlib import Path
from orglens.state import extract_status, extract_table_statuses


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


class TestTableStatusExtraction:
    def test_extracts_experiment_statuses(self):
        content = (
            "| # | Name | Status |\n"
            "|---|------|--------|\n"
            "| 1 | Agent Behavior | **Complete** |\n"
            "| 2 | World Model Study | **Active** |\n"
        )
        statuses = extract_table_statuses(content)
        assert statuses == [
            {"name": "Agent Behavior", "status": "complete"},
            {"name": "World Model Study", "status": "active"},
        ]

    def test_extracts_plan_statuses(self):
        content = (
            "| Plan | Scope | Status |\n"
            "|------|-------|--------|\n"
            "| 01 — Core Pipeline | ... | **Complete** |\n"
            "| 02 — CLI Commands | ... | **Pending** |\n"
        )
        statuses = extract_table_statuses(content)
        assert len(statuses) == 2
        assert statuses[0]["status"] == "complete"
        assert statuses[1]["status"] == "pending"

    def test_handles_no_bold_status(self):
        content = (
            "| Item | Status |\n"
            "|------|--------|\n"
            "| Foo | Done |\n"
        )
        statuses = extract_table_statuses(content)
        assert statuses[0]["status"] == "done"

    def test_no_table_returns_empty(self):
        content = "No tables here.\n"
        assert extract_table_statuses(content) == []
