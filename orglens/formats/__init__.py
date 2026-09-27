"""Document formats: markdown always, org beside it, others later (R1, R4).

Every glob and every status read in orglens goes through here, so a format
is one new module and a line in `FORMATS`, and nothing else in the engine
names a suffix.
"""

from __future__ import annotations

from pathlib import Path

from orglens.formats import markdown, org
from orglens.formats.base import Format

FORMATS: dict[str, Format] = {f.name: f for f in (markdown.FORMAT, org.FORMAT)}
SUFFIXES: tuple[str, ...] = tuple(f.suffix for f in FORMATS.values())

__all__ = ["Format", "FORMATS", "SUFFIXES", "get", "of", "is_document",
           "stem", "ordered", "existing", "file_globs"]


def get(name: str) -> Format:
    try:
        return FORMATS[name]
    except KeyError:
        known = ", ".join(sorted(FORMATS))
        raise ValueError(f"unknown format '{name}'; known: {known}") from None


def of(path: Path) -> Format | None:
    """The format a file is in, by its suffix, or None if it is not a document."""
    for fmt in FORMATS.values():
        if path.suffix == fmt.suffix:
            return fmt
    return None


def is_document(path: Path) -> bool:
    return path.suffix in SUFFIXES


def stem(name: str) -> str:
    """`overview.md` and `overview.org` are both `overview`. A suffix no
    format registers is part of the name and stays."""
    path = Path(name)
    return name[: -len(path.suffix)] if path.suffix in SUFFIXES else name


def ordered(prefer: str) -> tuple[str, ...]:
    """Every suffix, the preferred format's first."""
    first = get(prefer).suffix
    return (first,) + tuple(s for s in SUFFIXES if s != first)


def existing(directory: Path, name: str, prefer: str = "md") -> Path | None:
    """The file `name` refers to in `directory`, in whichever format it is.

    A name written with a suffix (`DECK.md`, as a grammar may still say) is
    tried as written first; then the stem under each suffix, the preferred
    format first. When one stem exists in two formats the preferred wins
    (R11) — `check` is what reports the pair.
    """
    candidates: list[Path] = []
    if Path(name).suffix in SUFFIXES:
        candidates.append(directory / name)
    base = stem(name)
    candidates += [directory / f"{base}{s}" for s in ordered(prefer)]
    for path in candidates:
        if path.is_file():
            return path
    return None


def file_globs(pattern: str) -> list[str]:
    """The globs a stem pattern means: one per registered suffix.

    `*` is `*.md` and `*.org`, never an image or a `.nav.yml` (R10). A
    pattern that already carries a suffix no format registers (`*.txt`)
    is left as written.
    """
    if Path(pattern).suffix:
        return [pattern]
    return [f"{pattern}{s}" for s in SUFFIXES]
