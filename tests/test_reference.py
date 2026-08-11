"""The skill's reference is generated, and the committed copy has to be current.

`SKILL.md` used to carry the same tables by hand, and they drifted: the skill
named one required file for a research program where the grammar named two.
This test is the reason that cannot happen again — the committed file is
compared against what the grammar renders today.
"""

from pathlib import Path

from orglens.grammar import Grammar
from orglens.reference import render

ROOT = Path(__file__).resolve().parents[1]
COMMITTED = ROOT / "skills" / "org-context" / "references" / "grammar-reference.md"


def test_the_committed_reference_matches_the_grammar():
    grammar = Grammar.from_yaml(ROOT / "orglens" / "grammars" / "default.yaml")

    assert COMMITTED.read_text() == render(grammar), (
        "The vocabulary reference is behind the grammar. Regenerate it:\n"
        f"  orglens reference --out {COMMITTED}"
    )


def test_it_renders_every_kind_the_grammar_declares(grammar):
    text = render(grammar)

    for name, entity_type in grammar.entity_types.items():
        assert f"`{name}`" in text
        assert f"`{entity_type.pattern}`" in text
    for name, artifact_type in grammar.artifact_types.items():
        assert f"`{artifact_type.find}`" in text
        assert artifact_type.means in text


def test_it_says_nothing_about_any_particular_tree(grammar, docs_tree):
    """A committed file must not depend on one machine's private docs."""
    text = render(grammar)

    assert "clipcompose" not in text
    assert str(docs_tree) not in text


def test_the_skill_no_longer_restates_the_vocabulary(grammar):
    """The third declaration. It is gone, and this is what keeps it gone.

    Only the body is checked, and only the filenames. The frontmatter has to
    keep saying "where do plans go" — those are the phrases that make the skill
    fire, not a claim about what a directory contains. What must not come back
    is the table of key files, which is the copy that drifted.
    """
    text = (ROOT / "skills" / "org-context" / "SKILL.md").read_text()
    body = text.split("---", 2)[-1]

    for entity_type in grammar.entity_types.values():
        for declared in entity_type.files:
            assert declared not in body, (
                f"SKILL.md names {declared!r}; the reference is generated for this"
            )
