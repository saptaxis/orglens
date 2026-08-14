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


def _rungs(name: str, candidates: list[Candidate]):
    """Walk the ladder, yielding `(how, [(candidate, path), ...])` for the
    first rung that has any existing match.

    Shared by `resolve_home`, which wants only the first pair, and
    `candidates_for`, which wants every pair at that same rung — the
    difference between "the answer" and "everyone who could have answered".
    """
    repo, _, subpath = name.partition("/")

    def spoken_for(c: Candidate) -> bool:
        # A directory carrying a marker has already answered what home it is.
        # A weaker rung must not overrule that with a coincidental basename
        # or remote match for a *different* name — otherwise a project's docs
        # checkout, sharing a leaf name with its code checkout, could shadow
        # the very home being looked up.
        return c.marker_home is not None and c.marker_home not in (name, repo)

    def joined(c: Candidate) -> Path:
        return c.path / subpath if subpath else c.path

    # A marker can claim a home two different ways, and they are not the
    # same shape: claiming the full name (subpath and all) means the
    # candidate's own directory *is* the answer, while claiming only the
    # repository segment means the subpath still has to be joined on. Merging
    # them into one boolean was the bug — a full-name match got the subpath
    # joined a second time, landing on a directory that never existed.
    for how, match, path_of in (
        ("marker", lambda c: c.marker_home == name, lambda c: c.path),
        ("marker", lambda c: c.marker_home == repo, joined),
        ("remote", lambda c: not spoken_for(c)
         and c.remote is not None and c.remote.split("/")[-1] == repo, joined),
        ("name", lambda c: not spoken_for(c) and c.name == repo, joined),
    ):
        existing = [
            (c, path_of(c)) for c in candidates if match(c) and path_of(c).exists()
        ]
        # A home declared before its folder was created, or a subpath since
        # moved, is filtered out here rather than at every call site — every
        # downstream consumer relies on a `Home` with a path existing.
        if existing:
            yield how, existing


def resolve_home(name: str, candidates: list[Candidate]) -> Home:
    """Locate a home by the ladder, saying which rung answered."""
    for how, existing in _rungs(name, candidates):
        _, path = existing[0]
        return Home(name=name, path=path, how=how)
    return Home(name=name, path=None, how="absent")


def candidates_for(name: str, candidates: list[Candidate]) -> list[Candidate]:
    """Every candidate that would satisfy this name at the rung that wins —
    not only the first, which is what `resolve_home` returns and what a
    caller standing on one machine sees.

    Two directories can tie at the same rung: two docs checkouts both named
    `alpha`, or two repositories whose remote both end in `owner/alpha`. The
    ladder still answers — it has to, resolution needs one path — but the
    tie is real and worth reporting, which is what `check` uses this for.
    """
    for _, existing in _rungs(name, candidates):
        return [c for c, _ in existing]
    return []
