"""Org: the status line is the `#+STATUS:` keyword (org-support R7).

A file-level keyword because the status is a sentence someone writes, not
a value from a fixed set, and it stays visible under the title in the
reader, which hides only settings lines.
"""

from __future__ import annotations

import re

from orglens.formats.base import Format, clean

#: Org keywords are case-insensitive; `#+status:` is as valid as `#+STATUS:`.
#: Within its own line: an empty `#+STATUS:` is no status, not the next line.
STATUS = re.compile(r"^#\+STATUS:[ \t]*(\S.*?)[ \t]*$", re.IGNORECASE | re.MULTILINE)
#: `#+begin_src` ... `#+end_src`, and every other block: an example of a
#: status line in a document is not that document's status.
BLOCK = re.compile(r"^[ \t]*#\+begin_(\w+)\b.*?^[ \t]*#\+end_\1\b[^\n]*",
                   re.IGNORECASE | re.MULTILINE | re.DOTALL)


#: `[[target][description]]` and `[[target]]`.
LINK = re.compile(r"\[\[([^\]]+)\](?:\[([^\]]+)\])?\]")
#: Verbatim, code, bold and italic, with org's own boundaries: a marker
#: opens after a space or bracket and closes before one, so a path's
#: slashes are not italics.
EMPHASIS = re.compile(r"(?<![\w/=~*])([=~*/])(?=\S)(.+?)(?<=\S)\1(?![\w/=~*])")


def plain(raw: str) -> str:
    """A line of org as plain text: links by their description, emphasis
    and verbatim marks dropped, `---` and `--` as the dashes they render."""
    text = LINK.sub(lambda m: m.group(2) or re.sub(r"^file:", "", m.group(1)), raw)
    return _unmark(text)


def _unmark(text: str) -> str:
    """Emphasis dropped, nested included; dashes converted outside verbatim
    and code only, where `=--under=` is a flag."""
    pieces, at = [], 0
    for m in EMPHASIS.finditer(text):
        pieces.append(_dashes(text[at:m.start()]))
        inner = m.group(2)
        pieces.append(inner if m.group(1) in "=~" else _unmark(inner))
        at = m.end()
    pieces.append(_dashes(text[at:]))
    return "".join(pieces)


def _dashes(text: str) -> str:
    return text.replace("---", "\u2014").replace("--", "\u2013")


def status(text: str) -> str | None:
    match = STATUS.search(BLOCK.sub("", text))
    return clean(plain(match.group(1))) if match else None


def stub(title: str, name: str, today: str) -> str:
    return (
        f"#+TITLE: {title}\n"
        f"#+STATUS: Opened {today}; nothing done yet.\n\n"
        "* What it is\n\n"
        f"What {name} is for, in a paragraph.\n\n"
        "* State tracking\n\n"
        "Where its state is written, and what to read to know where it stands.\n"
    )


def seed(title: str, text: str) -> str:
    return f"#+TITLE: {title}\n" + (f"\n{text}\n" if text else "")


FORMAT = Format(name="org", suffix=".org", status=status, stub=stub, seed=seed)
