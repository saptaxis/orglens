"""The one authored line the tree carries, and how old it is.

Everything else about an entity is derived (`activity.py`). This is not: a
status line is a human's summary of intent — *"vocabulary face is next and
should shrink before it is patched"* — and no amount of git archaeology
produces that sentence. Storing it does not create two truths, because there
is no other copy to disagree with.

What it can do is go stale, so it is always reported with its age. A five-month
-old line is then a dated quote rather than a claim about today.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

STATUS = re.compile(r"\*\*Status:\*\*\s*(.+)")


@dataclass(frozen=True)
class Status:
    text: str
    source: Path
    #: Unix seconds of the last edit, or None where that cannot be determined.
    edited: int | None = None

    @property
    def age_days(self) -> float | None:
        if self.edited is None:
            return None
        return (time.time() - self.edited) / 86400


def extract_status(content: str) -> str | None:
    """Pull the status line out of a document.

    Looks for `> **Status:** Active` and similar.
    """
    match = STATUS.search(content)
    if not match:
        return None
    raw = match.group(1).strip()
    raw = re.sub(r"\s*\(.*\)\s*$", "", raw)
    raw = re.sub(r",.*$", "", raw)
    # Preserve the author's case. Lowercasing here and re-capitalising at the
    # call site turned "POC" into "Poc" and "PhysicsX" into "Physicsx".
    return raw.strip()


def read_status(path: Path, declared: list[str] | None = None) -> Status | None:
    """The status line for an entity, and where it came from.

    Documents the grammar names are consulted first, then everything else
    alphabetically. Order matters more than it looks: scanning plainly by name
    picks `backlog.md` over `overview.md`, and `geocoding-results-Jun092026.md`
    over both. A document the grammar can describe outranks an ad-hoc one.

    Nothing names a *state file*. Move the line into whichever document you
    actually maintain and it is found there.
    """
    preferred = [path / name for name in (declared or []) if not name.endswith("/")]
    rest = sorted(p for p in path.glob("*.md") if p not in preferred)

    for candidate in preferred + rest:
        if not candidate.is_file():
            continue
        text = extract_status(candidate.read_text(errors="ignore"))
        if text:
            return Status(text=text, source=candidate, edited=_last_edit(candidate))
    return None


def _last_edit(path: Path) -> int | None:
    """When the document last changed, by git where possible.

    Reuses `activity`'s git plumbing rather than shelling out again: it is the
    module that already knows how to ask a repository when something moved, and
    a second copy here would be one more thing to keep in step. Falls back to
    mtime, which a fresh clone rewrites — hence the preference.
    """
    from orglens import activity

    root = activity._repo_root(path.parent)
    if root is not None:
        landed = activity._last_commit(root, path)
        if landed is not None:
            return landed
    try:
        return int(path.stat().st_mtime)
    except OSError:
        return None
