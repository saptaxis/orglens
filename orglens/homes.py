"""A home is named, not located. This turns the name into a path here.

There is no single right mechanism, so it is a ladder and the rung that
answered is reported. A marker is the strongest and the only one that writes
a file into a repository you may share; a git remote is free and already
present but not canonical across setups — this machine's traitful-docs uses a
host alias; a directory name always works and is exactly the coincidence the
units model exists to delete, which is why it is last and why `check` says
when it was used.

A name that resolves to nothing is `absent`, not an error. Several homes in
this tree's dispatch configs are not cloned on every machine.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from orglens.declaration import MARKER, read_marker

#: Deep enough for a repository sitting a couple of levels inside a root,
#: shallow enough that a root holding fifty checkouts scans in milliseconds.
DEFAULT_DEPTH = 3


@dataclass(frozen=True)
class Candidate:
    path: Path
    name: str
    marker_home: str | None = None
    remote: str | None = None


@dataclass(frozen=True)
class Home:
    name: str
    path: Path | None
    how: str  # marker | remote | name | absent


def normalise_remote(url: str) -> str | None:
    """The owner/repo tail of a git remote, host and alias discarded."""
    if not url:
        return None
    trimmed = url.strip()
    if trimmed.endswith(".git"):
        trimmed = trimmed[: -len(".git")]
    # scp-style (git@host:owner/repo) and URL-style (scheme://host/owner/repo)
    tail = re.split(r"[:/]", trimmed)
    if len(tail) < 2:
        return None
    return "/".join(tail[-2:])


def _remote_of(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return normalise_remote(result.stdout)


def scan_roots(roots: list[Path], max_depth: int = DEFAULT_DEPTH) -> list[Candidate]:
    """Every directory under the roots that could be a home, with its evidence."""
    found: list[Candidate] = []
    seen: set[Path] = set()

    def walk(base: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            children = sorted(p for p in base.iterdir() if p.is_dir())
        except OSError:
            return
        for child in children:
            if child.name.startswith("."):
                continue
            if child in seen:
                continue
            seen.add(child)
            marker = read_marker(child)
            found.append(
                Candidate(
                    path=child,
                    name=child.name,
                    marker_home=marker.home if marker else None,
                    remote=_remote_of(child) if (child / ".git").exists() else None,
                )
            )
            walk(child, depth + 1)

    for root in roots:
        # Resolved, not merely expanded. `~/Dropbox` is a symlink to
        # `~/Library/CloudStorage/Dropbox` here, and 1,547 of 1,667 indexed
        # sessions record the resolved form. Walking the symlink form yields
        # candidate paths that match none of them — and match failure is
        # silent, because a lookup returns empty rather than raising.
        # Resolving once at the root means every path downstream is resolved.
        walk(Path(root).expanduser().resolve(), 1)
    return found


def resolve_home(name: str, candidates: list[Candidate]) -> Home:
    """Locate a home by the ladder, saying which rung answered."""
    repo, _, subpath = name.partition("/")

    for how, match in (
        ("marker", lambda c: c.marker_home == name or c.marker_home == repo),
        ("remote", lambda c: c.remote is not None and c.remote.split("/")[-1] == repo),
        ("name", lambda c: c.name == repo),
    ):
        for candidate in candidates:
            if match(candidate):
                path = candidate.path / subpath if subpath else candidate.path
                return Home(name=name, path=path, how=how)

    return Home(name=name, path=None, how="absent")
