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


class TestLivenessJoinsByCwd:
    """A live session is joined to a unit by where its process is actually
    running, the same evidence `_sessions` uses — not by scad's `project`
    column, which is exactly the coincidence this branch exists to delete.
    """

    def _registry(self, tmp_path, sessions):
        registry = tmp_path / "sessions"
        registry.mkdir()
        for i, (session_id, cwd) in enumerate(sessions):
            (registry / f"proc-{i}.json").write_text(
                json.dumps({"pid": __import__("os").getpid(), "sessionId": session_id, "cwd": cwd})
            )
        return registry

    def test_a_live_session_in_the_units_home_is_seen(self, tmp_path, monkeypatch):
        home = tmp_path / "code" / "orglens"
        home.mkdir(parents=True)
        registry = self._registry(tmp_path, [("s1", str(home))])
        monkeypatch.setattr(activity, "LIVE_REGISTRY", registry)
        activity._live_entries.cache_clear()

        act = activity.read([home], "orglens", index=tmp_path / "absent.sqlite")

        assert act.live_sessions == 1

    def test_a_live_session_filed_under_a_different_project_by_scad_is_still_seen(
        self, tmp_path, monkeypatch
    ):
        """The reproduction: a live session running in a unit's docs home,
        which scad's index files under the docs repository's own project
        name (`traitful-docs`, say) rather than the unit's name. Joining on
        `project` misses it entirely; joining on cwd does not.
        """
        docs_home = tmp_path / "traitful-docs" / "docs" / "projects" / "widget"
        docs_home.mkdir(parents=True)
        index = tmp_path / "index.sqlite"
        import sqlite3

        db = sqlite3.connect(index)
        db.execute(
            "create table sessions (id text primary key, kind text not null, "
            "agent text not null, machine text not null, cwd text, project text, "
            "title text, name text, started integer, ended integer, "
            "n_turns integer not null default 0, grade text not null default '', "
            "source text not null default '', needs text, outcome text)"
        )
        db.execute(
            "insert into sessions (id, kind, agent, machine, cwd, project, n_turns) "
            "values ('s1', 'main', 'claude', 'test', ?, 'traitful-docs', 0)",
            (str(docs_home),),
        )
        db.commit()
        db.close()

        registry = self._registry(tmp_path, [("s1", str(docs_home))])
        monkeypatch.setattr(activity, "LIVE_REGISTRY", registry)
        activity._live_entries.cache_clear()

        act = activity.read([docs_home], "widget", index=index)

        assert act.live_sessions == 1

    def test_a_live_session_elsewhere_is_not_seen(self, tmp_path, monkeypatch):
        home = tmp_path / "code" / "orglens"
        other = tmp_path / "code" / "something-else"
        home.mkdir(parents=True)
        other.mkdir(parents=True)
        registry = self._registry(tmp_path, [("s1", str(other))])
        monkeypatch.setattr(activity, "LIVE_REGISTRY", registry)
        activity._live_entries.cache_clear()

        act = activity.read([home], "orglens", index=tmp_path / "absent.sqlite")

        assert act.live_sessions == 0

    def test_a_live_session_matches_a_container_cwd_by_home_name(
        self, tmp_path, monkeypatch
    ):
        home = tmp_path / "code" / "orglens"
        home.mkdir(parents=True)
        registry = self._registry(tmp_path, [("s1", "/workspace/orglens")])
        monkeypatch.setattr(activity, "LIVE_REGISTRY", registry)
        activity._live_entries.cache_clear()

        act = activity.read(
            [home], "orglens", index=tmp_path / "absent.sqlite", home_names=["orglens"]
        )

        assert act.live_sessions == 1
