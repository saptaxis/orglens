"""`orglens start` — the unit is what you asked for, launch and attribution
follow from it. See orglens/cli.py's `start` for the design sentence.
"""

from __future__ import annotations

from click.testing import CliRunner

from orglens import events
from orglens.cli import cli, _session_id_from


def test_the_session_id_is_read_from_scads_own_output():
    # scad prints `[scad] session: <id>` and writes a durable record. Reading
    # the id it printed is exact; finding the newest launch file would be a
    # guess.
    out = (
        "[scad] launching claude in scad-cl-1605\n"
        "[scad] session: 55d76105-719a-4ee7-96f5-6a93de9c9cc1  pane scad-cl-1605:0.0\n"
        "[scad] resume: cd /somewhere && claude --resume 55d76105-719a-4ee7-96f5-6a93de9c9cc1\n"
    )
    assert _session_id_from(out) == "55d76105-719a-4ee7-96f5-6a93de9c9cc1"


def test_no_session_line_is_none_not_a_crash():
    assert _session_id_from("[scad] something went sideways\n") is None
    assert _session_id_from("") is None


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
    def fail_if_called(cwd, agent, prompt):
        raise AssertionError("_launch must not be called when a home is ambiguous")

    monkeypatch.setattr("orglens.cli._launch", fail_if_called)
    monkeypatch.setattr("orglens.cli.EVENTS_DIR", tmp_path / "events")

    result = CliRunner().invoke(cli, ["start", "orglens"])
    # Two homes and no --home: the command says which are available rather
    # than picking one and being wrong quietly.
    assert "--home" in result.output


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
