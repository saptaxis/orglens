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

import time
from dataclasses import dataclass
from pathlib import Path

from orglens import formats


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
    """The markdown status line, `> **Status:** Active` and similar.

    Kept for callers that hold markdown text; anything reading a file goes
    through `read_status`, which picks the reader by the file's format.
    """
    return formats.get("md").status(content)


def read_status(path: Path, declared: list[str] | None = None,
                prefer: str = "md") -> Status | None:
    """The status line for an entity, and where it came from.

    Precedence: the driver document the grammar names, then the other documents
    it describes, then every other document alphabetically. That order matters
    more than it looks — scanning plainly by name picks `backlog` over the
    overview, and a dated results file over both. Each declared name is
    resolved by stem in any format, the grammar's own (`prefer`) first (R11).

    Nothing names a *state file*. Move the line into whichever document you
    actually maintain and it is found there; the driver is only where it is
    looked for first.
    """
    preferred = _declared(path, declared, prefer)
    return _first_status(preferred + _rest(path, preferred))


def unit_status(paths: list[Path], declared: list[str] | None = None,
                prefer: str = "md") -> Status | None:
    """The status line for a unit that lives in several homes.

    The documents the grammar names, in every home, before any other document
    in any home. Home by home, a code repository listed first would answer
    from its README or changelog — which may well quote `**Status:**` while
    describing the syntax — before the documents home was asked for its
    driver.
    """
    preferred = [p for path in paths for p in _declared(path, declared, prefer)]
    status = _first_status(preferred)
    if status is not None:
        return status
    for path in paths:
        status = _first_status(_rest(path, preferred))
        if status is not None:
            return status
    return None


def _declared(path: Path, declared: list[str] | None, prefer: str) -> list[Path]:
    found: list[Path] = []
    for name in declared or []:
        if name.endswith("/"):
            continue
        match = formats.existing(path, name, prefer)
        if match is not None and match not in found:
            found.append(match)
    return found


def _rest(path: Path, preferred: list[Path]) -> list[Path]:
    return sorted(
        p for p in _entries(path)
        if p.is_file() and formats.is_document(p) and p not in preferred
    )


def _first_status(candidates: list[Path]) -> Status | None:
    for candidate in candidates:
        fmt = formats.of(candidate)
        if fmt is None:
            continue
        text = fmt.status(candidate.read_text(errors="ignore"))
        if text:
            return Status(text=text, source=candidate, edited=_last_edit(candidate))
    return None


def _entries(path: Path) -> list[Path]:
    try:
        return list(path.iterdir())
    except OSError:
        return []


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
