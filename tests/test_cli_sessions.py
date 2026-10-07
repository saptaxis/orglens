"""`orglens sessions`, `resume` and `attribute`: what a unit's sessions
look like from the command line, and the two things you can do with one.

scad is never run here. `resume` is asserted on the argv handed to it;
`attribute` on the event written.
"""

import time

from click.testing import CliRunner

from orglens import events
from orglens.cli import cli
from tests.conftest import export_row, fake_scad


def _row(id, cwd, **extra):
    base = {"n_turns": 4, "started": 1000_000}
    base.update(extra)
    return export_row(id, cwd, **base)


def _setup(tmp_path, monkeypatch, two_root_tree, rows):
    """A fake scad export, an empty event log, and the two-root tree's config.
    `orglens`'s code home is `code/orglens`."""
    monkeypatch.setattr("orglens.sessions.run_scad", fake_scad(rows))
    monkeypatch.setattr("orglens.cli.EVENTS_DIR", tmp_path / "events")
    return tmp_path / "code" / "orglens"


class TestSessions:
    def test_a_units_sessions_are_listed_newest_first_with_how(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        home = _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("aaaa1111-old", str(home_ := tmp_path / "code" / "orglens"),
                 ended=2000_000, name="first"),
            _row("bbbb2222-new", str(home_), ended=9000_000, name="second",
                 outcome="awaiting-user", agent="codex"),
        ])
        result = CliRunner().invoke(cli, ["sessions", "orglens"])
        assert result.exit_code == 0, result.output
        lines = [l for l in result.output.splitlines() if l.strip()]
        assert "bbbb2222" in lines[0] and "second" in lines[0]
        assert "aaaa1111" in lines[1] and "first" in lines[1]
        assert "containment" in lines[0]
        assert "codex" in lines[0]
        assert "resumable" in lines[0] and "resumable" not in lines[1]

    def test_an_attributed_session_says_so(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("cccc3333-far", str(tmp_path / "elsewhere"), name="far away"),
        ])
        events.append(events.Event("attributed", "orglens", "cccc3333-far", 5, "m"),
                      root=tmp_path / "events")
        result = CliRunner().invoke(cli, ["sessions", "orglens"])
        assert "cccc3333" in result.output and "attributed" in result.output

    def test_zero_turn_rows_are_hidden_unless_all(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("dddd4444-real", str(home)),
            _row("eeee5555-skel", str(home), n_turns=0, grade="skeleton"),
        ])
        default = CliRunner().invoke(cli, ["sessions", "orglens"]).output
        assert "dddd4444" in default and "eeee5555" not in default
        everything = CliRunner().invoke(cli, ["sessions", "orglens", "--all"]).output
        assert "eeee5555" in everything

    def test_no_argument_groups_by_unit_and_ends_with_unattributed(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("ffff6666-mine", str(home), name="mine"),
            _row("0000aaaa-none", str(tmp_path / "nowhere"), name="nobody's"),
        ])
        out = CliRunner().invoke(cli, ["sessions"]).output
        assert out.index("orglens") < out.index("ffff6666") < out.index("unattributed") < out.index("0000aaaa")

    def test_none_lists_only_the_unattributed(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("ffff6666-mine", str(home)),
            _row("0000aaaa-none", str(tmp_path / "nowhere")),
        ])
        out = CliRunner().invoke(cli, ["sessions", "--none"]).output
        assert "0000aaaa" in out and "ffff6666" not in out

    def test_unattributed_rows_carry_where_and_what_was_last_said(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("0000aaaa-none", str(tmp_path / "somewhere" / "deep"), name="stray",
                 last_turn={"ts": 1, "role": "user", "text": "fix the login bug next"}),
        ])
        out = CliRunner().invoke(cli, ["sessions", "--none"]).output
        assert "somewhere/deep" in out
        assert "fix the login bug next" in out

    def test_two_ids_sharing_eight_characters_are_told_apart(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("019f7f9d-f67f-7c01-b8bb-d945811b5d1a", str(home), agent="codex"),
            _row("019f7f9d-09a8-7df3-a730-74a15cb4a0d1", str(home), agent="codex"),
        ])
        out = CliRunner().invoke(cli, ["sessions", "orglens"]).output
        assert "019f7f9d-f" in out and "019f7f9d-0" in out

    def test_a_unit_with_no_sessions_says_so(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [])
        result = CliRunner().invoke(cli, ["sessions", "orglens"])
        assert result.exit_code == 0
        assert "no sessions" in result.output


    def test_a_running_session_is_listed_first_even_with_no_turns(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("dddd4444-done", str(home), ended=9000_000),
            _row("eeee5555-live", str(home), n_turns=0, started=None,
                 live={"pid": 1, "name": None, "status": "busy", "waiting_for": ""}),
        ])

        lines = [l for l in CliRunner().invoke(cli, ["sessions", "orglens"]).output.splitlines() if l.strip()]
        assert "eeee5555" in lines[0] and "live" in lines[0]
        assert "dddd4444" in lines[1]


