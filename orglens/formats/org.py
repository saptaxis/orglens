"""Org: the status line is the `#+STATUS:` keyword (org-support R7).

A file-level keyword because the status is a sentence someone writes, not
a value from a fixed set, and it stays visible under the title in the
reader, which hides only settings lines.
"""

from __future__ import annotations

import re

from orglens.formats.base import Format, clean

#: Org keywords are case-insensitive; `#+status:` is as valid as `#+STATUS:`.
STATUS = re.compile(r"^#\+STATUS:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def status(text: str) -> str | None:
    match = STATUS.search(text)
    return clean(match.group(1)) if match else None


def stub(title: str, name: str, today: str) -> str:
    return (
        f"#+TITLE: {title}\n"
        f"#+STATUS: Opened {today}. Nothing done yet.\n\n"
        "* What it is\n\n"
        f"What {name} is for, in a paragraph.\n\n"
        "* State tracking\n\n"
        "Where its state is written, and what to read to know where it stands.\n"
    )


FORMAT = Format(name="org", suffix=".org", status=status, stub=stub)
