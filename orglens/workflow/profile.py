"""The marker file — configuration and resolver root in one.

Finding the config and finding the workflow root are the same operation, which
is why the profile file doubles as the marker. Nothing read this before, so
voice, length, and evidence bar were written down and unreachable.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def find_marker(start: Path, marker: str) -> Path | None:
    """Walk up from `start` looking for `marker`. Never defaults to cwd."""
    current = Path(start).resolve()
    for candidate in (current, *current.parents):
        path = candidate / marker
        if path.is_file():
            return path
    return None


def load_profile(
    packet: Path, workflow: dict, brief_frontmatter: dict
) -> tuple[str, dict]:
    """Resolve the packet's profile. Fails loudly rather than guessing (I7)."""
    marker_name = workflow["marker"]
    marker = find_marker(Path(packet), marker_name)
    if marker is None:
        raise FileNotFoundError(
            f"no {marker_name} found walking up from {packet}; "
            "a workflow set must be configured before any packet under it resolves"
        )

    config = yaml.safe_load(marker.read_text()) or {}
    profiles = config.get("profiles", {})
    name = brief_frontmatter.get("profile") or config.get("default")

    if name not in profiles:
        raise KeyError(
            f"profile {name!r} is not declared in {marker}; "
            f"known profiles: {sorted(profiles)}"
        )

    return name, profiles[name]
