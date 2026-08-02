"""Checking what a pass actually changed against what it declared.

Detection, not prevention. An in-place edit is already made by the time this
runs — rejecting it would need staging or a worktree, which is the isolation
machinery the substrate declines. The docs tree is a git repo, so a violation
is detected against HEAD and reverted with `git checkout --`.

This exists for the one thing an agent interpreter does that a deterministic
one never would: help. A reviser that widens a frozen brief while applying a
ratified cut is exactly the failure the gate model prevents, and no amount of
prose in a role file reliably stops it.
"""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path


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
        return []
    return [
        Path(line).name
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def _matches_any(name: str, patterns: list[str]) -> bool:
    return any(
        pattern == "**" or fnmatch.fnmatch(name, pattern) for pattern in patterns
    )


def check_delta(packet: Path, node: dict) -> list[str]:
    """Files modified in violation of the node's `must_not_modify`.

    `must_not_modify: ["**"]` means *everything except this node's declared
    writes* — a diagnostic node still creates what it declares.
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
