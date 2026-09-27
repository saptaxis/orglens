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
    assert act.live == [{"session": "a", "name": "working", "cwd": "/here", "spoke": None}]
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


def _note(session_id, *, topic="t", title="a note", project=None,
          tags=(), entities=(), ts="2024-02-01T00:00:00"):
    return {"session_id": session_id, "topic": topic, "title": title,
            "project": project, "tags": list(tags), "entities": list(entities),
            "ts": ts}


def test_a_note_reaches_the_unit_its_session_belongs_to_untagged():
    """The join the name match could not make. Nothing in this note names
    `u` — not the topic, not the tags, not the project it was filed under.
    It is the unit's because the session that wrote it is."""
    notes = [_note("s1", topic="something-else", project="some-directory")]
    out = activity.notes_by_unit(["u"], [_s("s1", units=("u",))], notes)
    assert [n["how"] for n in out["u"]] == [activity.WRITTEN]
    assert out["u"][0]["written_in"] == "some-directory"


def test_a_note_that_only_mentions_the_unit_is_marked_weaker():
    notes = [_note("s9", topic="other", project="elsewhere", tags=["u"])]
    out = activity.notes_by_unit(["u"], [_s("s1", units=("u",))], notes)
    assert [n["how"] for n in out["u"]] == [activity.MENTIONS]


def test_entities_count_as_a_mention_as_scad_about_counts_them():
    notes = [_note("s9", topic="other", project="elsewhere", entities=["u"])]
    out = activity.notes_by_unit(["u"], [], notes)
    assert [n["how"] for n in out["u"]] == [activity.MENTIONS]


def test_the_project_it_was_filed_under_is_its_own_reason():
    notes = [_note("s9", topic="other", project="u")]
    out = activity.notes_by_unit(["u"], [], notes)
    assert [n["how"] for n in out["u"]] == [activity.FILED]


def test_written_here_wins_over_the_weaker_reasons():
    """One note, one unit, several reasons — the exact one is reported."""
    notes = [_note("s1", topic="u", project="u", tags=["u"])]
    out = activity.notes_by_unit(["u"], [_s("s1", units=("u",))], notes)
    assert [n["how"] for n in out["u"]] == [activity.WRITTEN]


def test_one_note_reaches_every_unit_that_has_a_claim_on_it():
    notes = [_note("s1", topic="v", project="w", tags=["x"])]
    out = activity.notes_by_unit(["u", "v", "w", "x", "z"],
                                 [_s("s1", units=("u",))], notes)
    assert {k: [n["how"] for n in v] for k, v in out.items()} == {
        "u": [activity.WRITTEN], "v": [activity.MENTIONS],
        "w": [activity.FILED], "x": [activity.MENTIONS], "z": [],
    }


def test_the_export_is_read_once_for_the_whole_tree(monkeypatch):
    """The reason this replaced `--about` per unit: a 31-unit tree paid 31
    subprocess launches to read the same file."""
    calls = []

    def counting(argv):
        calls.append(argv)
        return [_note("s1", project="u")]

    monkeypatch.setattr("orglens.sessions.run_scad", counting)
    activity.notes_by_unit([f"unit-{i}" for i in range(31)], [])
    assert len(calls) == 1 and calls[0][:2] == ["notes", "ls"]


def test_read_passes_its_sessions_to_the_join(tmp_path, monkeypatch):
    """`read` has the unit's sessions in hand, so its notes get the exact
    join too — not only the tree-wide callers."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr("orglens.sessions.run_scad",
                        fake_scad(notes=[_note("s1", topic="x", project="y")]))
    act = activity.read([home], "u", sessions=[_s("s1", units=("u",))])
    assert [n["how"] for n in act.notes] == [activity.WRITTEN]
