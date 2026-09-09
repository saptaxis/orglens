"""`recency` is the one decision behind three renderings — `list`, `status`
and the HTML view. It used to live only in `view.py`, reaching into a row
dict; it is tested here directly, against the `Activity` it now takes."""

from __future__ import annotations

from orglens.activity import Activity, recency


def test_a_recent_file_edit_outranks_a_stale_session():
    edited_recently = Activity(modified=2_000_000_000, last_session=100)
    spoke_long_ago = Activity(modified=100, last_session=100)
    assert recency(edited_recently) > recency(spoke_long_ago)


def test_a_recent_session_outranks_a_stale_file_edit():
    stale_edit_recent_session = Activity(modified=100, last_session=2_000_000_000)
    stale_edit_stale_session = Activity(modified=100, last_session=100)
    assert (
        recency(stale_edit_recent_session) > recency(stale_edit_stale_session)
    )


def test_the_last_turn_wins_over_the_session_end_time_when_later():
    a = Activity(last_session=100, last_turn={"at": 900})
    assert recency(a) == 900


def test_a_live_session_outranks_every_timestamp():
    ancient_but_live = Activity(modified=1, live=[{"pid": 1}])
    recent_but_idle = Activity(modified=2_000_000_000)
    assert recency(ancient_but_live) > recency(recent_but_idle)


def test_no_activity_at_all_sorts_low_rather_than_raising():
    assert recency(Activity()) == 0
