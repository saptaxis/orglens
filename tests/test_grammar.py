"""The grammar: three blocks, loaded literally, with nothing inferred."""

import pytest

from orglens.grammar import Grammar


class TestLoading:
    def test_entity_types_come_from_the_entities_block(self, grammar):
        assert set(grammar.entity_types) == {
            "client", "project", "research-program", "experiment",
        }

    def test_a_pattern_is_kept_verbatim(self, grammar):
        assert grammar.entity_types["project"].pattern == "projects/*"
        assert grammar.entity_types["experiment"].pattern == "expt-*"

    def test_artifact_types_carry_a_glob_and_prose(self, grammar):
        plan = grammar.artifact_types["plan"]
        assert plan.find == "plans/*.md"
        assert "NN-topic-MonDDYYYY.md" in plan.means

    def test_structure_is_attached_to_its_entity_type(self, grammar):
        structure = grammar.entity_types["project"].structure
        assert structure["overview.md"]
        assert set(structure) == {"overview.md", "specs/", "plans/", "logs/"}

    def test_files_and_directories_are_told_apart_by_the_trailing_slash(self, grammar):
        project = grammar.entity_types["project"]
        assert set(project.files) == {"overview.md"}
        assert set(project.directories) == {"specs/", "plans/", "logs/"}


class TestPlacement:
    def test_the_container_is_the_head_of_the_pattern(self, grammar):
        assert grammar.entity_types["project"].container == "projects"
        assert grammar.entity_types["research-program"].container == "research"

    def test_a_bare_pattern_has_no_container(self, grammar):
        """`expt-*` names the directory itself, so it sits in its parent."""
        assert grammar.entity_types["experiment"].container == ""

    def test_the_artifact_directory_is_the_head_of_the_glob(self, grammar):
        assert grammar.artifact_types["plan"].directory == "plans"


class TestMinimalDeclarations:
    def test_a_grammar_needs_only_a_driver_and_entities(self, tmp_path):
        path = tmp_path / "g.yaml"
        path.write_text("version: 2\ndriver: DECK.md\nentities:\n  deck: capabilities/*\n")

        grammar = Grammar.from_yaml(path)

        assert grammar.entity_types["deck"].pattern == "capabilities/*"
        assert grammar.entity_types["deck"].structure == {}
        assert grammar.artifact_types == {}
        assert grammar.driver == "DECK.md"

    def test_a_grammar_without_a_driver_is_refused(self, tmp_path):
        """Every entity has one document saying where it stands.

        Optional would mean a None branch in every consumer that is never
        taken, and a failure at status time instead of at load time.
        """
        path = tmp_path / "g.yaml"
        path.write_text("version: 2\nentities:\n  deck: capabilities/*\n")

        with pytest.raises(ValueError, match="must declare `driver`"):
            Grammar.from_yaml(path)

    def test_a_second_tree_is_just_a_second_file(self, tmp_path):
        """Nothing in the design assumes one grammar exists in the world."""
        path = tmp_path / "other.yaml"
        path.write_text(
            "version: 2\n"
            "driver: DECK.md\n"
            "entities:\n"
            "  deck: capabilities/*\n"
            "artifacts:\n"
            "  card:\n"
            "    find: cards/*.md\n"
            "    means: One instruction to one model.\n"
            "structure:\n"
            "  deck:\n"
            "    DECK.md: What the deck is for.\n"
        )

        grammar = Grammar.from_yaml(path)

        assert grammar.artifact_types["card"].find == "cards/*.md"
        assert grammar.entity_types["deck"].files == {"DECK.md": "What the deck is for."}

    def test_the_driver_is_consulted_first_whatever_the_kind(self, grammar):
        """One name per tree, so nothing has to look it up per kind."""
        for name in grammar.entity_types:
            assert grammar.documents_for(name)[0] == grammar.driver

    def test_the_driver_is_never_listed_twice(self, grammar):
        for name in grammar.entity_types:
            order = grammar.documents_for(name)
            assert order.count(grammar.driver) == 1


class TestMeans:
    def test_folded_yaml_prose_is_flattened_to_one_line(self, grammar):
        """`>` folding leaves newlines that would break a markdown table."""
        for artifact_type in grammar.artifact_types.values():
            assert "\n" not in artifact_type.means
            assert not artifact_type.means.endswith(" ")

    def test_every_declared_part_says_what_it_is_for(self, grammar):
        """A structure entry with no prose is a key nobody can use."""
        for entity_type in grammar.entity_types.values():
            for path, means in entity_type.structure.items():
                assert means.strip(), f"{entity_type.name}:{path} says nothing"


def test_a_missing_find_is_an_error_not_a_silent_empty_kind(tmp_path):
    path = tmp_path / "g.yaml"
    path.write_text(
        "version: 2\ndriver: overview.md\nartifacts:\n  plan:\n    means: no glob\n"
    )

    with pytest.raises(KeyError):
        Grammar.from_yaml(path)
