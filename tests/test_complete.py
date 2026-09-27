"""What the shell is offered after `orglens <verb> <tab>`.

Every completer reads a cache, never the tree: a sweep would put a
multi-second pause on a keystroke. The tests that matter here are the ones
that pin that down — no snapshot means no completions and no wait.
"""

from orglens import complete

DATA = {
    "kinds": {"client": "clients/*", "project": "projects/*", "experiment": "expt-*"},
    "documents": {"plan": "plans/*", "spec": "specs/*"},
    "units": [
        {"name": "orglens", "status": "` line in a unit's documents"},
        {"name": "cribsheet", "status": "P1 sourcing done"},
        {"name": "freightify", "status": None},
    ],
}


def _snapshot(monkeypatch, data):
    monkeypatch.setattr(complete, "_snapshot_data", lambda: data)


def test_unit_names_come_from_the_snapshot_with_their_status(monkeypatch):
    _snapshot(monkeypatch, DATA)
    assert complete.unit_names() == [
        ("cribsheet", "P1 sourcing done"),
        ("freightify", ""),
        ("orglens", "` line in a unit's documents"),
    ]


def test_kinds_are_the_grammars_words_entity_and_document_alike(monkeypatch):
    _snapshot(monkeypatch, DATA)
    assert complete.kind_names() == [
        "client", "experiment", "plan", "project", "spec",
    ]


def test_no_snapshot_completes_to_nothing_rather_than_a_wait(monkeypatch):
    """The whole point of reading the cache. A completer that fell back to
    sweeping the roots would hang the prompt for seconds."""
    _snapshot(monkeypatch, {})
    assert complete.unit_names() == [] and complete.kind_names() == []


def test_an_unreadable_config_or_snapshot_is_not_an_error(monkeypatch):
    """A completer that raises takes the shell's prompt with it, so the
    read is guarded at its source rather than at each caller."""
    def boom():
        raise OSError("gone")

    monkeypatch.setattr("orglens.config.Config.current", staticmethod(boom))
    assert complete.unit_names() == [] and complete.kind_names() == []


def test_matching_is_by_prefix_and_ignores_case(monkeypatch):
    _snapshot(monkeypatch, DATA)
    assert [i.value for i in complete.units(None, None, "cr")] == ["cribsheet"]
    assert [i.value for i in complete.units(None, None, "ORG")] == ["orglens"]
    assert [i.value for i in complete.units(None, None, "zz")] == []


def test_the_status_line_rides_along_as_the_hint(monkeypatch):
    _snapshot(monkeypatch, DATA)
    assert complete.units(None, None, "cribsheet")[0].help == "P1 sourcing done"


def test_session_ids_are_capped(monkeypatch):
    rows = [{"id": f"id-{i}", "name": f"n{i}"} for i in range(complete.SESSION_CAP + 50)]
    monkeypatch.setattr("orglens.sessions.run_scad", lambda argv: rows)
    assert len(complete.session_ids()) == complete.SESSION_CAP


def test_no_scad_is_no_sessions_not_a_failure(monkeypatch):
    monkeypatch.setattr("orglens.sessions.run_scad", lambda argv: [])
    assert complete.session_ids() == []


def test_resume_offers_units_and_sessions_both(monkeypatch):
    _snapshot(monkeypatch, DATA)
    monkeypatch.setattr("orglens.sessions.run_scad",
                        lambda argv: [{"id": "orglens-session-id", "name": "x"}])
    values = [i.value for i in complete.units_or_sessions(None, None, "orglens")]
    assert values == ["orglens", "orglens-session-id"]


WORKFLOW = """
name: writing
nodes:
  - name: brief
    program: write-the-brief
    writes: brief.md
  - name: draft
    program: write-a-draft
    writes: draft.md
"""


def test_nodes_come_from_the_workflow_the_packet_is_bound_to(tmp_path, monkeypatch):
    """The packet is the command's own argument, so the workflow is knowable
    without asking which."""
    from orglens.workflow import session as ws

    flow = tmp_path / "WORKFLOW.yaml"
    flow.write_text(WORKFLOW)
    for program in ("write-the-brief", "write-a-draft"):
        (tmp_path / program).write_text("#!/bin/sh\n")
    packet = tmp_path / "packet"
    packet.mkdir()
    ws.bind(packet, flow)

    class Ctx:
        params = {"packet": str(packet)}

    assert [i.value for i in complete.nodes(Ctx, None, "")] == ["brief", "draft"]
    assert [i.value for i in complete.nodes(Ctx, None, "dr")] == ["draft"]
    assert complete.nodes(Ctx, None, "")[0].help == "write-the-brief"


def test_no_packet_on_the_line_is_no_nodes(tmp_path):
    """Correct rather than unhelpful: which nodes exist depends on which
    workflow, and nothing yet says which."""
    class Ctx:
        params = {}

    assert complete.nodes(Ctx, None, "") == []


def test_an_unbound_packet_is_no_nodes(tmp_path):
    packet = tmp_path / "packet"
    packet.mkdir()

    class Ctx:
        params = {"packet": str(packet)}

    assert complete.nodes(Ctx, None, "") == []


def test_packets_are_the_directories_holding_a_session_file(tmp_path, monkeypatch):
    for name in ("one", "two/deeper", "three"):
        (tmp_path / name).mkdir(parents=True)
    (tmp_path / "one" / "session.jsonl").write_text("")
    (tmp_path / "two" / "deeper" / "session.jsonl").write_text("")

    class Cfg:
        roots = [tmp_path]

    monkeypatch.setattr("orglens.config.Config.load", staticmethod(lambda: Cfg()))
    found = [i.value for i in complete.packets(None, None, "")]
    assert found == sorted([str(tmp_path / "one"), str(tmp_path / "two" / "deeper")])


def test_a_workflow_that_does_not_validate_still_completes(tmp_path):
    """The loader requires each node's program to exist; a completer must not.
    A workflow mid-edit would otherwise stop completing exactly when the node
    names are what you are reaching for."""
    from orglens.workflow import session as ws

    flow = tmp_path / "WORKFLOW.yaml"
    flow.write_text(WORKFLOW)          # programs deliberately absent
    packet = tmp_path / "packet"
    packet.mkdir()
    ws.bind(packet, flow)

    class Ctx:
        params = {"packet": str(packet)}

    assert [i.value for i in complete.nodes(Ctx, None, "")] == ["brief", "draft"]
