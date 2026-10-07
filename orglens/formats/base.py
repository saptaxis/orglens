"""What a format is, and the clean-up both status readers share."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Format:
    """A document format: its suffix, how to read the status line out of a
    document, and the driver document `new` writes.

    Only what orglens uses today (org-support R5). A heading parser or a
    link reader joins when a second caller needs one, not before.
    """

    name: str
    suffix: str
    status: Callable[[str], str | None]
    #: (title, unit name, today as YYYY-MM-DD) -> the document's text
    stub: Callable[[str, str, str], str]
    #: (title, what it is for) -> a file a kind's `structure:` declares,
    #: seeded by `new` so whoever opens it knows what goes there.
    seed: Callable[[str, str], str]


#: Brackets a sentence does not end inside.
_OPEN, _CLOSE = "([{\"", ")]}\""


def clean(raw: str) -> str:
    """The status as one sentence of plain text: the first sentence, the
    format's markup already taken out by its reader.

    A status is one sentence (inwit's workflow), and a longer line is cut at
    the end of its first one --- never inside brackets or quotes. Cutting at
    the first comma, as this did, left "(sessions per unit" open, and
    dropped "packaging in progress" from "Code complete, packaging in
    progress". A final full stop goes, as it would in a list.

    Preserves the author's case. Lowercasing and re-capitalising turned
    "POC" into "Poc" and "PhysicsX" into "Physicsx".
    """
    text = " ".join(raw.split())
    depth, quoted = 0, False
    for i, ch in enumerate(text):
        if ch == '"':
            quoted = not quoted
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(depth - 1, 0)
        elif (ch in ".?!" and not depth and not quoted
              and text[i + 1:i + 2] == " " and not text[i + 2:i + 3].islower()):
            text = text[:i + 1]
            break
    return text.rstrip(".").strip()
