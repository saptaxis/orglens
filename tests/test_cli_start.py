"""`orglens start` — the unit is what you asked for, launch and attribution
follow from it. See orglens/cli.py's `start` for the design sentence.
"""

from __future__ import annotations

import json
import subprocess

from click.testing import CliRunner

from orglens import activity, events
from orglens.cli import cli, _launch, _launch_record


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
    assert _launch_record(out)["session_id"] == "55d76105-719a-4ee7-96f5-6a93de9c9cc1"


def test_no_usable_id_is_none_not_a_crash():
    assert _launch_record("not json at all") is None
    assert _launch_record("") is None
    assert _launch_record(json.dumps({"agent": "claude"})) is None
    assert _launch_record(json.dumps({"session_id": ""})) is None


def _fake_run(returncode, stdout, stderr=""):
    def run(argv, capture_output, text, timeout):
        return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr=stderr)
    return run


def test_launch_returns_the_session_id_scad_minted(tmp_path, monkeypatch):
    record = json.dumps({"session_id": "sess-launched", "agent": "claude"})
    monkeypatch.setattr("orglens.cli.subprocess.run", _fake_run(0, record))

    assert _launch(tmp_path, "claude", None)["session_id"] == "sess-launched"


def test_a_nonzero_returncode_is_no_session_even_with_a_parseable_record(tmp_path,
                                                                         monkeypatch):
    # scad can exit non-zero while still printing a record shaped correctly
    # enough to parse — the returncode, not the record's shape, is what says
    # whether the launch succeeded. Delete the `returncode != 0` guard and
    # this goes green on a session that never actually started.
    record = json.dumps({"session_id": "sess-should-not-count", "agent": "claude"})
    monkeypatch.setattr("orglens.cli.subprocess.run", _fake_run(1, record))

    assert _launch(tmp_path, "claude", None) is None


def test_stderr_reaches_the_caller_and_stdout_is_not_echoed(tmp_path, monkeypatch, capsys):
    # Under `--json`, stdout is the machine record and stderr carries scad's
    # human-facing words. Echoing stdout here would print the JSON blob at
    # whoever ran `orglens start`; the fix is that only stderr is forwarded.
    record = json.dumps({"session_id": "sess-quiet", "agent": "claude"})
    human_line = "[scad] launched claude in scad-cl-1813:0.0"
    monkeypatch.setattr("orglens.cli.subprocess.run",
                        _fake_run(0, record, stderr=human_line))

    _launch(tmp_path, "claude", None)

    captured = capsys.readouterr()
    assert "sess-quiet" not in captured.out
    assert captured.out == ""
    assert human_line in captured.err


def test_a_subprocess_that_cannot_start_yields_no_session_not_a_crash(tmp_path,
                                                                      monkeypatch):
    def run(argv, capture_output, text, timeout):
        raise OSError("scad not found")
    monkeypatch.setattr("orglens.cli.subprocess.run", run)

    assert _launch(tmp_path, "claude", None) is None


def test_start_records_an_attribution(tmp_path, monkeypatch, two_root_tree_config):
    calls = {}

    def fake_launch(cwd, agent, prompt, window=None, name=None, split=False):
        calls["cwd"] = cwd
        calls["agent"] = agent
        return {"session_id": "sess-123"}

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
    monkeypatch.setattr("orglens.cli._launch", lambda c, a, p, **kw: None)
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
                        lambda cwd, agent, prompt, **kw: seen.update(prompt=prompt) or {"session_id": "s1"})
    monkeypatch.setattr("orglens.cli.EVENTS_DIR", tmp_path / "events")
    CliRunner().invoke(cli, ["start", "orglens", "--home", "orglens",
                             "--prompt", "just do the thing"])
    assert seen["prompt"] == "just do the thing"


def _attributed_elsewhere(tmp_path, monkeypatch):
    """A scad export holding one session that ran above every home, and an
    event attributing it to orglens. Only the event can make it orglens's."""
    from tests.conftest import export_row, fake_scad
    monkeypatch.setattr("orglens.sessions.run_scad",
                        fake_scad([export_row("sess-abc", str(tmp_path))]))
    monkeypatch.setattr("orglens.cli.EVENTS_DIR", tmp_path / "events")
    events.append(
        events.Event("attributed", "orglens", "sess-abc", 100, "test"),
        root=tmp_path / "events",
    )


def _spy(calls):
    def fake(paths, name, sessions=None, memos=None):
        calls[name] = sessions or []
        return activity.Activity()
    return fake


def test_list_passes_the_attributed_session_to_peek(tmp_path, monkeypatch, two_root_tree_config):
    # An assertion made by `start` must reach `list`'s ordering, or recording
    # it bought nothing. Spying on `activity.peek` catches a missed call site
    # directly, rather than via a count that could pass for the wrong reason.
    _attributed_elsewhere(tmp_path, monkeypatch)
    calls: dict = {}
    monkeypatch.setattr("orglens.activity.peek", _spy(calls))

    result = CliRunner().invoke(cli, ["list"])
    assert result.exit_code == 0
    assert calls, "activity.peek was never called"
    assert [(s.id, s.how) for s in calls["orglens"]] == [("sess-abc", "attributed")]


