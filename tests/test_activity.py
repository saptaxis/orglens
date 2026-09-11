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

    act = activity.read([docs, code], "unit", index=tmp_path / "absent.sqlite")

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

    act = activity.read([docs, code], "unit", index=tmp_path / "absent.sqlite")

    assert act.plan == "07"


def test_packets_are_summed_across_homes(tmp_path):
    """A workflow packet in the code home must not go uncounted because the
    docs home happened to be listed first and holds none.
    """
    docs = tmp_path / "docs"
    code = tmp_path / "code"
    (docs / "packet-a").mkdir(parents=True)
    (code / "packet-b").mkdir(parents=True)
    (docs / "packet-a" / "runs.jsonl").write_text("")
    (code / "packet-b" / "runs.jsonl").write_text("")

    act = activity.read([docs, code], "unit", index=tmp_path / "absent.sqlite")

    assert act.packets == 2


def test_blocked_packets_are_summed_across_homes(tmp_path):
    docs = tmp_path / "docs"
    code = tmp_path / "code"
    (docs / "packet-a").mkdir(parents=True)
    (code / "packet-b").mkdir(parents=True)
    (docs / "packet-a" / "runs.jsonl").write_text(
        json.dumps({"type": "needs_human", "event_id": "e1"}) + "\n"
    )
    (code / "packet-b" / "runs.jsonl").write_text(
        json.dumps({"type": "needs_human", "event_id": "e2"}) + "\n"
    )

    act = activity.read([docs, code], "unit", index=tmp_path / "absent.sqlite")

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

        act = activity.peek([home], "widget", index=tmp_path / "absent.sqlite")

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

        act = activity.peek([home], "widget", index=tmp_path / "absent.sqlite", sessions=[s1])

        assert act.sessions == 1
        assert act.last_session == 2

    def test_no_index_and_no_files_is_ordinary_not_an_error(self, tmp_path):
        home = tmp_path / "ghost"
        home.mkdir()

        act = activity.peek([home], "ghost", index=tmp_path / "absent.sqlite")

        assert act.sessions == 0
        assert act.last_session is None
