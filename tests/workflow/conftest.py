"""Shared fixture: a committed packet in a real git repo.

effects.check_delta diffs against HEAD, so a packet outside a repo reports no
violations and every verification test would pass vacuously.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ORCHESTRATOR_WORKFLOW = {
    "marker": "writing.yaml",
    "brief": "*-brief.md",
    "artifact": {"family": "draft", "canonical": "draft.md"},
    "terminal": {"published": "brief_published"},
    "nodes": {
        "critique": {
            "role": "critic.md",
            "reads": ["@brief", "@artifact"],
            "writes": ["findings.md"],
            "must_not_modify": ["**"],
            "diagnoses": True,
            "human_review": True,
            "expect": "revise",
            "guard": {
                "all": ["brief_exists", "artifact_exists"],
                "none": [
                    "artifact_noncanonical",
                    "awaiting_mutation",
                    "last_diagnostic_is_critique",
                ],
            },
        },
        "revise": {
            "role": "liner.md",
            "reads": ["@artifact"],
            "writes": ["draft.md"],
            "must_not_modify": ["writing-brief.md"],
            "mutates": True,
            "expect": "audit",
            "guard": {"all": ["awaiting_mutation"], "none": ["artifact_noncanonical"]},
        },
        "audit": {
            "role": "smell.md",
            "reads": ["@artifact"],
            "writes": ["findings.md"],
            "must_not_modify": ["**"],
            "diagnoses": True,
            "expect": "revise",
            "guard": {
                "all": ["brief_exists", "artifact_exists", "last_diagnostic_is_critique"],
                "none": ["artifact_noncanonical", "awaiting_mutation"],
            },
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

    (tmp_path / "writing.yaml").write_text(
        "default: portfolio\nprofiles:\n  portfolio: {}\n"
    )
    packet = tmp_path / "a-piece"
    packet.mkdir()
    (packet / "writing-brief.md").write_text("# Brief")
    (packet / "draft.md").write_text("original prose\n")

    deck = tmp_path / "deck"
    deck.mkdir()
    for card in ("critic.md", "liner.md", "smell.md"):
        (deck / card).write_text(f"# {card}")

    workflow_path = tmp_path / "WORKFLOW.yaml"
    workflow_path.write_text("workflow: t\n")  # hashed for version only

    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "packet")
    return packet, deck, workflow_path
