"""Tests for snapshot generation."""

import pytest
from pathlib import Path
from orglens.snapshot import generate_snapshot
from orglens.topology import Topology


@pytest.fixture
def topo(config, grammar):
    return Topology(config.docs_root, grammar)


class TestSnapshotGeneration:
    def test_generates_markdown(self, topo, config):
        snapshot = generate_snapshot(topo, config)
        assert isinstance(snapshot, str)
        assert len(snapshot) > 0

    def test_contains_header(self, topo, config):
        snapshot = generate_snapshot(topo, config)
        assert "# Topology Snapshot" in snapshot

    def test_contains_projects(self, topo, config):
        snapshot = generate_snapshot(topo, config)
        assert "clipcompose" in snapshot
        assert "orglens" in snapshot

    def test_contains_research_programs(self, topo, config):
        snapshot = generate_snapshot(topo, config)
        assert "physics-priors" in snapshot

    def test_contains_experiments(self, topo, config):
        snapshot = generate_snapshot(topo, config)
        assert "expt-1-agent-behavior" in snapshot

    def test_contains_status(self, topo, config):
        snapshot = generate_snapshot(topo, config)
        assert "active" in snapshot.lower() or "Active" in snapshot

    def test_contains_recent_artifacts(self, topo, config):
        snapshot = generate_snapshot(topo, config)
        # Should mention plans that exist
        assert "plan" in snapshot.lower()

    def test_contains_grammar_summary(self, topo, config):
        snapshot = generate_snapshot(topo, config)
        assert "Entity Types" in snapshot or "Grammar" in snapshot

    def test_writes_to_file(self, topo, config, tmp_path):
        snapshot_path = tmp_path / "snapshot.md"
        generate_snapshot(topo, config, output_path=snapshot_path)
        assert snapshot_path.exists()
        content = snapshot_path.read_text()
        assert "# Topology Snapshot" in content
