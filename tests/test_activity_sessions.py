import sqlite3
from pathlib import Path

from orglens import activity


def _schema(db):
    db.execute(
        "create table sessions (id text primary key, kind text not null, "
        "agent text not null, machine text not null, cwd text, project text, "
        "title text, name text, started integer, ended integer, "
        "n_turns integer not null default 0, grade text not null default '', "
        "source text not null default '', needs text, outcome text)"
    )
    # _sessions joins these; absent, the join raises and the whole query is
    # swallowed by `_sessions`'s bare except, silently zeroing out a correct
    # count. Empty is enough where a test doesn't exercise turns or notes.
    db.execute("create table turns (session_id text, ts text, role text, text text)")
    db.execute(
        "create table notes (session_id text, topic text, title text, ts text, "
        "tags text, entities text)"
    )


def _index(tmp_path, rows):
    db_path = tmp_path / "index.sqlite"
    db = sqlite3.connect(db_path)
    _schema(db)
    for row in rows:
        db.execute(
            "insert into sessions (id, kind, agent, machine, cwd, project, n_turns) "
            "values (?, 'main', 'claude', 'test', ?, ?, 1)",
            row,
        )
    db.commit()
    db.close()
    return db_path


def _session_row(db, id, cwd, project, kind="main", needs=None, title=None):
    db.execute(
        "insert into sessions (id, kind, agent, machine, cwd, project, title, "
        "n_turns, needs) values (?, ?, 'claude', 'test', ?, ?, ?, 0, ?)",
        (id, kind, cwd, project, title, needs),
    )


def _turn_row(db, session_id, ts, role, text):
    db.execute(
        "insert into turns (session_id, ts, role, text) values (?, ?, ?, ?)",
        (session_id, ts, role, text),
    )


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


# `_home_clause` joins per-home terms with `or`. Any query that appends its
# own `and ...` after that clause is vulnerable to SQL's precedence: `and`
# binds tighter than `or`, so `H1 or H2 and COND` parses as `H1 or (H2 and
# COND)` — a row matching the *first* home clause passes the whole `where`
# regardless of COND, while only rows matching later homes actually have to
# satisfy it. Two homes are enough to trigger this; it does not need three.


def test_a_null_turn_from_the_first_home_cannot_outrank_a_real_one(tmp_path):
    home_a = tmp_path / "code" / "unit-a"
    home_b = tmp_path / "code" / "unit-b"
    home_a.mkdir(parents=True)
    home_b.mkdir(parents=True)
    db_path = tmp_path / "index.sqlite"
    db = sqlite3.connect(db_path)
    _schema(db)
    _session_row(db, "s1", str(home_a), "unit-a")
    _session_row(db, "s2", str(home_b), "unit-b")
    # s1's only turn carries no text — the query's own condition means to
    # exclude it, no matter how it sorts.
    _turn_row(db, "s1", "2024-01-05T00:00:00", "assistant", None)
    # s2's turn is real but earlier. It must still win, because s1's does
    # not qualify at all.
    _turn_row(db, "s2", "2024-01-01T00:00:00", "user", "the actual content")
    db.commit()
    db.close()

    act = activity.read([home_a, home_b], "unit-a", index=db_path)
    assert act.last_turn == {
        "at": activity._epoch("2024-01-01T00:00:00"),
        "role": "user",
        "text": "the actual content",
    }


def test_a_session_with_no_open_question_cannot_pollute_needs(tmp_path):
    home_a = tmp_path / "code" / "unit-a"
    home_b = tmp_path / "code" / "unit-b"
    home_a.mkdir(parents=True)
    home_b.mkdir(parents=True)
    db_path = tmp_path / "index.sqlite"
    db = sqlite3.connect(db_path)
    _schema(db)
    # s1 (the first home) has no open question at all — `needs` is null.
    # It must never appear in the needs list.
    _session_row(db, "s1", str(home_a), "unit-a", needs=None)
    # s2 (the second home) has a real open question.
    _session_row(db, "s2", str(home_b), "unit-b", needs="what should X do?")
    db.commit()
    db.close()

    act = activity.read([home_a, home_b], "unit-a", index=db_path)
    assert act.needs == [{"question": "what should X do?", "at": None}]


def test_a_subagent_from_the_first_home_cannot_pollute_recent(tmp_path):
    home_a = tmp_path / "code" / "unit-a"
    home_b = tmp_path / "code" / "unit-b"
    home_a.mkdir(parents=True)
    home_b.mkdir(parents=True)
    db_path = tmp_path / "index.sqlite"
    db = sqlite3.connect(db_path)
    _schema(db)
    # s1 (the first home) is a subagent, not a main session — `recent`
    # deliberately wants only kind = 'main'.
    _session_row(db, "s1", str(home_a), "unit-a", kind="workflow-agent",
                 title="from-home-a-leaked")
    _session_row(db, "s2", str(home_b), "unit-b", kind="main",
                 title="from-home-b-real")
    db.commit()
    db.close()

    act = activity.read([home_a, home_b], "unit-a", index=db_path)
    assert act.recent == [
        {
            "at": None,
            "agent": "claude",
            "outcome": None,
            "name": "from-home-b-real",
            "turns": 0,
            "open": False,
        }
    ]