class TestResume:
    def test_a_session_id_is_handed_to_scad(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [_row("abcd1234-full-id", str(home))])
        seen = []
        monkeypatch.setattr("orglens.cli._scad", lambda argv: seen.append(argv) or 0)

        result = CliRunner().invoke(cli, ["resume", "abcd1234"])
        assert result.exit_code == 0, result.output
        assert seen == [["session", "resume", "abcd1234-full-id"]]

    def test_print_passes_through(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [_row("abcd1234-full-id", str(home))])
        seen = []
        monkeypatch.setattr("orglens.cli._scad", lambda argv: seen.append(argv) or 0)

        CliRunner().invoke(cli, ["resume", "abcd1234", "--print"])
        assert seen == [["session", "resume", "abcd1234-full-id", "--print"]]

    def test_a_unit_name_resumes_its_newest_session_whatever_its_outcome(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        """'Open' is read off the last turn, so it filtered out the sessions
        most worth resuming. The newest stopped session is the one."""
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("1111-newest-but-done", str(home), ended=9000_000, outcome="done"),
            _row("2222-open-older", str(home), ended=5000_000, outcome="awaiting-user"),
        ])
        seen = []
        monkeypatch.setattr("orglens.cli._scad", lambda argv: seen.append(argv) or 0)

        result = CliRunner().invoke(cli, ["resume", "orglens"])
        assert result.exit_code == 0, result.output
        assert seen == [["session", "resume", "1111-newest-but-done"]]

    def test_a_session_just_launched_is_the_one_resumed(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        """Observed 2026-09-27: a live session with no turns yet has no
        outcome, so it was passed over for an older one."""
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("1111-just-launched", str(home), n_turns=0, started=9000_000,
                 live={"pid": 7, "name": None, "status": "idle", "waiting_for": ""}),
            _row("2222-stopped", str(home), ended=5000_000, outcome="awaiting-user"),
        ])
        seen = []
        monkeypatch.setattr("orglens.cli._scad", lambda argv: seen.append(argv) or 0)

        result = CliRunner().invoke(cli, ["resume", "orglens"])
        assert result.exit_code == 0, result.output
        assert seen == [["session", "resume", "1111-just-launched"]]

    def test_a_running_session_goes_first_and_to_scad(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        """scad attaches to a running session's pane, or refuses when it
        cannot name one; a stopped session newer by its clock does not win."""
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("1111-stopped-newer", str(home), ended=9000_000),
            _row("2222-running", str(home), started=1000_000,
                 live={"pid": 7, "name": None, "status": "busy", "waiting_for": ""}),
        ])
        seen = []
        monkeypatch.setattr("orglens.cli._scad", lambda argv: seen.append(argv) or 0)

        CliRunner().invoke(cli, ["resume", "orglens"])
        assert seen == [["session", "resume", "2222-running"]]

    def test_the_others_are_named_in_one_line(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("1111-newest", str(home), ended=9000_000, name="orglens-a-oct06"),
            _row("2222-older", str(home), ended=5000_000, name="orglens-b-oct05"),
            _row("3333-oldest", str(home), ended=1000_000),
        ])
        monkeypatch.setattr("orglens.cli._scad", lambda argv: 0)

        out = CliRunner().invoke(cli, ["resume", "orglens"]).output
        others = [l for l in out.splitlines() if "orglens-b-oct05" in l]
        assert len(others) == 1
        assert "3333" in others[0] and "orglens resume orglens" in others[0]

    def test_a_unit_with_no_sessions_says_so(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [])
        seen = []
        monkeypatch.setattr("orglens.cli._scad", lambda argv: seen.append(argv) or 0)

        result = CliRunner().invoke(cli, ["resume", "orglens"])
        assert result.exit_code == 1
        assert seen == []
        assert "no sessions" in result.output

    def test_a_name_resumes_that_session(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("1111-newest", str(home), ended=9000_000, name="orglens-a-oct06"),
            _row("2222-named", str(home), ended=5000_000, name="orglens-b-oct05"),
        ])
        seen = []
        monkeypatch.setattr("orglens.cli._scad", lambda argv: seen.append(argv) or 0)

        result = CliRunner().invoke(cli, ["resume", "orglens", "orglens-b-oct05"])
        assert result.exit_code == 0, result.output
        assert seen == [["session", "resume", "2222-named"]]

    def test_two_sessions_with_one_name_resume_the_newest(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("1111-newer", str(home), ended=9000_000, name="twice"),
            _row("2222-older", str(home), ended=5000_000, name="twice"),
        ])
        seen = []
        monkeypatch.setattr("orglens.cli._scad", lambda argv: seen.append(argv) or 0)

        CliRunner().invoke(cli, ["resume", "orglens", "twice"])
        assert seen == [["session", "resume", "1111-newer"]]

    def test_an_unknown_name_lists_the_units_names(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("1111-named", str(home), ended=9000_000, name="orglens-a-oct06"),
        ])
        seen = []
        monkeypatch.setattr("orglens.cli._scad", lambda argv: seen.append(argv) or 0)

        result = CliRunner().invoke(cli, ["resume", "orglens", "nope"])
        assert result.exit_code == 1
        assert seen == []
        assert "nope" in result.output and "orglens-a-oct06" in result.output

    def test_a_name_after_a_session_id_is_refused(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [_row("abcd1234-full-id", str(home))])
        seen = []
        monkeypatch.setattr("orglens.cli._scad", lambda argv: seen.append(argv) or 0)

        result = CliRunner().invoke(cli, ["resume", "abcd1234", "some-name"])
        assert result.exit_code != 0
        assert seen == []

    def test_an_ambiguous_prefix_names_the_matches(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("abcd-one", str(home)), _row("abcd-two", str(home)),
        ])
        seen = []
        monkeypatch.setattr("orglens.cli._scad", lambda argv: seen.append(argv) or 0)

        result = CliRunner().invoke(cli, ["resume", "abcd"])
        assert result.exit_code == 1
        assert "abcd-one" in result.output and "abcd-two" in result.output
        assert seen == []

    def test_an_unknown_argument_is_neither(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [])
        result = CliRunner().invoke(cli, ["resume", "zzzz"])
        assert result.exit_code == 1
        assert "zzzz" in result.output


