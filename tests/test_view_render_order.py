"""`_recency` moved to `activity.py` as `recency` — this locks in that
`view.render` still sorts rows by it exactly as before the move."""

from __future__ import annotations

from pathlib import Path

from orglens.activity import Activity
from orglens.view import render

CTX = {"docs_roots": [Path("/docs")], "base_url": "http://localhost"}


def _row(name: str, activity: Activity) -> dict:
    return {
        "name": name,
        "path": Path(f"/docs/{name}"),
        "why": None,
        "activity": activity,
        "artifacts": [],
        "docs": [],
        "dirs": [],
    }


def test_rows_within_a_group_still_come_back_most_recent_first():
    rows = [
        _row("unit-long-idle", Activity(modified=100)),
        _row("unit-just-touched", Activity(modified=2_000_000_000)),
    ]

    page = render([("Projects", rows)], CTX)

    assert page.index("unit-just-touched") < page.index("unit-long-idle")


def test_a_live_row_still_leads_regardless_of_timestamps():
    rows = [
        _row("ancient-but-live", Activity(modified=1, live=[{"pid": 1, "session": "s", "cwd": "/x", "kind": "claude", "name": None}])),
        _row("recent-but-idle", Activity(modified=2_000_000_000)),
    ]

    page = render([("Projects", rows)], CTX)

    assert page.index("ancient-but-live") < page.index("recent-but-idle")


def test_a_live_session_renders_on_the_card():
    from orglens import view
    from orglens.activity import Activity
    a = Activity(live=[{"session": "abc", "name": "working on it", "cwd": "/x/y"}])
    row = {"name": "unit", "path": Path("/tmp/unit"), "why": None, "activity": a,
           "artifacts": [], "dirs": [], "docs": []}
    html = view._detail(row, {"docs_roots": [], "base_url": ""})
    assert "Running now (1)" in html
    assert "working on it" in html


def test_a_recent_session_shows_how_it_is_the_units():
    from orglens import view
    from orglens.activity import Activity
    a = Activity(recent=[{"id": "abc", "at": 1, "agent": "claude", "outcome": "done",
                          "name": "n", "turns": 3, "open": False, "how": "attributed"}])
    row = {"name": "unit", "path": Path("/tmp/unit"), "why": None, "activity": a,
           "artifacts": [], "dirs": [], "docs": []}
    html = view._detail(row, {"docs_roots": [], "base_url": ""})
    assert "attributed" in html


def test_unattributed_sessions_render_in_their_own_section_at_the_end():
    from orglens.sessions import Session
    loose = [Session(id="deadbeef-1", agent="codex", cwd="/nowhere", started=1000_000,
                     ended=2000_000, turns=9, label="stray work", outcome="awaiting-user",
                     live=False, units=frozenset(), how=None)]
    page = render([("Projects", [_row("a", Activity())])], CTX, unattributed=loose)
    assert "data-band='unattributed'" in page
    assert "stray work" in page
    assert page.index("data-band='unattributed'") > page.index("data-unit='a'")
    assert "scad session resume deadbeef-1 --print" in page


def test_no_unattributed_sessions_means_no_section():
    page = render([("Projects", [_row("a", Activity())])], CTX, unattributed=[])
    assert "Unattributed" not in page


def _row_with(name, a, part_of=None, kind="project"):
    row = _row(name, a)
    row["part_of"] = part_of
    row["kind"] = kind
    return row


def _recent(id, agent, name, at=1):
    return {"id": id, "at": at, "agent": agent, "outcome": "done", "name": name,
            "turns": 3, "open": False, "how": "containment"}


def test_cards_carry_what_the_filters_scope_on():
    a = Activity(recent=[_recent("s1", "claude", "first pass"), _recent("s2", "kimi", "second")])
    page = render([("Projects", [_row_with("alpha", a)])], CTX)
    assert "data-unit='alpha'" in page
    assert "data-agents='claude kimi'" in page
    # Searchable text is lowercased and carries the session labels.
    assert "first pass" in page.split("data-text='", 1)[1].split("'", 1)[0]


def test_unattributed_rows_in_the_view_show_the_last_thing_said():
    from orglens.sessions import Session
    loose = [Session(id="deadbeef-1", agent="codex", cwd="/Users/x/somewhere/deep", started=1000_000,
                     ended=2000_000, turns=9, label=None, outcome="awaiting-user",
                     live=False, units=frozenset(), how=None,
                     last_turn={"ts": 1, "role": "assistant", "text": "I renamed the module"})]
    page = render([("Projects", [_row("a", Activity())])], CTX, unattributed=loose)
    assert "I renamed the module" in page
    assert "somewhere/deep" in page
