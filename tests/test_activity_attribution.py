import json
import os
import sqlite3
from pathlib import Path

from orglens import activity
from tests.conftest import scad_index as _index


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


def test_the_index_location_is_read_when_called_not_when_imported(tmp_path, monkeypatch):
    # `index` defaulted to `SCAD_INDEX` in the signature, which bound the real
    # `~/.scad/index.sqlite` at import time, so a caller that passed nothing
    # (`list`, `status`, `view`) could not be pointed anywhere else by a test.
    home = tmp_path / "orglens"
    home.mkdir()
    index = _index(tmp_path, [("s1", str(home), "orglens")])
    monkeypatch.setattr(activity, "SCAD_INDEX", index)

    assert activity.read([home], "orglens").sessions == 1
    assert activity.peek([home], "orglens").sessions == 1