class TestAttribute:
    def test_writes_the_event_start_writes(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("abcd1234-far", str(tmp_path / "elsewhere")),
        ])
        result = CliRunner().invoke(cli, ["attribute", "abcd1234", "orglens"])
        assert result.exit_code == 0, result.output
        [event] = events.read_all(root=tmp_path / "events")
        assert (event.kind, event.unit, event.session) == ("attributed", "orglens", "abcd1234-far")
        assert "abcd1234-far" in result.output and "orglens" in result.output

    def test_the_session_then_belongs_to_that_unit_alone(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("abcd1234-far", str(tmp_path / "elsewhere")),
        ])
        CliRunner().invoke(cli, ["attribute", "abcd1234", "orglens"])
        out = CliRunner().invoke(cli, ["sessions", "orglens"]).output
        assert "abcd1234" in out and "attributed" in out

    def test_an_unknown_session_is_refused(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [])
        result = CliRunner().invoke(cli, ["attribute", "nope", "orglens"])
        assert result.exit_code == 1
        assert events.read_all(root=tmp_path / "events") == []

    def test_an_unknown_unit_is_refused(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("abcd1234-far", str(tmp_path / "elsewhere")),
        ])
        result = CliRunner().invoke(cli, ["attribute", "abcd1234", "no-such-unit"])
        assert result.exit_code == 1
        assert events.read_all(root=tmp_path / "events") == []


