"""What `activity.read` derives from the sessions it is handed.

Which sessions a unit has is decided in `sessions.py` and tested there.
`read` takes that list and answers the rest: counts, the last thing said,
open questions, the recent few, what is running. Nothing here matches a
cwd; a session is the unit's because it was passed in.
"""

import sqlite3
from pathlib import Path

from orglens import activity
from orglens.sessions import Session


def _schema(db):
    db.execute(
        "create table sessions (id text primary key, kind text not null, "
        "agent text not null, machine text not null, cwd text, project text, "
        "title text, name text, started integer, ended integer, "
        "n_turns integer not null default 0, grade text not null default '', "
        "source text not null default '', needs text, outcome text)"
    )
    db.execute("create table turns (session_id text, ts text, role text, text text)")
    db.execute(
        "create table notes (session_id text, topic text, title text, ts text, "
        "tags text, entities text)"
    )


def _index(tmp_path, rows: list[dict]) -> Path:
    db_path = tmp_path / "index.sqlite"
    db = sqlite3.connect(db_path)
    _schema(db)
    for row in rows:
        turns = row.pop("turns", [])
        base = {"kind": "main", "agent": "claude", "machine": "test", "n_turns": 1}
        base.update(row)
        cols = ", ".join(base)
        db.execute(f"insert into sessions ({cols}) values ({', '.join('?' * len(base))})",
                   tuple(base.values()))
        for ts, role, text in turns:
            db.execute("insert into turns (session_id, ts, role, text) values (?, ?, ?, ?)",
                       (base["id"], ts, role, text))
    db.commit()
    db.close()
    return db_path


def _s(id, *, agent="claude", turns=1, started=None, ended=None, label=None,
       outcome=None, live=False, cwd="/x", units=("u",), how="containment"):
    return Session(id=id, agent=agent, cwd=cwd, started=started, ended=ended,
                   turns=turns, label=label, outcome=outcome, live=live,
                   units=frozenset(units), how=how)


def test_the_count_is_the_sessions_given(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    act = activity.read([home], "u", index=tmp_path / "absent.sqlite",
                        sessions=[_s("a"), _s("b"), _s("c")])
    assert act.sessions == 3


def test_no_sessions_given_means_none(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    assert activity.read([home], "u", index=tmp_path / "absent.sqlite").sessions == 0


def test_turns_agents_and_last_time_come_from_the_list(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    act = activity.read([home], "u", index=tmp_path / "absent.sqlite", sessions=[
        _s("a", agent="codex", turns=5, ended=2000_000),
        _s("b", agent="claude", turns=7, started=9000_000),
    ])
    assert act.turns == 12
    assert act.agents == ["claude", "codex"]
    assert act.last_session == 9000       # scad stores milliseconds


def test_recent_is_the_newest_eight_with_open_marked(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    given = [_s(f"s{i}", ended=i * 1000, label=f"n{i}",
                outcome="awaiting-user" if i == 3 else "done") for i in range(10)]
    act = activity.read([home], "u", index=tmp_path / "absent.sqlite", sessions=given)
    assert [r["name"] for r in act.recent] == [f"n{i}" for i in range(9, 1, -1)]
    assert [r["open"] for r in act.recent] == [False] * 6 + [True, False]
    assert act.recent[0] == {
        "id": "s9", "at": 9, "agent": "claude", "outcome": "done", "name": "n9",
        "turns": 1, "open": False, "how": "containment",
    }
    assert act.open_sessions == 1


def test_live_is_the_running_ones_from_the_list(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    act = activity.read([home], "u", index=tmp_path / "absent.sqlite", sessions=[
        _s("a", live=True, label="working", cwd="/here"),
        _s("b", live=False),
    ])
    assert act.live == [{"session": "a", "name": "working", "cwd": "/here"}]
    assert act.live_sessions == 1


def test_last_turn_is_looked_up_by_the_ids_given(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    index = _index(tmp_path, [
        {"id": "mine", "turns": [("2024-01-01T00:00:00", "user", "the actual content")]},
        {"id": "other", "turns": [("2024-06-01T00:00:00", "user", "someone else's")]},
    ])
    act = activity.read([home], "u", index=index, sessions=[_s("mine")])
    assert act.last_turn == {
        "at": activity._epoch("2024-01-01T00:00:00"), "role": "user",
        "text": "the actual content",
    }


def test_a_turn_with_no_text_cannot_outrank_a_real_one(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    index = _index(tmp_path, [
        {"id": "a", "turns": [("2024-01-05T00:00:00", "assistant", None)]},
        {"id": "b", "turns": [("2024-01-01T00:00:00", "user", "the actual content")]},
    ])
    act = activity.read([home], "u", index=index, sessions=[_s("a"), _s("b")])
    assert act.last_turn["text"] == "the actual content"


def test_needs_are_looked_up_by_the_ids_given(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    index = _index(tmp_path, [
        {"id": "a", "needs": None},
        {"id": "b", "needs": "what should X do?"},
        {"id": "c", "needs": "not this unit's"},
    ])
    act = activity.read([home], "u", index=index, sessions=[_s("a"), _s("b")])
    assert act.needs == [{"question": "what should X do?", "at": None}]


def test_peek_reaches_the_same_count_and_time_as_read(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    given = [_s("a", ended=2000_000), _s("b", live=True)]
    read = activity.read([home], "u", index=tmp_path / "absent.sqlite", sessions=given)
    peek = activity.peek([home], "u", index=tmp_path / "absent.sqlite", sessions=given)
    assert (peek.sessions, peek.last_session, peek.live_sessions) == (
        read.sessions, read.last_session, read.live_sessions)
