import sqlite3
from pathlib import Path

from orglens import activity


def _index(tmp_path, rows):
    db_path = tmp_path / "index.sqlite"
    db = sqlite3.connect(db_path)
    db.execute(
        "create table sessions (id text primary key, kind text not null, "
        "agent text not null, machine text not null, cwd text, project text, "
        "title text, name text, started integer, ended integer, "
        "n_turns integer not null default 0, grade text not null default '', "
        "source text not null default '', needs text, outcome text)"
    )
    # _sessions joins these; absent, the join raises and the whole query is
    # swallowed by `_sessions`'s bare except, silently zeroing out a correct
    # count. Empty is enough — these tests don't exercise turns or notes.
    db.execute("create table turns (session_id text, ts text, role text, text text)")
    db.execute(
        "create table notes (session_id text, topic text, title text, ts text, "
        "tags text, entities text)"
    )
    for row in rows:
        db.execute(
            "insert into sessions (id, kind, agent, machine, cwd, project, n_turns) "
            "values (?, 'main', 'claude', 'test', ?, ?, 1)",
            row,
        )
    db.commit()
    db.close()
    return db_path


def test_sessions_from_two_homes_join_into_one_unit(tmp_path):
    code = tmp_path / "code" / "neuronal-degeneracy"
    docs = tmp_path / "docs" / "research" / "neuronal-degeneracy"
    code.mkdir(parents=True)
    docs.mkdir(parents=True)
    index = _index(tmp_path, [
        ("s1", str(code), "neuronal-degeneracy"),
        ("s2", str(docs), "traitful-docs"),      # filed under the repo today
        ("s3", str(docs / "specs"), "traitful-docs"),
    ])
    act = activity.read([code, docs], "neuronal-degeneracy", index=index)
    assert act.sessions == 3


def test_a_session_elsewhere_does_not_join(tmp_path):
    home = tmp_path / "code" / "orglens"
    other = tmp_path / "code" / "something-else"
    home.mkdir(parents=True)
    other.mkdir(parents=True)
    index = _index(tmp_path, [
        ("s1", str(home), "orglens"),
        ("s2", str(other), "something-else"),
    ])
    act = activity.read([home], "orglens", index=index)
    assert act.sessions == 1


def test_no_index_is_ordinary_not_an_error(tmp_path):
    home = tmp_path / "x"
    home.mkdir()
    act = activity.read([home], "x", index=tmp_path / "absent.sqlite")
    assert act.sessions == 0


def test_a_home_reached_through_a_symlink_still_matches(tmp_path):
    # ~/Dropbox is a symlink to ~/Library/CloudStorage/Dropbox and sessions
    # record the resolved form. A home in symlink form must still match, or a
    # unit silently reports zero sessions.
    real = tmp_path / "real" / "orglens"
    real.mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "real")
    index = _index(tmp_path, [("s1", str(real), "orglens")])
    act = activity.read([link / "orglens"], "orglens", index=index)
    assert act.sessions == 1


def test_a_container_session_matches_its_home_by_name(tmp_path):
    # scad mounts a repository named X at /workspace/X. 35 of orglens's own
    # 79 sessions are container-side and match no host path.
    home = tmp_path / "code" / "orglens"
    home.mkdir(parents=True)
    index = _index(tmp_path, [
        ("s1", str(home), "orglens"),
        ("s2", "/workspace/orglens", "orglens"),
        ("s3", "/workspace/something-else", "something-else"),
    ])
    act = activity.read([home], "orglens", index=index, home_names=["orglens"])
    assert act.sessions == 2