class TestTriage:
    """Deciding the unclaimed pile: at a prompt, or over a file. Neither
    proposes a unit — the person assigns, the tool records."""

    def test_a_dismissed_session_leaves_the_unclaimed_pile(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("0000aaaa-none", str(tmp_path / "nowhere")),
        ])
        run = CliRunner()
        assert "0000aaaa" in run.invoke(cli, ["sessions", "--none"]).output
        run.invoke(cli, ["dismiss", "0000aaaa", "--why", "scratch"])
        assert "0000aaaa" not in run.invoke(cli, ["sessions", "--none"]).output

    def test_attributing_a_dismissed_session_brings_it_back(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("0000aaaa-none", str(tmp_path / "nowhere")),
        ])
        run = CliRunner()
        run.invoke(cli, ["dismiss", "0000aaaa"])
        run.invoke(cli, ["attribute", "0000aaaa", "orglens"])
        assert "0000aaaa" in run.invoke(cli, ["sessions", "orglens"]).output

    def test_why_is_recorded_on_the_attribution(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("0000aaaa-none", str(tmp_path / "nowhere")),
        ])
        CliRunner().invoke(cli, ["attribute", "0000aaaa", "orglens",
                                 "--why", "the release branch"])
        written = events.read_all(root=tmp_path / "events")
        assert [(e.unit, e.why) for e in written] == [("orglens", "the release branch")]

    def test_triage_takes_a_unit_a_skip_and_a_dismissal_in_turn(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("0000aaaa-none", str(tmp_path / "nowhere"), started=3000_000),
            _row("0000bbbb-none", str(tmp_path / "nowhere"), started=2000_000),
            _row("0000cccc-none", str(tmp_path / "nowhere"), started=1000_000),
        ])
        # newest first: attribute, skip, dismiss.
        answers = "orglens\nbecause\ns\nd\nnever work\n"
        out = CliRunner().invoke(cli, ["sessions", "--triage", "--one-by-one"],
                                 input=answers).output
        assert "3 unclaimed" in out
        written = {e.session[:8]: (e.kind, e.why) for e in
                   events.read_all(root=tmp_path / "events")}
        assert written == {"0000aaaa": ("attributed", "because"),
                           "0000cccc": ("dismissed", "never work")}

    def test_triage_never_proposes_a_unit(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        """A session at a shared root could be any of the units under it;
        guessing from its title is the containment mistake one layer up."""
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("0000aaaa-none", str(tmp_path / "nowhere"), name="orglens work"),
        ])
        out = CliRunner().invoke(cli, ["sessions", "--triage", "--one-by-one"],
                                 input="q\n").output
        assert "stopped." in out
        assert events.read_all(root=tmp_path / "events") == []

    def test_an_unknown_unit_is_refused_not_recorded(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("0000aaaa-none", str(tmp_path / "nowhere")),
        ])
        CliRunner().invoke(cli, ["sessions", "--triage", "--one-by-one"],
                           input="no-such-unit\nq\n")
        assert events.read_all(root=tmp_path / "events") == []

    def test_json_rows_carry_an_empty_unit_to_fill_in(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        import json
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("0000aaaa-none", str(tmp_path / "nowhere")),
        ])
        rows = json.loads(CliRunner().invoke(
            cli, ["sessions", "--none", "--json"]).output)
        assert [r["unit"] for r in rows] == [""]
        assert rows[0]["id"].startswith("0000aaaa")

    def test_from_file_applies_the_units_written_into_it(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        import json
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("0000aaaa-none", str(tmp_path / "nowhere")),
            _row("0000bbbb-none", str(tmp_path / "nowhere")),
            _row("0000cccc-none", str(tmp_path / "nowhere")),
        ])
        edited = tmp_path / "pile.json"
        edited.write_text(json.dumps([
            {"id": "0000aaaa-none", "unit": "orglens", "why": "mine"},
            {"id": "0000bbbb-none", "unit": "d", "why": "scratch"},
            {"id": "0000cccc-none", "unit": ""},
        ]))
        res = CliRunner().invoke(cli, ["sessions", "--from", str(edited)])
        assert res.exception is None, res.exception
        out = res.output
        assert "2 decided, 1 left alone" in out
        written = {e.session[:8]: e.kind for e in
                   events.read_all(root=tmp_path / "events")}
        assert written == {"0000aaaa": "attributed", "0000bbbb": "dismissed"}