def test_status_passes_the_attributed_session_to_read(tmp_path, monkeypatch, two_root_tree_config):
    _attributed_elsewhere(tmp_path, monkeypatch)
    calls: dict = {}
    monkeypatch.setattr("orglens.activity.read", _spy(calls))

    result = CliRunner().invoke(cli, ["status"])
    assert result.exit_code == 0
    assert [(s.id, s.how) for s in calls["orglens"]] == [("sess-abc", "attributed")]


def test_view_passes_the_attributed_session_to_read(tmp_path, monkeypatch, two_root_tree_config):
    # `--out` and `--no-open` keep this hermetic: nothing is written outside
    # `tmp_path`, and nothing tries to shell out to `open`.
    _attributed_elsewhere(tmp_path, monkeypatch)
    calls: dict = {}
    monkeypatch.setattr("orglens.activity.read", _spy(calls))

    out = tmp_path / "view.html"
    result = CliRunner().invoke(cli, ["view", "--out", str(out), "--no-open"])
    assert result.exit_code == 0
    assert [(s.id, s.how) for s in calls["orglens"]] == [("sess-abc", "attributed")]


def test_start_prints_the_way_back_in(tmp_path, monkeypatch, two_root_tree_config):
    # scad launches detached and prints a pane; through orglens that pane
    # arrived on stderr with no attach command and no `resume` line, so an
    # agent that ran `start` had no idea the session was already running.
    def fake_launch(cwd, agent, prompt, window=None, name=None, split=False):
        return {"session_id": "sess-123", "tmux": "scad-cl-2347:0.0"}
    monkeypatch.setattr("orglens.cli._launch", fake_launch)
    monkeypatch.setattr("orglens.cli.EVENTS_DIR", tmp_path / "events")

    result = CliRunner().invoke(cli, ["start", "orglens", "--home", "orglens"])
    assert result.exit_code == 0, result.output
    assert "attributed session sess-123 to orglens" in result.output
    assert "running detached" in result.output
    assert "tmux attach -t scad-cl-2347" in result.output
    assert "orglens resume orglens" in result.output


def test_dry_run_says_the_launch_is_detached(tmp_path, monkeypatch, two_root_tree_config):
    result = CliRunner().invoke(cli, ["start", "orglens", "--home", "orglens", "--dry-run",
                                      "--prompt", "do the thing"])
    assert result.exit_code == 0
    assert "detached" in result.output
    assert "scad session launch" in result.output
    assert "do the thing" in result.output
    assert "returns at once" in result.output or "your terminal" in result.output


def test_launch_returns_the_record_not_only_the_id(tmp_path, monkeypatch):
    record = json.dumps({"session_id": "sess-launched", "agent": "claude", "tmux": "scad-cl-1:0.0"})
    monkeypatch.setattr("orglens.cli.subprocess.run", _fake_run(0, record))
    got = _launch(tmp_path, "claude", None)
    assert got["session_id"] == "sess-launched" and got["tmux"] == "scad-cl-1:0.0"


def _named(monkeypatch, tmp_path, seen, extra=()):
    def fake_launch(cwd, agent, prompt, window=None, name=None, split=False):
        seen.update(window=window, name=name)
        return {"session_id": "s1"}
    monkeypatch.setattr("orglens.cli._launch", fake_launch)
    monkeypatch.setattr("orglens.cli.EVENTS_DIR", tmp_path / "events")
    return CliRunner().invoke(cli, ["start", "orglens", "--home", "orglens", *extra])


def test_the_composed_name_is_unit_context_and_day(tmp_path, monkeypatch,
                                                   two_root_tree_config):
    """What the person writes by hand: `orglens-backlog-feats-sep11`. The bare
    unit name is worse than scad's own default, which at least appends two
    characters — two sessions on one unit would both be `orglens`."""
    import time
    monkeypatch.setattr("orglens.cli.time.localtime",
                        lambda *a: time.strptime("2026-09-25", "%Y-%m-%d"))
    seen = {}
    _named(monkeypatch, tmp_path, seen, ["--about", "backlog feats"])
    assert seen["name"] == "orglens-backlog-feats-sep25"


def test_without_context_it_is_unit_and_day(tmp_path, monkeypatch, two_root_tree_config):
    import time
    monkeypatch.setattr("orglens.cli.time.localtime",
                        lambda *a: time.strptime("2026-09-25", "%Y-%m-%d"))
    seen = {}
    _named(monkeypatch, tmp_path, seen)
    assert seen["name"] == "orglens-sep25"


def test_only_two_words_of_context_survive(tmp_path, monkeypatch, two_root_tree_config):
    import time
    monkeypatch.setattr("orglens.cli.time.localtime",
                        lambda *a: time.strptime("2026-09-25", "%Y-%m-%d"))
    seen = {}
    _named(monkeypatch, tmp_path, seen, ["--about", "org mode backend discussion"])
    assert seen["name"] == "orglens-org-mode-sep25"


