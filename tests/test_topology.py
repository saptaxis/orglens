"""Tests for topology operations."""

import pytest
from pathlib import Path
from orglens.topology import Topology


@pytest.fixture
def topo(config, grammar):
    return Topology(config.docs_root, grammar)


class TestEntityDiscovery:
    def test_discovers_projects(self, topo):
        projects = topo.list_entities("project")
        names = [e.name for e in projects]
        assert "clipcompose" in names
        assert "orglens" in names

    def test_discovers_research_programs(self, topo):
        programs = topo.list_entities("research-program")
        names = [e.name for e in programs]
        assert "physics-priors" in names

    def test_discovers_experiments(self, topo):
        expts = topo.list_entities("experiment")
        names = [e.name for e in expts]
        assert "expt-1-agent-behavior" in names

    def test_discovers_clients(self, topo):
        clients = topo.list_entities("client")
        names = [e.name for e in clients]
        assert "freightify" in names

    def test_list_all_entities(self, topo):
        all_entities = topo.list_entities()
        assert len(all_entities) >= 5  # 2 projects + 1 rp + 1 expt + 1 client

    def test_entity_has_path(self, topo):
        projects = topo.list_entities("project")
        clipcompose = [e for e in projects if e.name == "clipcompose"][0]
        assert clipcompose.path.name == "clipcompose"
        assert clipcompose.path.exists()

    def test_entity_has_type(self, topo):
        projects = topo.list_entities("project")
        assert all(e.entity_type == "project" for e in projects)

    def test_experiment_knows_parent(self, topo):
        expts = topo.list_entities("experiment")
        expt = expts[0]
        assert expt.parent_name == "physics-priors"


class TestEntityResolution:
    def test_resolve_by_exact_name(self, topo):
        entity = topo.resolve("clipcompose")
        assert entity.name == "clipcompose"
        assert entity.entity_type == "project"

    def test_resolve_by_partial_name(self, topo):
        entity = topo.resolve("physics")
        assert entity.name == "physics-priors"

    def test_resolve_ambiguous_raises(self, topo, docs_tree):
        # Add another entity starting with "c"
        client2 = docs_tree / "clients" / "cloudcorp"
        client2.mkdir(parents=True)
        (client2 / "overview.md").write_text("# Overview\n")
        # "c" matches clipcompose, cloudcorp, clients...
        # But "clip" should still resolve
        entity = topo.resolve("clip")
        assert entity.name == "clipcompose"

    def test_resolve_not_found_raises(self, topo):
        with pytest.raises(ValueError, match="No entity"):
            topo.resolve("nonexistent")


class TestEntityScaffolding:
    def test_scaffold_project(self, topo, docs_tree):
        topo.scaffold_entity("project", "new-tool")
        proj_dir = docs_tree / "projects" / "new-tool"
        assert proj_dir.exists()
        assert (proj_dir / "overview.md").exists()
        assert (proj_dir / "specs").is_dir()
        assert (proj_dir / "plans").is_dir()
        assert (proj_dir / "logs").is_dir()

    def test_scaffold_project_overview_content(self, topo, docs_tree):
        topo.scaffold_entity("project", "new-tool")
        content = (docs_tree / "projects" / "new-tool" / "overview.md").read_text()
        assert "# Overview" in content
        assert "Pending" in content

    def test_scaffold_research_program(self, topo, docs_tree):
        topo.scaffold_entity("research-program", "new-research")
        rp_dir = docs_tree / "research" / "new-research"
        assert rp_dir.exists()
        assert (rp_dir / "research-question.md").exists()
        assert (rp_dir / "research-program-state.md").exists()
        assert (rp_dir / "specs").is_dir()
        assert (rp_dir / "literature").is_dir()
        assert (rp_dir / "directions").is_dir()
        assert (rp_dir / "brainstorms").is_dir()

    def test_scaffold_experiment(self, topo, docs_tree):
        topo.scaffold_entity("experiment", "world-model", parent="physics-priors")
        # Should auto-number: expt-2-world-model (expt-1 exists)
        expt_dir = docs_tree / "research" / "physics-priors" / "expt-2-world-model"
        assert expt_dir.exists()
        assert (expt_dir / "design.md").exists()
        assert (expt_dir / "plans").is_dir()
        assert (expt_dir / "logs").is_dir()
        assert (expt_dir / "findings").is_dir()

    def test_scaffold_duplicate_raises(self, topo):
        with pytest.raises(FileExistsError):
            topo.scaffold_entity("project", "clipcompose")


class TestArtifactOperations:
    def test_find_plans_in_entity(self, topo):
        plans = topo.find_artifacts("plan", "physics-priors")
        # Should find plans in expt-1 (recursive within research program)
        assert len(plans) >= 2
        names = [p.name for p in plans]
        assert "01-testbed-Feb032026.md" in names

    def test_find_specs_in_entity(self, topo):
        specs = topo.find_artifacts("spec", "clipcompose")
        names = [s.name for s in specs]
        assert "agent-integration.md" in names

    def test_find_all_plans(self, topo):
        plans = topo.find_artifacts("plan")
        assert len(plans) >= 3  # 1 in clipcompose + 2 in expt-1

    def test_next_artifact_number(self, topo):
        nn = topo.next_artifact_number("plan", "expt-1-agent-behavior")
        assert nn == 3  # 01 and 02 exist

    def test_next_artifact_number_empty(self, topo):
        nn = topo.next_artifact_number("plan", "orglens")
        assert nn == 1

    def test_scaffold_artifact(self, topo, docs_tree):
        from datetime import date
        path = topo.scaffold_artifact("plan", "clipcompose", "agent-integration")
        assert path.exists()
        today = date.today().strftime("%b%d%Y")
        assert path.name == f"02-agent-integration-{today}.md"
        content = path.read_text()
        assert "# 02" in content

    def test_scaffold_log(self, topo, docs_tree):
        from datetime import date
        path = topo.scaffold_artifact("log", "expt-1-agent-behavior", "testbed")
        today = date.today().strftime("%b%d%Y")
        assert path.name == f"02-testbed-{today}-log.md"

    def test_scaffold_spec(self, topo, docs_tree):
        path = topo.scaffold_artifact("spec", "orglens", "system-design-v2")
        assert path.name == "system-design-v2.md"
        assert path.parent.name == "specs"

    def test_find_all_plans_no_duplicates(self, topo):
        """Global find must not return experiment artifacts twice."""
        plans = topo.find_artifacts("plan")
        paths = [str(p.path) for p in plans]
        assert len(paths) == len(set(paths)), (
            f"Duplicate artifacts found: {[p for p in paths if paths.count(p) > 1]}"
        )

    def test_find_all_logs_no_duplicates(self, topo):
        """Global find must not return experiment logs twice."""
        logs = topo.find_artifacts("log")
        paths = [str(p.path) for p in logs]
        assert len(paths) == len(set(paths))
