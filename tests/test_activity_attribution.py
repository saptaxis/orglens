import json
import os
import sqlite3
from pathlib import Path

from orglens import activity


def _index(tmp_path, rows):
    """A scad index with the tables `_sessions` actually queries.

    The auxiliary tables matter: a missing `turns` raises inside the query and
    the bare `except sqlite3.Error` returns zeros, so every assertion would
    pass or fail for the wrong reason.
    """
    db_path = tmp_path / "index.sqlite"
    db = sqlite3.connect(db_path)
    db.execute(
        "create table sessions (id text primary key, kind text not null, "
        "agent text not null, machine text not null, cwd text, project text, "
        "title text, name text, started integer, ended integer, "
        "n_turns integer not null default 0, grade text not null default '', "
        "source text not null default '', outcome text, needs text)"
    )
    db.execute("create table turns (session_id text, ts integer, role text, text text)")
    db.execute(
        "create table notes (session_id text, idx integer, ts integer, topic text, "
        "relation text, parent text, title text, tags text, entities text, "
        "note_path text, kind text, project text)"
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


def test_an_attributed_session_counts_even_from_outside_every_home(tmp_path):
    home = tmp_path / "docs" / "projects" / "orglens"
    elsewhere = tmp_path / "docs"          # the repo root, above every home
    home.mkdir(parents=True)
    index = _index(tmp_path, [("s1", str(elsewhere), "traitful-docs")])

    without = activity.read([home], "orglens", index=index)
    assert without.sessions == 0

    with_it = activity.read([home], "orglens", index=index,
                            attributed={"s1": "orglens"})
    assert with_it.sessions == 1


def test_an_attribution_to_another_unit_does_not_count(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    index = _index(tmp_path, [("s1", str(tmp_path / "elsewhere"), "x")])
    act = activity.read([home], "orglens", index=index,
                        attributed={"s1": "something-else"})
    assert act.sessions == 0


def test_containment_and_attribution_do_not_double_count(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    index = _index(tmp_path, [("s1", str(home), "orglens")])
    act = activity.read([home], "orglens", index=index,
                        attributed={"s1": "orglens"})
    assert act.sessions == 1


def test_no_attributions_behaves_exactly_as_before(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    index = _index(tmp_path, [("s1", str(home), "orglens")])
    assert activity.read([home], "orglens", index=index).sessions == 1
    assert activity.read([home], "orglens", index=index, attributed={}).sessions == 1


def test_peek_honours_attributed_the_same_way_read_does(tmp_path):
    """The brief's tests only exercise `read`. My ruling requires `peek` (what
    `orglens list` uses) to reach the same count as `read` for an explicitly
    attributed session outside every home — otherwise `list` and `status`
    would disagree about the same unit."""
    home = tmp_path / "docs" / "projects" / "orglens"
    elsewhere = tmp_path / "docs"
    home.mkdir(parents=True)
    index = _index(tmp_path, [("s1", str(elsewhere), "traitful-docs")])

    without = activity.peek([home], "orglens", index=index)
    assert without.sessions == 0

    with_it = activity.peek([home], "orglens", index=index,
                            attributed={"s1": "orglens"})
    assert with_it.sessions == 1


def _live(tmp_path, session, cwd):
    """A live-registry directory holding one running-session record, in the
    shape `_live_entries` reads: pid, sessionId, cwd, kind."""
    live = tmp_path / "live"
    live.mkdir()
    (live / f"{session}.json").write_text(json.dumps(
        {"pid": os.getpid(), "sessionId": session, "cwd": str(cwd), "kind": "main"}))
    return live


def test_an_attributed_live_session_shows_even_from_outside_every_home(
    tmp_path, monkeypatch
):
    """`_live_for`'s attribution branch: a running session, explicitly
    attributed, must appear in the unit's `live` list even when its cwd is
    above every home — not just counted in `sessions` (covered above)."""
    home = tmp_path / "docs" / "projects" / "orglens"
    home.mkdir(parents=True)
    monkeypatch.setattr(activity, "LIVE_REGISTRY",
                        _live(tmp_path, "s1", tmp_path / "docs"))
    index = tmp_path / "nope.sqlite"
    assert activity.read([home], "orglens", index=index).live == []
    got = activity.read([home], "orglens", index=index,
                        attributed={"s1": "orglens"}).live
    assert [e["session"] for e in got] == ["s1"]
