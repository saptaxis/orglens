"""The contract every registered format passes (org-support R17).

Parametrised over the registry, so a format added later is held to the same
tests without anyone writing new ones.
"""

from pathlib import Path

import pytest

from orglens import formats

ALL = sorted(formats.FORMATS)


@pytest.mark.parametrize("name", ALL)
def test_the_stub_carries_a_status_its_own_reader_finds(name):
    fmt = formats.get(name)
    text = fmt.stub("Overview", "clipcompose", "2026-09-26")
    assert fmt.status(text) == "Opened 2026-09-26; nothing done yet"


@pytest.mark.parametrize("name", ALL)
def test_the_stub_names_the_unit_and_the_title(name):
    text = formats.get(name).stub("Overview", "clipcompose", "2026-09-26")
    assert "Overview" in text and "clipcompose" in text


def test_markdown_status_line():
    assert formats.get("md").status("# X\n\n> **Status:** Active\n") == "Active"


def test_org_status_keyword():
    assert formats.get("org").status("#+TITLE: X\n#+STATUS: Active\n") == "Active"


def test_org_status_keyword_is_case_insensitive_like_org():
    assert formats.get("org").status("#+status: Parked\n") == "Parked"


@pytest.mark.parametrize("name", ALL)
def test_status_clean_up_is_shared(name):
    """The first sentence, whole: a comma or a parenthesis is part of it."""
    fmt = formats.get(name)
    line = ("> **Status:** Active, since May (see log). Next: more.\n" if name == "md"
            else "#+STATUS: Active, since May (see log). Next: more.\n")
    assert fmt.status(line) == "Active, since May (see log)"


@pytest.mark.parametrize("name", ALL)
def test_a_sentence_does_not_end_inside_brackets_or_quotes(name):
    fmt = formats.get(name)
    body = 'Released (sessions per unit. Mostly) and "Done. Really" shipped. Next.'
    line = f"> **Status:** {body}\n" if name == "md" else f"#+STATUS: {body}\n"
    assert fmt.status(line) == 'Released (sessions per unit. Mostly) and "Done. Really" shipped'


def test_org_markup_is_plain_text():
    org = formats.get("org")
    line = ("#+STATUS: 0.6.0: the tree (=orglens tree=, =--under=), *bold* /it/, "
            "see [[file:log.org][the log]] and [[file:x.org]] --- LOW--MED\n")
    assert org.status(line) == (
        "0.6.0: the tree (orglens tree, --under), bold it, see the log and x.org "
        "\u2014 LOW\u2013MED")


def test_org_slashes_in_a_path_are_not_italics():
    assert formats.get("org").status("#+STATUS: in notes/p1/list here\n") == "in notes/p1/list here"


def test_nested_org_emphasis_is_all_dropped():
    assert formats.get("org").status("#+STATUS: */Name/ is provisional*\n") == "Name is provisional"


def test_markdown_markup_is_plain_text():
    md = formats.get("md")
    line = "> **Status:** **Bold** `code` [the log](log.md), snake_case_name stays\n"
    assert md.status(line) == "Bold code the log, snake_case_name stays"


def test_a_file_with_no_status_has_none():
    for name in ALL:
        assert formats.get(name).status("just text\n") is None


def test_suffixes_are_every_registered_format():
    assert set(formats.SUFFIXES) == {".md", ".org"}


def test_is_document_knows_only_registered_suffixes(tmp_path):
    for name in ("a.md", "a.org", "a.png", ".nav.yml", "session.jsonl", "a.txt"):
        (tmp_path / name).write_text("x")
    kept = sorted(p.name for p in tmp_path.iterdir() if formats.is_document(p))
    assert kept == ["a.md", "a.org"]


def test_of_returns_the_format_of_a_path():
    assert formats.of(Path("x/overview.org")).name == "org"
    assert formats.of(Path("x/overview.md")).name == "md"
    assert formats.of(Path("x/figure.png")) is None


def test_stem_strips_only_a_registered_suffix():
    assert formats.stem("overview.md") == "overview"
    assert formats.stem("overview.org") == "overview"
    assert formats.stem("overview") == "overview"
    assert formats.stem("notes.txt") == "notes.txt"


def test_ordered_puts_the_preferred_suffix_first():
    assert formats.ordered("org")[0] == ".org"
    assert formats.ordered("md")[0] == ".md"
    assert set(formats.ordered("org")) == set(formats.SUFFIXES)


def test_existing_prefers_the_grammars_format_when_both_exist(tmp_path):
    (tmp_path / "overview.md").write_text("x")
    (tmp_path / "overview.org").write_text("x")
    assert formats.existing(tmp_path, "overview", prefer="org").name == "overview.org"
    assert formats.existing(tmp_path, "overview", prefer="md").name == "overview.md"


def test_the_grammars_format_wins_over_a_suffix_as_written(tmp_path):
    """Read as written first, `overview.md` under `format: org` was read
    while `check` said `overview.org` was."""
    (tmp_path / "DECK.md").write_text("x")
    (tmp_path / "DECK.org").write_text("x")
    assert formats.existing(tmp_path, "DECK.md", prefer="org").name == "DECK.org"
    assert formats.existing(tmp_path, "DECK.org", prefer="md").name == "DECK.md"


def test_existing_finds_the_other_format_when_the_named_one_is_absent(tmp_path):
    (tmp_path / "overview.org").write_text("x")
    assert formats.existing(tmp_path, "overview.md").name == "overview.org"


def test_existing_is_none_when_nothing_is_there(tmp_path):
    assert formats.existing(tmp_path, "overview") is None


def test_file_globs_expand_a_bare_pattern_to_every_suffix():
    assert sorted(formats.file_globs("*")) == ["*.md", "*.org"]
    assert sorted(formats.file_globs("[0-9][0-9]-*")) == ["[0-9][0-9]-*.md", "[0-9][0-9]-*.org"]


def test_file_globs_leave_an_unregistered_suffix_alone():
    assert formats.file_globs("*.txt") == ["*.txt"]


@pytest.mark.parametrize("name", ALL)
def test_an_empty_status_is_none_not_the_next_line(name):
    text = ("# X\n\n> **Status:**\nnext line\n" if name == "md"
            else "#+TITLE: X\n#+STATUS:\n* Heading one\n")
    assert formats.get(name).status(text) is None


def test_an_org_status_in_a_block_is_not_the_documents():
    org = formats.get("org")
    example = "#+begin_src org\n#+STATUS: example only\n#+end_src\n"
    assert org.status("#+TITLE: x\n" + example) is None
    assert org.status("#+TITLE: x\n" + example + "#+STATUS: Real\n") == "Real"
    assert org.status("#+BEGIN_EXAMPLE\n#+STATUS: no\n#+END_EXAMPLE\n#+STATUS: Yes\n") == "Yes"


def test_a_markdown_status_in_a_fence_is_not_the_documents():
    md = formats.get("md")
    fence = "```\n> **Status:** in a fence\n```\n"
    assert md.status("# X\n\n" + fence) is None
    assert md.status("# X\n\n" + fence + "\n> **Status:** Real\n") == "Real"
