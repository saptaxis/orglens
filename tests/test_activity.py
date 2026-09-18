"""Facts that must be derived from every home, not only the first one."""

import json
from pathlib import Path

from orglens import activity


def test_touched_is_the_newest_commit_across_homes(tmp_path):
    """A unit whose docs home is listed first used to report the docs
    home's commit date and nothing later, however recently the code home
    had actually been touched.
    """
    docs = tmp_path / "docs"
    code = tmp_path / "code"
    docs.mkdir()
    code.mkdir()

    def _commit(path, when):
        import subprocess

        subprocess.run(["git", "init", "-q"], cwd=path, check=True)
        subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=path, check=True)
        subprocess.run(["git", "config", "user.name", "a"], cwd=path, check=True)
        (path / "f.txt").write_text("x")
        subprocess.run(["git", "add", "-A"], cwd=path, check=True)
        env = {
            "GIT_AUTHOR_DATE": when,
            "GIT_COMMITTER_DATE": when,
            "PATH": __import__("os").environ["PATH"],
        }
        subprocess.run(
            ["git", "commit", "-q", "-m", "x"], cwd=path, check=True, env=env
        )

    _commit(docs, "2020-01-01T00:00:00")
    _commit(code, "2024-06-01T00:00:00")

    act = activity.read([docs, code], "unit")

    newer = int(
        __import__("datetime")
        .datetime.fromisoformat("2024-06-01T00:00:00")
        .timestamp()
    )
    assert act.touched == newer


def test_plan_is_the_highest_numbered_plan_across_homes(tmp_path):
    """A docs home holding plan 03 must not shadow a code home holding
    plan 07 just because it sorts first in `unit.paths`.
    """
    docs = tmp_path / "docs"
    code = tmp_path / "code"
    (docs / "plans").mkdir(parents=True)
    (code / "plans").mkdir(parents=True)
    (docs / "plans" / "03-thing-Feb032026.md").write_text("# 03\n")
    (code / "plans" / "07-thing-Feb072026.md").write_text("# 07\n")

    act = activity.read([docs, code], "unit")

    assert act.plan == "07"


def _chain_packet(directory, gate: bool):
    """A workflow packet: a session log, with an unanswered question if `gate`."""
    from orglens.workflow import session
    directory.mkdir(parents=True)
    session.bind(directory, directory / "WORKFLOW.yaml")
    fact = {"type": "done", "node": "one", "agent": "claude"}
    if gate:
        fact["question"] = "which way?"
    session.append(directory, fact)


def test_packets_are_summed_across_homes(tmp_path):
    docs = tmp_path / "docs"
    code = tmp_path / "code"
    _chain_packet(docs / "packet-a", gate=False)
    _chain_packet(code / "packet-b", gate=False)
    # The old engine's log is not a packet any more.
    (code / "old").mkdir()
    (code / "old" / "runs.jsonl").write_text("")

    act = activity.read([docs, code], "unit")

    assert act.packets == 2


def test_blocked_packets_are_the_ones_with_an_open_gate(tmp_path):
    docs = tmp_path / "docs"
    code = tmp_path / "code"
    _chain_packet(docs / "packet-a", gate=True)
    _chain_packet(code / "packet-b", gate=True)
    _chain_packet(code / "packet-c", gate=False)

    act = activity.read([docs, code], "unit")

    assert act.packets == 3
    assert act.blocked == 2


class TestPeek:
    """`peek` is `list`'s cheap alternative to `read` — enough to sort and
    date a unit without the per-home git subprocess calls `read` makes for
    the last commit and the dirty count.
    """

    def test_it_reports_the_newest_file_mtime_without_touching_git(self, tmp_path):
        home = tmp_path / "docs" / "widget"
        home.mkdir(parents=True)
        (home / "f.txt").write_text("x")

        act = activity.peek([home], "widget")

        assert act.modified is not None
        # Never ran a git subprocess, so there is nothing to report here —
        # `status`'s facts, not `list`'s, are what would need it.
        assert act.touched is None
        assert act.dirty == 0

    def test_it_reports_the_last_session_time(self, tmp_path):
        from orglens.sessions import Session

        home = tmp_path / "code" / "widget"
        home.mkdir(parents=True)
        s1 = Session(id="s1", agent="claude", cwd=str(home), started=1000, ended=2000,
                     turns=1, label=None, outcome=None, live=False,
                     units=frozenset({"widget"}), how="containment")

        act = activity.peek([home], "widget", sessions=[s1])

        assert act.sessions == 1
        assert act.last_session == 2

    def test_no_scad_and_no_files_is_ordinary_not_an_error(self, tmp_path):
        home = tmp_path / "ghost"
        home.mkdir()

        act = activity.peek([home], "ghost")

        assert act.sessions == 0
        assert act.last_session is None


class TestGitCostsOncePerRepo:
    """`status` used to run three git subprocesses per home. The root is
    found by walking up to `.git`, and `git status` runs once per repository
    however many homes it holds."""

    def test_repo_root_is_found_without_running_git(self, tmp_path, monkeypatch):
        import subprocess as sp
        repo = tmp_path / "repo"
        deep = repo / "docs" / "projects" / "x"
        deep.mkdir(parents=True)
        (repo / ".git").mkdir()
        monkeypatch.setattr(sp, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("git was run")))

        assert activity._repo_root(deep) == repo
        assert activity._repo_root(tmp_path / "nowhere") is None

    def test_a_worktree_git_file_counts_as_a_root(self, tmp_path):
        repo = tmp_path / "wt"
        (repo / "sub").mkdir(parents=True)
        (repo / ".git").write_text("gitdir: /elsewhere/.git/worktrees/wt\n")
        assert activity._repo_root(repo / "sub") == repo

    def test_dirty_runs_git_status_once_per_repo(self, tmp_path, monkeypatch):
        import subprocess as sp
        repo = tmp_path / "repo"
        a, b = repo / "a", repo / "b"
        a.mkdir(parents=True); b.mkdir()
        sp.run(["git", "init", "-q"], cwd=repo, check=True)
        (a / "one.txt").write_text("x"); (a / "two.txt").write_text("y")
        (b / "three.txt").write_text("z")

        calls = []
        real = activity._git
        def spy(args, cwd):
            calls.append(args[0]); return real(args, cwd)
        monkeypatch.setattr(activity, "_git", spy)
        activity._status_lines.cache_clear()

        assert activity._dirty(repo, a) == 2
        assert activity._dirty(repo, b) == 1
        assert calls.count("status") == 1
