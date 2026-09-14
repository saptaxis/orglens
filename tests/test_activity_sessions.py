"""What `activity.read` derives from the sessions it is handed.

Which sessions a unit has is decided in `sessions.py` and tested there.
`read` takes that list and answers the rest: counts, the last thing said,
open questions, the recent few, what is running, and the notes about the
unit. Nothing here matches a cwd; a session is the unit's because it was
passed in.
"""

from orglens import activity
from orglens.sessions import Session
from tests.conftest import fake_scad


def _s(id, *, agent="claude", turns=1, started=None, ended=None, label=None,
       outcome=None, live=False, cwd="/x", units=("u",), how="containment",
       last_turn=None, needs=None):
    return Session(id=id, agent=agent, cwd=cwd, started=started, ended=ended,
                   turns=turns, label=label, outcome=outcome, live=live,
                   units=frozenset(units), how=how, last_turn=last_turn, needs=needs)


def test_the_count_is_the_sessions_given(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    act = activity.read([home], "u", sessions=[_s("a"), _s("b"), _s("c")])
    assert act.sessions == 3


def test_no_sessions_given_means_none(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    assert activity.read([home], "u").sessions == 0


def test_turns_agents_and_last_time_come_from_the_list(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    act = activity.read([home], "u", sessions=[
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
    act = activity.read([home], "u", sessions=given)
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
    act = activity.read([home], "u", sessions=[
        _s("a", live=True, label="working", cwd="/here"),
        _s("b", live=False),
    ])
    assert act.live == [{"session": "a", "name": "working", "cwd": "/here"}]
    assert act.live_sessions == 1


def test_last_turn_is_the_newest_across_the_sessions(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    act = activity.read([home], "u", sessions=[
        _s("a", last_turn={"ts": "2024-01-05T00:00:00", "role": "assistant", "text": "later"}),
        _s("b", last_turn={"ts": "2024-01-01T00:00:00", "role": "user", "text": "earlier"}),
        _s("c", last_turn=None),
    ])
    assert act.last_turn == {
        "at": activity._epoch("2024-01-05T00:00:00"), "role": "assistant", "text": "later",
    }


def test_needs_are_the_sessions_open_questions_newest_first(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    act = activity.read([home], "u", sessions=[
        _s("a", needs=None, ended=3000_000),
        _s("b", needs="what should X do?", ended=2000_000),
        _s("c", needs="and Y?", ended=1000_000),
    ])
    assert act.needs == [
        {"question": "what should X do?", "at": 2000},
        {"question": "and Y?", "at": 1000},
    ]


def test_notes_come_from_scad_notes_about_the_unit(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr("orglens.sessions.run_scad", fake_scad(notes=[
        {"topic": "u", "title": "a note in u", "ts": "2024-02-01T00:00:00", "tags": ["x"], "project": "u"},
        {"topic": "other", "title": "written elsewhere", "ts": "2024-01-01T00:00:00", "tags": ["u"], "project": "elsewhere"},
    ]))
    act = activity.read([home], "u")
    assert [n["title"] for n in act.notes] == ["a note in u", "written elsewhere"]
    assert act.notes[1]["written_in"] == "elsewhere" and act.notes[1]["about"] is True
    assert act.notes[0]["at"] == activity._epoch("2024-02-01T00:00:00")


def test_peek_reaches_the_same_count_and_time_as_read(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    given = [_s("a", ended=2000_000), _s("b", live=True)]
    read = activity.read([home], "u", sessions=given)
    peek = activity.peek([home], "u", sessions=given)
    assert (peek.sessions, peek.last_session, peek.live_sessions) == (
        read.sessions, read.last_session, read.live_sessions)
