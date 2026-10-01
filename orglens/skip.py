"""Which folders a walk never enters. One rule for every walk.

Hidden folders always; beyond them, the names in config's `skip:`, or the
default when config has none. Set once per process, by whatever makes a
config the one in force (`Config.current`), before anything walks.

A setting rather than a parameter: the walkers are cached per process and
called with a path alone from a dozen places, and the list is constant for
a process — one command is one process.
"""

from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path

#: Build output and dependency folders: never declarations or documents, and
#: the bulk of a code repository's directory count. `site` is MkDocs' build.
DEFAULT: tuple[str, ...] = (
    "node_modules", "__pycache__", "*.egg-info", "site-packages",
    "venv", "env", "build", "dist", "target", "site",
)

_in_force: tuple[str, ...] = DEFAULT


def use(patterns) -> None:
    """Make `patterns` the list every walk skips, from here on."""
    global _in_force
    _in_force = tuple(patterns)


def skipped(name: str) -> bool:
    """Whether a folder of this name is never entered. `fnmatchcase`, not
    `fnmatch`: macOS folds case, and a rule must mean the same everywhere."""
    return name.startswith(".") or any(fnmatchcase(name, p) for p in _in_force)


def descend(entry: Path) -> bool:
    """Whether a walk goes into this entry: a real directory, not a link to
    one, and not skipped. Without a depth limit, following a link could leave
    the tree or go round a loop forever."""
    try:
        return entry.is_dir() and not entry.is_symlink() and not skipped(entry.name)
    except OSError:
        return False


def walk_files(root: Path, name: str):
    """Every file called `name` under `root`, by the same rule: no skipped
    folder entered, no link followed."""
    stack = [Path(root)]
    while stack:
        try:
            entries = list(stack.pop().iterdir())
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.name == name and entry.is_file():
                    yield entry
                elif descend(entry):
                    stack.append(entry)
            except OSError:
                continue
