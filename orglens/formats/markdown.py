"""Markdown: the status line is `> **Status:** ...`."""

from __future__ import annotations

import re

from orglens.formats.base import Format, clean

STATUS = re.compile(r"\*\*Status:\*\*\s*(.+)")


def status(text: str) -> str | None:
    match = STATUS.search(text)
    return clean(match.group(1)) if match else None


def stub(title: str, name: str, today: str) -> str:
    return (
        f"# {title}\n\n"
        f"> **Status:** Opened {today}. Nothing done yet.\n\n"
        "## What it is\n\n"
        f"What {name} is for, in a paragraph.\n\n"
        "## State tracking\n\n"
        "Where its state is written, and what to read to know where it stands.\n"
    )


def seed(title: str, text: str) -> str:
    return f"# {title}\n" + (f"\n{text}\n" if text else "")


FORMAT = Format(name="md", suffix=".md", status=status, stub=stub, seed=seed)
