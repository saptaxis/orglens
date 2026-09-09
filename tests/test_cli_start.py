"""`orglens start` — the unit is what you asked for, launch and attribution
follow from it. See orglens/cli.py's `start` for the design sentence.
"""

from __future__ import annotations

import json

from click.testing import CliRunner

from orglens import activity, events
from orglens.cli import cli, _session_id_from


def test_the_session_id_is_read_from_scads_own_record():
    # `--json` makes scad emit its launch record as one JSON object. The id
    # is a contract that record publishes, not prose to scrape a line out of.
    out = json.dumps({
        "agent": "claude",
        "session_id": "55d76105-719a-4ee7-96f5-6a93de9c9cc1",
        "cwd": "/somewhere",
        "tmux": "scad-cl-1605:0.0",
        "started": "2026-09-09T10:43:13Z",
        "resume": "cd /somewhere && claude --resume 55d76105-719a-4ee7-96f5-6a93de9c9cc1",
        "provenance": "minted",
    })
    assert _session_id_from(out) == "55d76105-719a-4ee7-96f5-6a93de9c9cc1"


def test_no_usable_id_is_none_not_a_crash():
    assert _session_id_from("not json at all") is None
    assert _session_id_from("") is None
    assert _session_id_from(json.dumps({"agent": "claude"})) is None
    assert _session_id_from(json.dumps({"session_id": ""})) is None


def test_start_records_an_attribution(tmp_path, monkeypatch, two_root_tree_config):
    calls = {}

    def fake_launch(cwd, agent, prompt):
        calls["cwd"] = cwd
        calls["agent"] = agent
        return "sess-123"

    monkeypatch.setattr("orglens.cli._launch", fake_launch)
    monkeypatch.setattr("orglens.cli.EVENTS_DIR", tmp_path / "events")

    result = CliRunner().invoke(cli, ["start", "orglens", "--home", "orglens"])
    assert result.exit_code == 0
    assert events.attributions(root=tmp_path / "events") == {"sess-123": "orglens"}


def test_start_in_a_unit_with_several_homes_requires_choosing(tmp_path, monkeypatch,
                                                              two_root_tree_config):
    # `CliRunner.invoke` swallows an exception raised inside the command into
    # `result.exception` rather than letting it reach pytest, so a stub that
    # merely raises when called is inert — the test would stay green even if
    # `start` regressed into calling `_launch` here. Recording the call and
    # asserting on the record directly is what actually catches that.
    called = []

    def record_call(cwd, agent, prompt):
        called.append((cwd, agent, prompt))
        return "should-not-be-reached"

    monkeypatch.setattr("orglens.cli._launch", record_call)
    monkeypatch.setattr("orglens.cli.EVENTS_DIR", tmp_path / "events")

    result = CliRunner().invoke(cli, ["start", "orglens"])
    # Two homes and no --home: the command says which are available rather
    # than picking one and being wrong quietly.
    assert "--home" in result.output
    assert called == []
    assert result.exit_code == 1


def test_dry_run_launches_nothing_and_records_nothing(tmp_path, monkeypatch,
                                                      two_root_tree_config):
    monkeypatch.setattr("orglens.cli.EVENTS_DIR", tmp_path / "events")
    result = CliRunner().invoke(cli, ["start", "orglens", "--home", "orglens",
                                      "--dry-run"])
    assert result.exit_code == 0
    assert events.attributions(root=tmp_path / "events") == {}


def test_a_launch_that_yields_no_id_still_exits_zero_and_says_so(tmp_path, monkeypatch,
                                                                two_root_tree_config):
    monkeypatch.setattr("orglens.cli._launch", lambda c, a, p: None)
    monkeypatch.setattr("orglens.cli.EVENTS_DIR", tmp_path / "events")
    result = CliRunner().invoke(cli, ["start", "orglens", "--home", "orglens"])
    assert result.exit_code == 0
    assert "not attributed" in result.output.lower()
    assert events.attributions(root=tmp_path / "events") == {}


def test_the_arrival_names_the_unit_and_all_its_homes(two_root_tree):
    from orglens.cli import _arrival

    unit = two_root_tree.resolve("orglens")
    chosen = next(h for h in unit.homes if h.path is not None)
    text = _arrival(unit, chosen, two_root_tree)

    assert "orglens" in text

    # Isolated to the homes-listing region ("  {name}  ->  {path}" lines
    # under "Its homes are:") rather than searched for across the whole
    # text. In this fixture the driver-document line further down names a
    # path that happens to sit inside the second home's directory, so a
    # whole-text search would pass even if the homes loop below printed only
    # `chosen` — which is exactly the regression this test exists to catch.
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if "Its homes are:" in line)
    end = start + 1
    while end < len(lines) and lines[end].strip():
        end += 1
    homes_region = "\n".join(lines[start:end])

    # Every home, not only the one launched in — the point is that the session
    # learns the work is bigger than the directory it woke up in.
    for home in unit.homes:
        if home.path is not None:
            assert str(home.path) in homes_region


