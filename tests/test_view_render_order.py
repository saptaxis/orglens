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
    assert "Unattributed (1)" in page
    assert "stray work" in page
    assert page.index("Unattributed (1)") > page.index("Projects")
    assert "scad session resume deadbeef-1 --print" in page


def test_no_unattributed_sessions_means_no_section():
    page = render([("Projects", [_row("a", Activity())])], CTX, unattributed=[])
    assert "Unattributed" not in page
