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

    def test_snapshot_attributes_artifacts_to_experiments(self, topo, config):
        """Artifacts under a research program should show which experiment they're from."""
        snapshot = generate_snapshot(topo, config)
        # After fix, experiment artifacts should be labeled with experiment name
        # e.g. "**Plans** (expt-1-agent-behavior): 2"
        # rather than just "**Plans:** 2" with no attribution
        lines = snapshot.split("\n")
        for line in lines:
            if "01-testbed-Feb032026.md" in line:
                # Find the artifact header above this line
                idx = lines.index(line)
                header_found = False
                for j in range(idx, max(0, idx-4), -1):
                    if lines[j].startswith("**") and "expt-1-agent-behavior" in lines[j]:
                        header_found = True
                        break
                assert header_found, (
                    f"Plan artifact not attributed to experiment in header. "
                    f"Context: {lines[max(0,idx-3):idx+1]}"
                )
                break
        else:
            pytest.fail("Plan artifact not found in snapshot at all")

    def test_writes_to_file(self, topo, config, tmp_path):
        snapshot_path = tmp_path / "snapshot.md"
        generate_snapshot(topo, config, output_path=snapshot_path)
        assert snapshot_path.exists()
        content = snapshot_path.read_text()
        assert "# Topology Snapshot" in content
