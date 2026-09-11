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