class TestHeldTwice:
    """A session id with two live processes on it. scad reports the other
    holders; orglens is the surface that would otherwise open a third."""

    def _held(self, tmp_path, monkeypatch, two_root_tree):
        home = tmp_path / "code" / "orglens"
        return _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("abcd1234-full-id", str(home), live={
                "pid": 1, "name": "mine", "status": "idle", "waiting_for": "",
                "also_held_by": [{"pid": 2, "name": "older",
                                  "pane": "scad-cl-1128:0.0"}]}),
        ])

    def test_resume_says_where_the_other_process_is(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        self._held(tmp_path, monkeypatch, two_root_tree)
        monkeypatch.setattr("orglens.cli._scad", lambda argv: 0)
        out = CliRunner().invoke(cli, ["resume", "abcd1234"]).output
        assert "scad-cl-1128:0.0" in out and "pid 2" in out

    def test_check_reports_it_and_does_not_gate(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        self._held(tmp_path, monkeypatch, two_root_tree)
        result = CliRunner().invoke(cli, ["check"])
        assert "more than one process" in result.output
        assert result.exit_code == 0

    def test_a_single_holder_is_not_reported(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("abcd1234-full-id", str(home), live={
                "pid": 1, "name": "mine", "status": "idle",
                "waiting_for": "", "also_held_by": []}),
        ])
        assert "more than one process" not in CliRunner().invoke(cli, ["check"]).output


class TestResumePrompt:
    def test_a_prompt_goes_to_scad_session_send(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        """Not a terminal to type in: the turn is delivered to the open pane.
        orglens builds no tmux transport of its own."""
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("abcd1234-full-id", str(home)),
        ])
        seen = []
        monkeypatch.setattr("orglens.cli._scad", lambda argv: seen.append(argv) or 0)
        CliRunner().invoke(cli, ["resume", "abcd1234", "--prompt", "carry on"])
        assert seen == [["session", "send", "abcd1234-full-id", "carry on"]]


