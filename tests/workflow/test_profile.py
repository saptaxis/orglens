from __future__ import annotations

from pathlib import Path

import pytest

from orglens.workflow.profile import find_marker, load_profile

WORKFLOW = {"marker": "writing.yaml"}

MARKER = """
default: portfolio
profiles:
  portfolio: {voice: portfolio, length: 2500}
  research:  {voice: research, length: 1700, guide: writing-guide.md}
"""


def make(tmp_path: Path) -> Path:
    (tmp_path / "writing.yaml").write_text(MARKER)
    packet = tmp_path / "a-piece"
    packet.mkdir()
    return packet


def test_finds_the_marker_by_walking_up(tmp_path: Path):
    packet = make(tmp_path)
    assert find_marker(packet, "writing.yaml") == tmp_path / "writing.yaml"


def test_missing_marker_returns_none(tmp_path: Path):
    assert find_marker(tmp_path, "writing.yaml") is None


def test_loads_the_default_profile(tmp_path: Path):
    packet = make(tmp_path)
    name, config = load_profile(packet, WORKFLOW, {})
    assert name == "portfolio"
    assert config["length"] == 2500


def test_the_brief_may_override_the_profile(tmp_path: Path):
    packet = make(tmp_path)
    name, config = load_profile(packet, WORKFLOW, {"profile": "research"})
    assert name == "research"
    assert config["guide"] == "writing-guide.md"


def test_a_missing_marker_fails_loudly(tmp_path: Path):
    """I7: explicit path -> marker walk-up -> fail. Never guess."""
    with pytest.raises(FileNotFoundError, match="writing.yaml"):
        load_profile(tmp_path, WORKFLOW, {})


def test_an_unknown_profile_name_fails_loudly(tmp_path: Path):
    packet = make(tmp_path)
    with pytest.raises(KeyError, match="nonesuch"):
        load_profile(packet, WORKFLOW, {"profile": "nonesuch"})
