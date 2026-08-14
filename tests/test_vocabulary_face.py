"""The vocabulary is declared once. This test is why.

Before plan 08 the tree's vocabulary lived in three places: `grammars/default.yaml`,
four Python modules that hardcoded the same strings, and hand-written tables in
`SKILL.md`. All three drifted — `orglens list --type deck` raised `KeyError`,
88 documents were invisible to `find`, and the skill's table disagreed with the
grammar about which files a research program needs.

Prose did not stop that. This does: every noun the grammar declares is banned
from the engine, so bypassing the grammar fails a test instead of shipping.

The banned list is *derived from the grammar*, not hand-maintained. Adding a
type to the YAML automatically forbids hardcoding it.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from orglens.grammar import Grammar

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "orglens"

#: The vocabulary face. `activity.py` and `view.py` are exempt: they derive what
#: is true rather than declaring what may exist, and they were built after the
#: drift they would otherwise be blamed for. `workflow/` has its own check.
FACE = ("cli.py", "check.py", "config.py", "declaration.py", "documents.py",
        "grammar.py", "homes.py", "reference.py", "snapshot.py", "state.py",
        "topology.py", "units.py")


def default_grammar() -> Grammar:
    return Grammar.from_yaml(ENGINE / "grammars" / "default.yaml")


def vocabulary() -> set[str]:
    """Every noun the grammar declares. None of these belong in Python."""
    grammar = default_grammar()
    words: set[str] = set(grammar.entity_types) | set(grammar.artifact_types)
    for entity_type in grammar.entity_types.values():
        for key in entity_type.structure:
            words.add(key.rstrip("/").removesuffix(".md"))
        # "projects" out of "projects/*", "expt-" out of "expt-*"
        words.add(entity_type.pattern.split("*")[0].strip("/"))
    for artifact_type in grammar.artifact_types.values():
        words.add(artifact_type.find.split("/")[0])
    return {w for w in words if w}


def face_sources() -> list[Path]:
    return [ENGINE / name for name in FACE if (ENGINE / name).exists()]


def code_strings(path: Path) -> list[tuple[int, str]]:
    """Every string the module *acts on*, and every name it defines.

    Docstrings and comments are deliberately excluded. Prose has to be able to
    say "the gate hid four research programs" in order to explain why the gate
    is gone; what must not happen is code *deciding* on that word. A comment
    cannot route, look up, or filter.
    """
    tree = ast.parse(path.read_text())
    documentation = {
        node.body[0].value
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }

    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node not in documentation:
                found.append((node.lineno, node.value))
        elif isinstance(node, ast.Attribute):
            found.append((node.lineno, node.attr))
        elif isinstance(node, ast.Name):
            found.append((node.lineno, node.id))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.append((node.lineno, node.name))
    return found


@pytest.mark.parametrize("word", sorted(vocabulary()))
def test_no_declared_noun_is_hardcoded_in_the_face(word: str):
    pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
    hits = []
    for path in face_sources():
        for line, text in code_strings(path):
            if pattern.search(text):
                hits.append(f"{path.name}:{line}: {text!r}")
    assert not hits, (
        f"{word!r} is declared in the grammar. The engine must ask the grammar "
        f"for it rather than knowing it:\n" + "\n".join(hits)
    )


def test_every_module_in_the_face_is_accounted_for():
    """A new module in the vocabulary face joins the check, or the check rots."""
    present = {
        p.name for p in ENGINE.glob("*.py")
        if p.name not in ("__init__.py", "activity.py", "view.py")
    }
    assert present == set(FACE), (
        "modules in the vocabulary face but not checked: "
        f"{sorted(present - set(FACE))}; listed but missing: "
        f"{sorted(set(FACE) - present)}"
    )


def test_the_grammar_is_three_blocks_and_two_scalars():
    """Nine keys became three blocks. Anything more needs an argument, in a diff.

    `driver` is the one scalar that earned its place: every entity has one
    document saying where it stands, and the engine may not know its name.
    """
    import yaml

    data = yaml.safe_load((ENGINE / "grammars" / "default.yaml").read_text())
    assert set(data) == {"version", "driver", "entities", "artifacts", "structure"}


def test_entity_patterns_are_relative_so_nesting_is_never_declared():
    """`research/*/expt-*` pinned experiments one level below a program.

    Depth is not the grammar's business: an experiment is `expt-*` wherever it
    sits, which is what lets a client grow projects without a grammar edit.
    """
    for entity_type in default_grammar().entity_types.values():
        assert entity_type.pattern.count("*") == 1, entity_type
        assert not entity_type.pattern.startswith("/"), entity_type
        head = entity_type.pattern.split("*")[0]
        assert head.count("/") <= 1, (
            f"{entity_type.name!r} pins a depth in its pattern: {entity_type.pattern!r}"
        )
