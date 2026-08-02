from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from orglens.workflow.effects import VerificationUnavailable, check_delta, revert


def git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "writing-brief.md").write_text("# Brief\n")
    (tmp_path / "draft.md").write_text("v1\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)
    return tmp_path


NODE = {"writes": ["draft.md"], "must_not_modify": ["writing-brief.md"]}


def test_clean_when_only_declared_writes_changed(tmp_path: Path):
    repo = git_repo(tmp_path)
    (repo / "draft.md").write_text("v2\n")
    assert check_delta(repo, NODE) == []


def test_reports_a_protected_file(tmp_path: Path):
    repo = git_repo(tmp_path)
    (repo / "draft.md").write_text("v2\n")
    (repo / "writing-brief.md").write_text("# Brief, widened\n")
    assert check_delta(repo, NODE) == ["writing-brief.md"]


def test_glob_patterns_are_honoured(tmp_path: Path):
    repo = git_repo(tmp_path)
    (repo / "decisions-01.md").write_text("## Accept\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "round"], cwd=repo, check=True)
    (repo / "decisions-01.md").write_text("## Accept\n- tampered\n")
    node = {"writes": ["draft.md"], "must_not_modify": ["decisions-*.md"]}
    assert check_delta(repo, node) == ["decisions-01.md"]


def test_double_star_means_everything_except_declared_writes(tmp_path: Path):
    repo = git_repo(tmp_path)
    (repo / "draft.md").write_text("tampered\n")
    node = {"writes": ["decisions-01.md"], "must_not_modify": ["**"]}
    assert check_delta(repo, node) == ["draft.md"]


def test_new_files_are_not_modifications(tmp_path: Path):
    repo = git_repo(tmp_path)
    (repo / "decisions-01.md").write_text("## Proposed\n")
    node = {"writes": ["decisions-01.md"], "must_not_modify": ["**"]}
    assert check_delta(repo, node) == []


def test_outside_a_repo_verification_is_unavailable_not_clean(tmp_path: Path):
    """`git diff` fails with no repository to diff against. Returning `[]`
    there would report every packet outside a repo as clean forever — a
    pass overwriting a protected file would be recorded as a clean
    completion. This must be distinguishable from a real "nothing changed"."""
    (tmp_path / "writing-brief.md").write_text("# Brief\n")
    (tmp_path / "draft.md").write_text("v2\n")
    with pytest.raises(VerificationUnavailable):
        check_delta(tmp_path, NODE)


def test_revert_restores_a_protected_file(tmp_path: Path):
    repo = git_repo(tmp_path)
    (repo / "writing-brief.md").write_text("# Brief, widened\n")
    revert(repo, ["writing-brief.md"])
    assert (repo / "writing-brief.md").read_text() == "# Brief\n"
