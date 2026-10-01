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


def clean(raw: str) -> str:
    """The status text without a trailing parenthetical or a comma clause.

    Preserves the author's case. Lowercasing and re-capitalising turned
    "POC" into "Poc" and "PhysicsX" into "Physicsx".
    """
    raw = raw.strip()
    raw = re.sub(r"\s*\(.*\)\s*$", "", raw)
    raw = re.sub(r",.*$", "", raw)
    return raw.strip()