def test_the_arrival_points_at_the_driver_document_when_there_is_one(two_root_tree):
    from orglens.cli import _arrival

    unit = two_root_tree.resolve("orglens")
    chosen = next(h for h in unit.homes if h.path is not None)
    assert "overview.md" in _arrival(unit, chosen, two_root_tree)


def test_the_arrival_survives_a_unit_with_nothing_in_it(tmp_path, grammar):
    from orglens.cli import _arrival
    from orglens.declaration import MARKER
    from orglens.units import Registry

    bare = tmp_path / "docs" / "projects" / "bare"
    bare.mkdir(parents=True)
    (bare / MARKER).write_text("unit: bare\nkind: project\nhomes:\n  - x\n")
    (tmp_path / "x").mkdir()
    registry = Registry([tmp_path / "docs", tmp_path], grammar)

    unit = registry.resolve("bare")
    chosen = next(h for h in unit.homes if h.path is not None)
    text = _arrival(unit, chosen, registry)
    assert "bare" in text          # no overview, no status, still says something


def test_an_explicit_prompt_replaces_the_arrival(tmp_path, monkeypatch,
                                                 two_root_tree_config):
    seen = {}
    monkeypatch.setattr("orglens.cli._launch",
                        lambda cwd, agent, prompt: seen.update(prompt=prompt) or "s1")
    monkeypatch.setattr("orglens.cli.EVENTS_DIR", tmp_path / "events")
    CliRunner().invoke(cli, ["start", "orglens", "--home", "orglens",
                             "--prompt", "just do the thing"])
    assert seen["prompt"] == "just do the thing"


def test_list_passes_attributions_to_peek(tmp_path, monkeypatch, two_root_tree_config):
    # An assertion made by `start` must reach `list`'s ordering, or recording
    # it bought nothing. Spying on `activity.peek` sidesteps the real
    # `~/.scad/index.sqlite` entirely and catches a missed call site directly,
    # rather than via a count that could pass for the wrong reason.
    monkeypatch.setattr("orglens.cli.EVENTS_DIR", tmp_path / "events")
    events.append(
        events.Event("attributed", "orglens", "sess-abc", 100, "test"),
        root=tmp_path / "events",
    )

    calls = []

    def fake_peek(paths, name, index=None, home_names=None, attributed=None):
        calls.append(attributed)
        return activity.Activity()

    monkeypatch.setattr("orglens.activity.peek", fake_peek)

    result = CliRunner().invoke(cli, ["list"])
    assert result.exit_code == 0
    assert calls, "activity.peek was never called"
    assert calls[0] == {"sess-abc": "orglens"}


def test_status_passes_attributions_to_read(tmp_path, monkeypatch, two_root_tree_config):
    # Same claim as `list`'s test, for `status`'s reader instead.
    monkeypatch.setattr("orglens.cli.EVENTS_DIR", tmp_path / "events")
    events.append(
        events.Event("attributed", "orglens", "sess-abc", 100, "test"),
        root=tmp_path / "events",
    )

    calls = []

    def fake_read(paths, name, index=None, home_names=None, attributed=None):
        calls.append(attributed)
        return activity.Activity()

    monkeypatch.setattr("orglens.activity.read", fake_read)

    result = CliRunner().invoke(cli, ["status"])
    assert result.exit_code == 0
    assert calls, "activity.read was never called"
    assert calls[0] == {"sess-abc": "orglens"}


def test_view_passes_attributions_to_read(tmp_path, monkeypatch, two_root_tree_config):
    # Same claim again, for `view`'s reader. `--out` and `--no-open` keep this
    # hermetic: nothing is written outside `tmp_path`, and nothing tries to
    # shell out to `open`.
    monkeypatch.setattr("orglens.cli.EVENTS_DIR", tmp_path / "events")
    events.append(
        events.Event("attributed", "orglens", "sess-abc", 100, "test"),
        root=tmp_path / "events",
    )

    calls = []

    def fake_read(paths, name, index=None, home_names=None, attributed=None):
        calls.append(attributed)
        return activity.Activity()

    monkeypatch.setattr("orglens.activity.read", fake_read)

    out = tmp_path / "view.html"
    result = CliRunner().invoke(cli, ["view", "--out", str(out), "--no-open"])
    assert result.exit_code == 0
    assert calls, "activity.read was never called"
    assert calls[0] == {"sess-abc": "orglens"}