def test_an_explicit_name_is_used_as_given(tmp_path, monkeypatch, two_root_tree_config):
    seen = {}
    _named(monkeypatch, tmp_path, seen, ["--name", "whatever-I-said"])
    assert seen["name"] == "whatever-I-said"


def test_no_name_launches_unnamed(tmp_path, monkeypatch, two_root_tree_config):
    seen = {}
    _named(monkeypatch, tmp_path, seen, ["--no-name"])
    assert seen["name"] is None


def test_a_name_already_in_the_index_is_uniquified(tmp_path, monkeypatch,
                                                  two_root_tree_config):
    """Two sessions on one unit on one day is ordinary; two with one name is
    not, and the /resume picker is where that hurts."""
    import time
    from orglens.sessions import Session
    monkeypatch.setattr("orglens.cli.time.localtime",
                        lambda *a: time.strptime("2026-09-25", "%Y-%m-%d"))
    monkeypatch.setattr("orglens.cli.sessions.all_sessions", lambda *a: [
        Session(id="old", agent="claude", cwd=None, started=None, ended=None,
                turns=1, label="orglens-sep25", outcome=None, live=False,
                units=frozenset({"orglens"}), how="attributed"),
    ])
    seen = {}
    _named(monkeypatch, tmp_path, seen)
    assert seen["name"] == "orglens-sep25-2"


def test_the_window_takes_the_context_when_there_is_one(tmp_path, monkeypatch,
                                                        two_root_tree_config):
    """A window name sits in the status bar, so it stays short: the context if
    there is one, the unit otherwise, and never the date."""
    seen = {}
    _named(monkeypatch, tmp_path, seen, ["--window", "--about", "org mode"])
    assert seen["window"] == "org-mode"


def test_window_and_name_are_passed_to_scad(tmp_path, monkeypatch,
                                            two_root_tree_config):
    """The unit name is the one thing orglens knows and scad does not, so it
    is what the window and the session are called."""
    seen = {}

    def fake_launch(cwd, agent, prompt, window=None, name=None, split=False):
        seen.update(window=window, name=name)
        return {"session_id": "s1"}

    monkeypatch.setattr("orglens.cli._launch", fake_launch)
    monkeypatch.setattr("orglens.cli.EVENTS_DIR", tmp_path / "events")
    import time
    monkeypatch.setattr("orglens.cli.time.localtime",
                        lambda *a: time.strptime("2026-09-25", "%Y-%m-%d"))
    CliRunner().invoke(cli, ["start", "orglens", "--home", "orglens", "--window"])
    assert seen == {"window": "orglens", "name": "orglens-sep25"}


def test_no_name_leaves_the_session_unnamed(tmp_path, monkeypatch,
                                            two_root_tree_config):
    seen = {}

    def fake_launch(cwd, agent, prompt, window=None, name=None, split=False):
        seen.update(window=window, name=name)
        return {"session_id": "s1"}

    monkeypatch.setattr("orglens.cli._launch", fake_launch)
    monkeypatch.setattr("orglens.cli.EVENTS_DIR", tmp_path / "events")
    CliRunner().invoke(cli, ["start", "orglens", "--home", "orglens", "--no-name"])
    assert seen == {"window": None, "name": None}


def test_the_launch_argv_carries_window_and_name(tmp_path, monkeypatch):
    seen = []
    inner = _fake_run(0, json.dumps({"session_id": "s1"}))

    def run(argv, **kw):
        seen.append(argv)
        return inner(argv, **kw)

    monkeypatch.setattr("orglens.cli.subprocess.run", run)
    _launch(tmp_path, "claude", None, window="orglens", name="orglens")
    assert seen[0][-4:] == ["--window", "orglens", "--name", "orglens"]


def test_split_is_passed_to_scad(tmp_path, monkeypatch, two_root_tree_config):
    """A pane beside the one you typed in; scad does the splitting."""
    seen = {}

    def fake_launch(cwd, agent, prompt, window=None, name=None, split=False):
        seen.update(window=window, split=split)
        return {"session_id": "s1"}

    monkeypatch.setattr("orglens.cli._launch", fake_launch)
    monkeypatch.setattr("orglens.cli.EVENTS_DIR", tmp_path / "events")
    result = CliRunner().invoke(cli, ["start", "orglens", "--home", "orglens", "--split"])
    assert result.exit_code == 0, result.output
    assert seen == {"window": None, "split": True}


def test_split_and_window_together_are_refused(tmp_path, monkeypatch,
                                                two_root_tree_config):
    monkeypatch.setattr("orglens.cli._launch", lambda *a, **k: {"session_id": "s1"})
    result = CliRunner().invoke(cli, ["start", "orglens", "--home", "orglens",
                                      "--split", "--window"])
    assert result.exit_code != 0


def test_launch_hands_split_to_scad(tmp_path, monkeypatch):
    argvs = []

    def run(argv, **kw):
        argvs.append(argv)
        return _fake_run(0, json.dumps({"session_id": "s"}))(argv, **kw)

    monkeypatch.setattr("orglens.cli.subprocess.run", run)
    _launch(tmp_path, "claude", None, split=True)
    assert "--split" in argvs[0]
