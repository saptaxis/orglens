"""`view` as a daily driver: units banded by when they last moved, every
card foldable, the status line shown as the person's last word with its age."""

from __future__ import annotations

import time
from pathlib import Path

from orglens.activity import Activity
from orglens.view import band, clocks, placing, render, stale

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

    def test_units_naming_each_other_as_parents_both_stay_on_the_page(self):
        # A cycle has no top-level member, so nesting under parents drew
        # neither card. Each is a top-level card instead.
        rows = [_row("a", Activity(last_session=NOW - H), part_of="b"),
                _row("b", Activity(last_session=NOW - H), part_of="a")]
        page = render([("Projects", rows)], CTX, now=NOW)
        assert "data-unit='a'" in page
        assert "data-unit='b'" in page

    def test_bands_through_last_week_are_open_and_older_ones_folded(self):
        rows = [_row("a", Activity(last_session=NOW - H)),
                _row("b", Activity(modified=NOW - 10 * 24 * H)),
                _row("c", Activity(modified=NOW - 20 * 24 * H))]
        page = render([("Projects", rows)], CTX, now=NOW)
        assert "<details class='band' data-band='today' open>" in page
        assert "<details class='band' data-band='last week' open>" in page
        assert "<details class='band' data-band='this month'>" in page


def _recent(page):
    return page[page.index("<section data-tab='recent'>"):page.index("<section data-tab='explore'>")]


def _explore(page):
    return page[page.index("<section data-tab='explore'>"):]


TREE = [
    _row("org", Activity(last_session=NOW - 3 * H), kind="organization"),
    _row("prog", Activity(last_session=NOW - 30 * H), kind="research", part_of="org"),
    _row("expt", Activity(last_session=NOW - 2 * H), kind="experiment", part_of="prog"),
    _row("alpha", Activity(last_session=NOW - 5 * H), part_of="org"),
    _row("beta", Activity(last_session=NOW - H), part_of="org"),
]


class TestPlacing:
    def test_by_session_ignores_a_newer_edit(self):
        a = Activity(last_session=NOW - 5 * 24 * H, modified=NOW - H)
        assert band(a, now=NOW, by="session") == "this week"
        assert band(a, now=NOW, by="edit") == "today"

    def test_a_unit_with_no_session_is_placed_by_its_edit(self):
        a = Activity(modified=NOW - 3 * H)
        assert placing(a, "session", NOW) == ("edited", NOW - 3 * H)

    def test_a_unit_with_no_edit_is_placed_by_its_session(self):
        a = Activity(last_session=NOW - 3 * H)
        assert placing(a, "edit", NOW) == ("session", NOW - 3 * H)

    def test_waiting_comes_first_in_either_mode(self):
        a = Activity(needs=[{"question": "q", "at": NOW - 9 * 24 * H}], modified=NOW - H)
        assert band(a, now=NOW, by="edit") == "waiting"
        assert band(a, now=NOW, by="session") == "waiting"

    def test_last_week_is_seven_to_fourteen_days(self):
        assert band(Activity(last_session=NOW - 8 * 24 * H), now=NOW) == "last week"
        assert band(Activity(last_session=NOW - 15 * 24 * H), now=NOW) == "this month"

    def test_every_card_carries_both_bands_and_both_lines(self):
        page = render([("All", [_row("p", Activity(last_session=NOW - 5 * 24 * H,
                                                    modified=NOW - H))])], CTX, now=NOW)
        assert "data-bs='this week' data-be='today'" in page
        card = _recent(page)
        session = card[card.index("facts by-session"):card.index("facts by-edit")]
        edit = card[card.index("facts by-edit"):]
        assert session.index("session 5d ago") < session.index("edited 1h ago")
        assert "<span class='placed'>session 5d ago" in session
        assert "<span class='placed'>edited 1h ago" in edit


class TestRecent:
    def test_every_unit_is_its_own_card_banded_by_its_own_time(self):
        """0.6.0 nested everything inside the organisations' cards, so the
        page showed two."""
        recent = _recent(render([("All", TREE)], CTX, now=NOW))
        today = recent[recent.index("data-band='today'"):recent.index("data-band='yesterday'")]
        yesterday = recent[recent.index("data-band='yesterday'"):recent.index("data-band='this week'")]
        for name in ("org", "expt", "alpha", "beta"):
            assert f"data-unit='{name}'" in today
        assert "data-unit='prog'" in yesterday
        assert recent.count("class='nested'") == 0

    def test_each_card_shows_its_path_and_a_name_in_it_scopes(self):
        recent = _recent(render([("All", TREE)], CTX, now=NOW))
        card = recent[recent.index("data-unit='expt'"):]
        assert "<a class='seg' data-scope='org'>org</a>" in card
        assert "<a class='seg' data-scope='prog'>prog</a>" in card
        assert "data-anc=' org prog expt '" in recent

    def test_cards_in_a_band_are_sorted_by_path(self):
        recent = _recent(render([("All", TREE)], CTX, now=NOW))
        order = [recent.index(f"data-unit='{n}'") for n in ("org", "alpha", "beta", "expt")]
        assert order == sorted(order)

    def test_the_scope_filter_lists_every_unit_with_units_under_it(self):
        page = render([("All", TREE)], CTX, now=NOW)
        scope = page[page.index("<select id='scope'>"):page.index("</select>")]
        assert "value='org'" in scope and "value='prog'" in scope
        assert "value='expt'" not in scope and "value='alpha'" not in scope
        assert scope.index("value='org'") < scope.index("value='prog'")


class TestExplore:
    def test_the_tree_nests_with_kinds_grouped_under_a_top_node(self):
        explore = _explore(render([("All", TREE)], CTX, now=NOW))
        assert explore.count("data-unit='expt' data-parent") == 1
        prog = explore[explore.index("<div class='node' data-unit='prog'>"):]
        assert "data-unit='expt'" in prog
        groups = explore[explore.index("<div class='node' data-unit='org'>"):]
        assert groups.index("<details class='kgroup' open><summary>project") \
            < groups.index("data-unit='beta'")
        assert "<summary>research" in groups

    def test_siblings_are_sorted_by_recency(self):
        explore = _explore(render([("All", TREE)], CTX, now=NOW))
        assert explore.index("data-unit='beta'") < explore.index("data-unit='alpha'")

    def test_a_single_kind_below_the_top_is_not_grouped(self):
        explore = _explore(render([("All", TREE)], CTX, now=NOW))
        prog = explore[explore.index("<div class='node' data-unit='prog'>"):]
        prog = prog[:prog.index("data-unit='expt'")]
        assert "kgroup" not in prog

    def test_explore_cards_draw_no_path(self):
        explore = _explore(render([("All", TREE)], CTX, now=NOW))
        assert "class='seg'" not in explore

    def test_both_tabs_are_on_the_page_recent_first(self):
        page = render([("All", TREE)], CTX, now=NOW)
        assert page.index("data-tab='recent'>Recent<") < page.index("data-tab='explore'>Explore<")
        assert "<main data-tab='recent' data-by='session'>" in page
