"""`view` as a daily driver: units banded by when they last moved, every
card foldable, the status line shown as the person's last word with its age."""

from __future__ import annotations

import time
from pathlib import Path

from orglens.activity import Activity
from orglens.view import band, clocks, render, stale

CTX = {"docs_roots": [Path("/docs")], "base_url": "http://localhost"}
NOW = 1_800_000_000
H = 3600


def _row(name, a, kind="project", part_of=None, why=None, why_age=None):
    return {"name": name, "kind": kind, "part_of": part_of, "path": Path(f"/docs/{name}"),
            "why": why, "why_edited": why_age, "activity": a,
            "artifacts": [], "docs": [], "dirs": []}


class TestClocks:
    def test_live_outranks_everything(self):
        a = Activity(live=[{"session": "s", "name": "n", "cwd": "/x"}], modified=NOW - 40 * 24 * H)
        assert clocks(a, now=NOW)[0] == ("live", NOW)

    def test_session_then_edit_then_commit(self):
        a = Activity(last_session=NOW - 2 * H, modified=NOW - 5 * H, touched=NOW - 9 * H)
        assert [c[0] for c in clocks(a, now=NOW)] == ["session", "edited", "committed"]

    def test_an_open_pane_that_has_not_spoken_for_a_day_is_idle_not_live(self):
        a = Activity(live=[{"session": "s", "name": "n", "cwd": "/x", "spoke": NOW - 3 * 24 * H}])
        assert clocks(a, now=NOW)[0] == ("idle", NOW - 3 * 24 * H)
        assert band(a, now=NOW) == "this week"
        page = render([("Projects", [_row("p", a)])], CTX, now=NOW)
        assert "open pane, idle 3d" in page and "&#x25CF; live" not in page

    def test_a_pane_that_spoke_today_is_live(self):
        a = Activity(live=[{"session": "s", "name": "n", "cwd": "/x", "spoke": NOW - 2 * H}])
        assert band(a, now=NOW) == "today"

    def test_a_gate_is_a_clock_of_its_own(self):
        a = Activity(needs=[{"question": "q", "at": NOW - H}])
        assert clocks(a, now=NOW)[0] == ("waiting", NOW - H)


class TestBand:
    def test_bands_by_the_newest_clock(self):
        assert band(Activity(last_session=NOW - 3 * H), now=NOW) == "today"
        assert band(Activity(modified=NOW - 30 * H), now=NOW) == "yesterday"
        assert band(Activity(touched=NOW - 4 * 24 * H), now=NOW) == "this week"
        assert band(Activity(last_session=NOW - 20 * 24 * H), now=NOW) == "this month"
        assert band(Activity(modified=NOW - 90 * 24 * H), now=NOW) == "earlier"
        assert band(Activity(), now=NOW) == "earlier"

    def test_waiting_is_its_own_band_whatever_the_clocks_say(self):
        a = Activity(needs=[{"question": "q", "at": NOW - 60 * 24 * H}], modified=NOW - 90 * 24 * H)
        assert band(a, now=NOW) == "waiting"


class TestStale:
    def test_a_status_line_older_than_the_newest_clock_by_a_week_is_stale(self):
        a = Activity(last_session=NOW - H)
        assert stale(a, why_edited=NOW - 10 * 24 * H, now=NOW) is True
        assert stale(a, why_edited=NOW - 2 * 24 * H, now=NOW) is False
        assert stale(a, why_edited=None, now=NOW) is False


class TestPage:
    def test_units_are_grouped_into_bands_newest_first(self):
        rows = [
            _row("old", Activity(modified=NOW - 90 * 24 * H)),
            _row("fresh", Activity(last_session=NOW - H)),
            _row("weekly", Activity(modified=NOW - 3 * 24 * H)),
        ]
        page = render([("Projects", rows)], CTX, now=NOW)
        assert page.index("data-band='today'") < page.index("data-band='this week'") < page.index("data-band='earlier'")
        today = page[page.index("data-band='today'"):page.index("data-band='this week'")]
        assert "data-unit='fresh'" in today and "data-unit='weekly'" not in today

    def test_kind_is_a_chip_not_a_section(self):
        page = render([("Projects", [_row("p", Activity(last_session=NOW - H))]),
                       ("Clients", [_row("c", Activity(last_session=NOW - 2 * H), kind="client")])], CTX, now=NOW)
        assert "<h2 class='grp' data-group='Projects'>" not in page
        assert "class='kind'>project<" in page and "class='kind'>client<" in page
        assert "data-kind='client'" in page

    def test_waiting_band_comes_first_with_the_question_on_the_card(self):
        rows = [_row("hot", Activity(last_session=NOW - H)),
                _row("asked", Activity(needs=[{"question": "which way?", "at": NOW - 5 * H}]))]
        page = render([("Projects", rows)], CTX, now=NOW)
        assert page.index("data-band='waiting'") < page.index("data-band='today'")
        waiting = page[page.index("data-band='waiting'"):page.index("data-band='today'")]
        assert "which way?" in waiting and "data-unit='asked'" in waiting

    def test_the_card_says_which_clock_placed_it(self):
        page = render([("Projects", [_row("p", Activity(last_session=NOW - 3 * H, modified=NOW - 30 * H))])], CTX, now=NOW)
        card = page[page.index("data-unit='p'"):]
        assert "session 3h ago" in card
        assert card.index("session 3h ago") < card.index("edited 1d ago")

    def test_a_stale_status_line_is_marked(self):
        a = Activity(last_session=NOW - H)
        page = render([("Projects", [_row("p", a, why="v1 done", why_age=NOW - 20 * 24 * H)])], CTX, now=NOW)
        assert "class='why stale'" in page and "20d old" in page
        page2 = render([("Projects", [_row("p", a, why="v1 done", why_age=NOW - H)])], CTX, now=NOW)
        assert "class='why stale'" not in page2

    def test_sessions_and_edits_far_apart_get_a_tag(self):
        talked = render([("Projects", [_row("p", Activity(last_session=NOW - H, modified=NOW - 30 * 24 * H))])], CTX, now=NOW)
        assert "nothing landed" in talked
        landed = render([("Projects", [_row("p", Activity(modified=NOW - H, last_session=NOW - 30 * 24 * H))])], CTX, now=NOW)
        assert "no session" in landed

    def test_an_experiment_nests_under_its_programme(self):
        rows = [_row("prog", Activity(last_session=NOW - H), kind="research-program"),
                _row("expt-1", Activity(modified=NOW - 2 * H), kind="experiment", part_of="prog")]
        page = render([("Research programs", [rows[0]]), ("Experiments", [rows[1]])], CTX, now=NOW)
        prog_card = page[page.index("data-unit='prog'"):]
        assert "data-unit='expt-1'" in prog_card
        assert page.count("data-unit='expt-1'") == 1

    def test_bands_older_than_yesterday_are_folded(self):
        rows = [_row("a", Activity(last_session=NOW - H)), _row("b", Activity(modified=NOW - 10 * 24 * H))]
        page = render([("Projects", rows)], CTX, now=NOW)
        assert "<details class='band' data-band='today' open>" in page
        assert "<details class='band' data-band='this month'>" in page
