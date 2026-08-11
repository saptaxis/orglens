"""Discovery: patterns find things, nothing filters, nesting is never declared."""

import pytest

from orglens.topology import Topology


@pytest.fixture
def topo(docs_tree, grammar):
    return Topology(docs_tree, grammar)


class TestDiscovery:
    def test_every_matching_directory_is_found(self, topo):
        names = {e.name for e in topo.list_entities()}
        assert names == {
            "clipcompose", "orglens", "physics-priors",
            "expt-1-agent-behavior", "freightify",
        }

    def test_each_entity_carries_its_kind(self, topo):
        kinds = {e.name: e.entity_type for e in topo.list_entities()}
        assert kinds["clipcompose"] == "project"
        assert kinds["physics-priors"] == "research-program"
        assert kinds["expt-1-agent-behavior"] == "experiment"
        assert kinds["freightify"] == "client"

    def test_filtering_by_kind(self, topo):
        assert {e.name for e in topo.list_entities("project")} == {
            "clipcompose", "orglens",
        }

    def test_the_parent_is_whichever_entity_contains_it(self, topo):
        expt = next(e for e in topo.list_entities() if e.name.startswith("expt-"))
        assert expt.parent_name == "physics-priors"

    def test_a_top_level_entity_has_no_parent(self, topo):
        project = next(e for e in topo.list_entities() if e.name == "clipcompose")
        assert project.parent_name is None

    def test_ordering_is_stable(self, topo):
        assert [e.name for e in topo.list_entities()] == [
            e.name for e in topo.list_entities()
        ]


class TestNothingIsFiltered:
    def test_an_entity_missing_every_declared_file_is_still_found(self, docs_tree, grammar):
        """The old gate hid four real entities, two on a naming near-miss."""
        bare = docs_tree / "projects" / "resume"
        bare.mkdir()
        (bare / "resume-May222026.md").write_text("# Resume\n")

        assert "resume" in {e.name for e in Topology(docs_tree, grammar).list_entities()}

    def test_a_completely_empty_directory_is_an_entity(self, docs_tree, grammar):
        (docs_tree / "clients" / "itus-capital").mkdir()

        found = Topology(docs_tree, grammar).list_entities("client")

        assert {e.name for e in found} == {"freightify", "itus-capital"}

    def test_a_document_that_matches_no_naming_template_is_found(self, topo, docs_tree):
        """`01-stg-simulator-setup.md` has no date. 49 real plans look like this."""
        (docs_tree / "projects" / "clipcompose" / "plans" / "02-no-date.md").write_text("x")
        (docs_tree / "projects" / "clipcompose" / "plans" / "e5-03-prefixed-Apr142026.md").write_text("y")

        found = {a.name for a in topo.find_artifacts("plan", "clipcompose")}

        assert found == {
            "01-packaging-Feb252026.md", "02-no-date.md", "e5-03-prefixed-Apr142026.md",
        }


class TestNestingIsNeverDeclared:
    def test_a_client_can_grow_projects_with_no_grammar_edit(self, docs_tree, grammar):
        nested = docs_tree / "clients" / "freightify" / "projects" / "rfp-tooling"
        nested.mkdir(parents=True)

        found = {e.name: e for e in Topology(docs_tree, grammar).list_entities()}

        assert found["rfp-tooling"].entity_type == "project"
        assert found["rfp-tooling"].parent_name == "freightify"

    def test_a_project_can_grow_experiments(self, docs_tree, grammar):
        nested = docs_tree / "projects" / "clipcompose" / "expt-1-encoding"
        nested.mkdir(parents=True)

        found = {e.name: e for e in Topology(docs_tree, grammar).list_entities()}

        assert found["expt-1-encoding"].entity_type == "experiment"
        assert found["expt-1-encoding"].parent_name == "clipcompose"

    def test_nesting_three_deep_terminates(self, docs_tree, grammar):
        deep = docs_tree / "clients" / "freightify" / "projects" / "a" / "expt-1-b"
        deep.mkdir(parents=True)

        found = {e.name for e in Topology(docs_tree, grammar).list_entities()}

        assert {"freightify", "a", "expt-1-b"} <= found

    def test_children_of_reaches_any_depth(self, docs_tree, grammar):
        deep = docs_tree / "clients" / "freightify" / "projects" / "a" / "expt-1-b"
        deep.mkdir(parents=True)
        topo = Topology(docs_tree, grammar)

        client = topo.resolve("freightify")

        assert {c.name for c in topo.children_of(client)} == {"a", "expt-1-b"}


