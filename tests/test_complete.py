"""What the shell is offered after `orglens <verb> <tab>`.

Every completer reads a cache, never the tree: a sweep would put a
multi-second pause on a keystroke. The tests that matter here are the ones
that pin that down — no snapshot means no completions and no wait.
"""

from orglens import complete

SNAPSHOT = """# Topology Snapshot

**Kinds:** client (`clients/*`), project (`projects/*`), experiment (`expt-*`)

**Documents:** plan (`plans/*.md`), spec (`specs/*.md`)

## Projects

### orglens — ` line in a unit's documents

Homes: `/x/orglens`

### cribsheet — P1 sourcing done

## Clients

### freightify
"""


def _snapshot(monkeypatch, text):
    monkeypatch.setattr(complete, "_snapshot_text", lambda: text)


def test_unit_names_come_from_the_snapshot_with_their_status(monkeypatch):
    _snapshot(monkeypatch, SNAPSHOT)
    assert complete.unit_names() == [
        ("cribsheet", "P1 sourcing done"),
        ("freightify", ""),
        ("orglens", "` line in a unit's documents"),
    ]


def test_kinds_are_the_grammars_words_entity_and_document_alike(monkeypatch):
    _snapshot(monkeypatch, SNAPSHOT)
    assert complete.kind_names() == [
        "client", "experiment", "plan", "project", "spec",
    ]


def test_no_snapshot_completes_to_nothing_rather_than_a_wait(monkeypatch):
    """The whole point of reading the cache. A completer that fell back to
    sweeping the roots would hang the prompt for seconds."""
    _snapshot(monkeypatch, "")
    assert complete.unit_names() == [] and complete.kind_names() == []


def test_an_unreadable_config_or_snapshot_is_not_an_error(monkeypatch):
    """A completer that raises takes the shell's prompt with it, so the
    read is guarded at its source rather than at each caller."""
    def boom():
        raise OSError("gone")

    monkeypatch.setattr("orglens.config.Config.load", staticmethod(boom))
    assert complete.unit_names() == [] and complete.kind_names() == []


def test_matching_is_by_prefix_and_ignores_case(monkeypatch):
    _snapshot(monkeypatch, SNAPSHOT)
    assert [i.value for i in complete.units(None, None, "cr")] == ["cribsheet"]
    assert [i.value for i in complete.units(None, None, "ORG")] == ["orglens"]
    assert [i.value for i in complete.units(None, None, "zz")] == []


def test_the_status_line_rides_along_as_the_hint(monkeypatch):
    _snapshot(monkeypatch, SNAPSHOT)
    assert complete.units(None, None, "cribsheet")[0].help == "P1 sourcing done"


def test_session_ids_are_capped(monkeypatch):
    rows = [{"id": f"id-{i}", "name": f"n{i}"} for i in range(complete.SESSION_CAP + 50)]
    monkeypatch.setattr("orglens.sessions.run_scad", lambda argv: rows)
    assert len(complete.session_ids()) == complete.SESSION_CAP


def test_no_scad_is_no_sessions_not_a_failure(monkeypatch):
    monkeypatch.setattr("orglens.sessions.run_scad", lambda argv: [])
    assert complete.session_ids() == []


def test_resume_offers_units_and_sessions_both(monkeypatch):
    _snapshot(monkeypatch, SNAPSHOT)
    monkeypatch.setattr("orglens.sessions.run_scad",
                        lambda argv: [{"id": "orglens-session-id", "name": "x"}])
    values = [i.value for i in complete.units_or_sessions(None, None, "orglens")]
    assert values == ["orglens", "orglens-session-id"]
