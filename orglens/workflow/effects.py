"""Checking what a pass actually changed against what it declared.

Detection, not prevention. An in-place edit is already made by the time this
runs — rejecting it would need staging or a worktree, which is the isolation
machinery the substrate declines. The docs tree is a git repo, so a violation
is detected against HEAD and reverted with `git checkout --`.

This exists for the one thing an agent interpreter does that a deterministic
one never would: help. A reviser that widens a frozen brief while applying a
ratified cut is exactly the failure the gate model prevents, and no amount of
prose in a role file reliably stops it.

Bound: `git diff --name-only HEAD` reports changes to tracked files only. A
pass that creates a brand-new file inside a packet declaring everything
protected leaves no trace here — the file is untracked, not modified, and no
diff line names it.
"""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path


class VerificationUnavailable(RuntimeError):
    """Raised when whether anything protected changed cannot be determined —
    for example, the packet is not inside a git repository. A caller must
    not treat this the same as "checked, and nothing changed."
    """


def _modified_tracked_files(packet: Path) -> list[str]:
    """Tracked files changed since HEAD, relative to the packet."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", "."],
        cwd=packet,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise VerificationUnavailable(
            f"git diff could not run against {packet} (exit {result.returncode}): "
            f"{result.stderr.strip()}; whether anything protected changed is unknown"
        )
    return [
        Path(line).name
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def _matches_any(name: str, patterns: list[str]) -> bool:
    return any(
        pattern == "**" or fnmatch.fnmatch(name, pattern) for pattern in patterns
    )


def dirty_files(packet: Path) -> frozenset[str]:
    """Names of tracked files already modified relative to HEAD, at the
    moment this is called.

    A baseline the caller takes *before* dispatching a pass, so a violation
    found afterward can be judged against what changed because of the pass,
    not against everything that was already dirty when it started. Without
    this, a pre-existing uncommitted edit inside the packet is indistinguishable
    from one the pass just made, and gets attributed — and reverted — as if
    the pass had caused it.
    """
    return frozenset(_modified_tracked_files(Path(packet)))


def file_hash(packet: Path, name: str) -> str | None:
    """The content hash of ``packet / name`` right now, or ``None`` if the
    file does not exist.

    Computed with ``git hash-object`` rather than opening the file from
    Python, matching how every other check in this module goes through git
    instead of reading a document body directly. Two calls at two different
    times that return the same hash mean the file did not change between
    them, even though both may differ from ``HEAD``.
    """
    path = Path(packet) / name
    if not path.exists():
        return None
    result = subprocess.run(
        ["git", "hash-object", "--", name],
        cwd=packet,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise VerificationUnavailable(
            f"git hash-object could not run against {path} (exit {result.returncode}): "
            f"{result.stderr.strip()}; whether anything protected changed is unknown"
        )
    return result.stdout.strip()


def check_delta(packet: Path, node: dict) -> list[str]:
    """Files modified in violation of the node's `must_not_modify`.

    `must_not_modify: ["**"]` means *everything except this node's declared
    writes* — a diagnostic node still creates what it declares.

    Raises `VerificationUnavailable` if it cannot be determined whether
    anything protected changed (for instance, `packet` is not inside a git
    repository). An empty list means checked and clean, never "could not
    check" — those are not the same outcome and a caller must not confuse
    them.
    """
    protected = node.get("must_not_modify") or []
    if not protected:
        return []

    declared_writes = node.get("writes") or []
    violations = [
        name
        for name in _modified_tracked_files(Path(packet))
        if _matches_any(name, protected) and not _matches_any(name, declared_writes)
    ]
    return sorted(set(violations))


def revert(packet: Path, paths: list[str]) -> None:
    """Restore paths to their HEAD state."""
    if not paths:
        return
    subprocess.run(
        ["git", "checkout", "HEAD", "--", *paths],
        cwd=packet,
        capture_output=True,
        check=False,
    )