class TestResolve:
    def test_exact_match(self, topo):
        assert topo.resolve("clipcompose").name == "clipcompose"

    def test_prefix_match(self, topo):
        assert topo.resolve("clip").name == "clipcompose"

    def test_substring_match(self, topo):
        assert topo.resolve("agent-behavior").name == "expt-1-agent-behavior"

    def test_no_match_lists_what_there_is(self, topo):
        with pytest.raises(ValueError, match="Available"):
            topo.resolve("nonexistent")

    def test_an_ambiguous_prefix_refuses_to_guess(self, docs_tree, grammar):
        (docs_tree / "projects" / "clipboard").mkdir()

        with pytest.raises(ValueError, match="multiple"):
            Topology(docs_tree, grammar).resolve("clip")


class TestFindingDocuments:
    def test_across_the_whole_tree(self, topo):
        assert len(topo.find_artifacts("plan")) == 3

    def test_scoped_to_an_entity(self, topo):
        found = topo.find_artifacts("plan", "clipcompose")
        assert [a.name for a in found] == ["01-packaging-Feb252026.md"]

    def test_scoping_to_a_parent_includes_its_children(self, topo):
        """An experiment's plans belong to the program you asked about."""
        found = topo.find_artifacts("plan", "physics-priors")

        assert len(found) == 2
        assert {a.entity_name for a in found} == {"expt-1-agent-behavior"}

    def test_documents_are_attributed_to_the_entity_that_holds_them(self, topo):
        found = topo.find_artifacts("log", "physics-priors")
        assert [a.entity_name for a in found] == ["expt-1-agent-behavior"]

    def test_an_absent_directory_is_not_an_error(self, topo):
        assert topo.find_artifacts("spec", "freightify") == []


class TestWhatAnEntityActuallyHolds:
    def test_subdirectories_include_undeclared_ones(self, topo, docs_tree):
        """`archive/` and `presentation/` are real and in no grammar."""
        (docs_tree / "research" / "physics-priors" / "archive").mkdir()
        program = topo.resolve("physics-priors")

        assert "archive" in {d.name for d in topo.subdirectories(program)}

    def test_hidden_directories_are_left_out(self, topo, docs_tree):
        (docs_tree / "projects" / "clipcompose" / ".cache").mkdir()
        project = topo.resolve("clipcompose")

        assert ".cache" not in {d.name for d in topo.subdirectories(project)}

    def test_top_level_documents_are_listed(self, topo, docs_tree):
        (docs_tree / "projects" / "clipcompose" / "backlog.md").write_text("# Backlog\n")
        project = topo.resolve("clipcompose")

        assert {d.name for d in topo.documents(project)} == {
            "overview.md", "backlog.md",
        }


class TestCreation:
    def test_creating_an_entity_makes_what_the_grammar_describes(self, topo, docs_tree):
        path = topo.scaffold_entity("project", "new-tool")

        assert path == docs_tree / "projects" / "new-tool"
        assert (path / "overview.md").exists()
        assert (path / "specs").is_dir()
        assert (path / "plans").is_dir()
        assert (path / "logs").is_dir()

    def test_a_new_file_says_what_it_is_for(self, topo):
        path = topo.scaffold_entity("project", "new-tool")

        text = (path / "overview.md").read_text()
        assert "**Status:** Pending" in text
        assert "What it is, its stack, and where its state lives." in text

    def test_what_was_created_is_then_discovered(self, topo):
        topo.scaffold_entity("project", "new-tool")
        assert "new-tool" in {e.name for e in topo.list_entities()}

    def test_creating_inside_a_parent(self, topo):
        path = topo.scaffold_entity(
            "experiment", "expt-2-world-model", parent="physics-priors"
        )

        assert path.parent.name == "physics-priors"
        assert (path / "design.md").exists()
        assert (path / "findings").is_dir()

    def test_a_name_the_pattern_would_not_find_is_refused(self, topo):
        """Creating something invisible is the one thing `new` must not do."""
        with pytest.raises(ValueError, match="would not be found"):
            topo.scaffold_entity("experiment", "world-model", parent="physics-priors")

    def test_creating_over_an_existing_directory_is_refused(self, topo):
        with pytest.raises(ValueError, match="already exists"):
            topo.scaffold_entity("project", "clipcompose")

    def test_an_entity_with_no_declared_structure_is_just_a_directory(self, docs_tree, tmp_path):
        from orglens.grammar import Grammar

        path = tmp_path / "g.yaml"
        path.write_text("version: 2\nentities:\n  deck: capabilities/*\n")
        topo = Topology(docs_tree, Grammar.from_yaml(path))

        created = topo.scaffold_entity("deck", "writing")

        assert created.is_dir()
        assert [*created.iterdir()] == []