class TestTriageInGroups:
    """One decision per directory instead of one per session. Measured
    2026-09-25: 201 unclaimed and six directories held ~95 of them."""

    def _three_dirs(self, tmp_path, monkeypatch, two_root_tree):
        return _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("0000aaaa-none", str(tmp_path / "scratch" / "one"), started=5000_000),
            _row("0000bbbb-none", str(tmp_path / "scratch" / "two"), started=4000_000),
            _row("0000cccc-none", str(tmp_path / "scratch" / "three"), started=3000_000),
            _row("0000dddd-none", str(tmp_path / "elsewhere" / "x"), started=2000_000),
        ])

    def test_groups_are_counted_by_the_directory_above_the_cwd(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        self._three_dirs(tmp_path, monkeypatch, two_root_tree)
        out = CliRunner().invoke(cli, ["sessions", "--none", "--groups"]).output
        assert "4 unclaimed in 2 directories" in out
        assert "3" in out.split("scratch")[0].splitlines()[-1]

    def test_one_answer_decides_the_whole_group(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        self._three_dirs(tmp_path, monkeypatch, two_root_tree)
        # biggest group first: three in scratch/ -> orglens; then elsewhere -> dismiss
        out = CliRunner().invoke(cli, ["sessions", "--triage"],
                                 input="orglens\nmine\nd\nscratch\n").output
        assert "attributed 3 sessions to orglens" in out
        written = {e.session[:8]: (e.kind, e.why) for e in
                   events.read_all(root=tmp_path / "events")}
        assert written == {
            "0000aaaa": ("attributed", "mine"),
            "0000bbbb": ("attributed", "mine"),
            "0000cccc": ("attributed", "mine"),
            "0000dddd": ("dismissed", "scratch"),
        }

    def test_each_falls_through_to_one_session_at_a_time(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        self._three_dirs(tmp_path, monkeypatch, two_root_tree)
        CliRunner().invoke(cli, ["sessions", "--triage"],
                           input="e\norglens\n\ns\ns\nq\n")
        written = {e.session[:8]: e.kind for e in
                   events.read_all(root=tmp_path / "events")}
        assert written == {"0000aaaa": "attributed"}

    def test_dismiss_under_a_path_clears_a_whole_tree(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        self._three_dirs(tmp_path, monkeypatch, two_root_tree)
        out = CliRunner().invoke(cli, ["dismiss", "--under",
                                       str(tmp_path / "scratch"), "--why", "tmp"]).output
        assert "dismissed 3 sessions" in out
        assert "0000dddd" in CliRunner().invoke(cli, ["sessions", "--none"]).output

    def test_dismiss_under_leaves_an_attributed_session_alone(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        """A path can contain a unit's home; dismissing what someone claimed
        on purpose is not what this is for."""
        self._three_dirs(tmp_path, monkeypatch, two_root_tree)
        run = CliRunner()
        run.invoke(cli, ["attribute", "0000bbbb", "orglens"])
        run.invoke(cli, ["dismiss", "--under", str(tmp_path / "scratch")])
        assert "0000bbbb" in run.invoke(cli, ["sessions", "orglens"]).output

    def test_why_is_shown_on_the_row_it_was_written_about(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        """A field the person is asked to fill and never shown again is the
        write-only defect one layer down."""
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("0000aaaa-none", str(tmp_path / "nowhere"),
                 last_turn={"ts": 1, "role": "user", "text": "the last thing said"}),
        ])
        run = CliRunner()
        run.invoke(cli, ["attribute", "0000aaaa", "orglens", "--why", "the release branch"])
        assert "why: the release branch" in run.invoke(cli, ["sessions", "orglens"]).output

        # On a dismissed row it outranks the last turn, which is only the
        # newest thing said rather than something said about the session. A
        # dismissal has to stay visible, or a mistaken one is unrecoverable.
        run.invoke(cli, ["dismiss", "0000aaaa", "--why", "actually nobody's"])
        out = run.invoke(cli, ["sessions", "--dismissed"]).output
        assert "why: actually nobody's" in out and "the last thing said" not in out


class TestMemos:
    """scad 0.9.0 refuses every memo command until a machine's store is
    moved, and says what to run. That has to reach the person."""

    MOVE = "Error: memos moved to ~/.scad/memos. Run: mv ~/.scad/notes ~/.scad/memos"

    def _refuse(self, monkeypatch):
        from orglens import sessions

        def refuse(argv):
            raise sessions.ScadFailed(self.MOVE)
        monkeypatch.setattr("orglens.sessions.run_scad_or_say", refuse)

    def test_memos_lists_what_was_written_about_a_unit(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [])
        monkeypatch.setattr("orglens.sessions.run_scad_or_say", fake_scad(memos=[
            {"session_id": "x", "topic": "the-topic", "title": "a memo about it",
             "ts": "2026-10-01T00:00:00", "project": "orglens", "tags": [], "entities": []},
        ]))
        result = CliRunner().invoke(cli, ["memos", "orglens"])
        assert result.exit_code == 0, result.output
        assert "the-topic" in result.output and "a memo about it" in result.output

    def test_a_refusal_is_shown_not_an_empty_list(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [])
        self._refuse(monkeypatch)
        result = CliRunner().invoke(cli, ["memos", "orglens"])
        assert result.exit_code == 1
        assert "mv ~/.scad/notes ~/.scad/memos" in result.output
        assert "no memos" not in result.output

    def test_status_says_the_refusal_once_and_goes_on(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [])
        self._refuse(monkeypatch)
        result = CliRunner().invoke(cli, ["status"])
        assert result.exit_code == 0, result.output
        assert result.output.count("mv ~/.scad/notes ~/.scad/memos") == 1

    def test_notes_is_no_longer_a_command(self, two_root_tree_config):
        assert CliRunner().invoke(cli, ["notes"]).exit_code != 0


#: The real call, taken before the autouse fixture stands it in.
from orglens import sessions as _sessions
OR_SAY = _sessions.run_scad_or_say


def test_scads_own_words_come_back_when_it_refuses(monkeypatch):
    import subprocess as sp
    import pytest
    monkeypatch.setattr("orglens.sessions.subprocess.run",
                        lambda argv, **k: sp.CompletedProcess(argv, 1, "", "Error: run mv a b\n"))
    with pytest.raises(_sessions.ScadFailed, match="^Error: run mv a b$"):
        OR_SAY(["memos", "ls"])


class TestStaleIndex:
    """Nothing reindexes on a timer; the commands that list or pick sessions
    say when scad's index is behind."""

    def _age(self, monkeypatch, status):
        monkeypatch.setattr("orglens.sessions.index_status", lambda: status)

    def test_an_old_index_is_said_by_sessions_resume_and_status(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [_row("abcd1234-full-id", str(home))])
        monkeypatch.setattr("orglens.cli._scad", lambda argv: 0)
        self._age(monkeypatch, {"indexed_at": "x", "age_s": 3 * 3600})
        for argv in (["sessions", "orglens"], ["resume", "abcd1234"], ["status"]):
            out = CliRunner().invoke(cli, argv).output
            assert "index is 3h old" in out and "scad reindex" in out, argv

    def test_a_fresh_index_says_nothing(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [])
        self._age(monkeypatch, {"indexed_at": "x", "age_s": 600})
        assert "reindex" not in CliRunner().invoke(cli, ["sessions", "orglens"]).output

    def test_never_indexed_is_said(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [])
        self._age(monkeypatch, {"indexed_at": None, "age_s": None})
        assert "never indexed" in CliRunner().invoke(cli, ["sessions", "orglens"]).output

    def test_an_old_scad_is_no_warning(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        _setup(tmp_path, monkeypatch, two_root_tree, [])
        self._age(monkeypatch, None)
        assert "reindex" not in CliRunner().invoke(cli, ["sessions", "orglens"]).output


INDEX_STATUS = _sessions.index_status


def test_index_status_reads_scads_json_and_tolerates_an_old_scad(monkeypatch):
    import subprocess as sp
    monkeypatch.setattr("orglens.sessions.subprocess.run", lambda argv, **k: sp.CompletedProcess(
        argv, 0, '{"indexed_at": "2026-10-07T10:53:02+05:30", "age_s": 412}', ""))
    assert INDEX_STATUS()["age_s"] == 412
    monkeypatch.setattr("orglens.sessions.subprocess.run", lambda argv, **k: sp.CompletedProcess(
        argv, 2, "", "Error: No such command 'index'."))
    assert INDEX_STATUS() is None
