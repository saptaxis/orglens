"""Shared fixture: a packet committed in a real git repo.

The engine itself no longer consults git at all — verification is gone, so
nothing here needs a "before" state to judge a pass against. The fixture
stays git-backed anyway because that is the real operating model this plan
targets: a pass that overreaches is a diff to look at, not something this
fixture has to simulate.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

# `after:`-chained guards throughout, no `mutates`/`diagnoses`/`expect`/
# `must_not_modify`/`marker` — those concepts do not exist anymore.
#
# `critique` is reachable straight from an empty run log (the fixture packet
# starts with its brief and draft already in place, as if the packet were
# handed over mid-flight). `revise` follows either a `critique` or an
# `audit`, and `audit` follows a `revise` — a real loop. `brief` is declared
# but not reachable through any guard here; it exists only as a target a
# human can move the cursor to by hand.
#
# `critique`'s second read glob matches nothing in the fixture packet on
# purpose, so a glob report has something to report as unmatched.
ORCHESTRATOR_WORKFLOW = {
    "terminal": {"done": "exists:PUBLISHED"},
    "nodes": {
        "critique": {
            "role": "critic.md",
            "reads": ["writing-brief.md", "notes-*.md"],
            "writes": ["findings.md"],
            "human_review": True,
            "guard": {"all": ["after:nothing"]},
        },
        "revise": {
            "role": "liner.md",
            "reads": ["draft.md"],
            "writes": ["draft.md"],
            "guard": {"any": ["after:critique", "after:audit"]},
        },
        "audit": {
            "role": "smell.md",
            "reads": ["draft.md"],
            "writes": ["findings.md"],
            "guard": {"all": ["after:revise"]},
        },
        "brief": {
            "role": "self",
            "reads": [],
            "writes": ["writing-brief.md"],
            "guard": {"all": ["after:brief"]},
        },
    },
}


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo_packet(tmp_path: Path):
    """(packet, deck, workflow_path) — committed, so HEAD is a real baseline."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")

    packet = tmp_path / "a-piece"
    packet.mkdir()
    (packet / "writing-brief.md").write_text("# Brief")
    (packet / "draft.md").write_text("original prose\n")

    deck = tmp_path / "deck"
    deck.mkdir()
    for card in ("critic.md", "liner.md", "smell.md"):
        (deck / card).write_text(f"# {card}")

    workflow_path = tmp_path / "WORKFLOW.yaml"
    workflow_path.write_text(yaml.safe_dump(ORCHESTRATOR_WORKFLOW))

    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "packet")
    return packet, deck, workflow_path
