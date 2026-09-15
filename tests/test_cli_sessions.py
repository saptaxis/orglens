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

    def test_a_unit_name_resumes_its_newest_open_session(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row("1111-newest-but-done", str(home), ended=9000_000, outcome="done"),
            _row("2222-open-older", str(home), ended=5000_000, outcome="awaiting-user"),
            _row("3333-open-oldest", str(home), ended=1000_000, outcome="in-flight"),
        ])
        seen = []
        monkeypatch.setattr("orglens.cli._scad", lambda argv: seen.append(argv) or 0)

        result = CliRunner().invoke(cli, ["resume", "orglens"])
        assert result.exit_code == 0, result.output
        assert seen == [["session", "resume", "2222-open-older"]]

    def test_a_unit_with_nothing_open_lists_its_newest_three(
        self, tmp_path, monkeypatch, two_root_tree, two_root_tree_config
    ):
        home = tmp_path / "code" / "orglens"
        _setup(tmp_path, monkeypatch, two_root_tree, [
            _row(f"{i}{i}{i}{i}-done", str(home), ended=i * 1000_000, outcome="done")
            for i in range(1, 6)
        ])
        seen = []
        monkeypatch.setattr("orglens.cli._scad", lambda argv: seen.append(argv) or 0)

        result = CliRunner().invoke(cli, ["resume", "orglens"])
        assert result.exit_code == 1
        assert seen == []
        assert "nothing open" in result.output
        assert "5555" in result.output and "3333" in result.output and "2222" not in result.output

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
