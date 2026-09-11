"""Which units a session belongs to, defined once."""

from pathlib import Path

from orglens import events
from orglens.declaration import MARKER
from orglens.grammar import Grammar
from orglens.sessions import all_sessions, for_unit, unattributed
from orglens.units import Registry
from tests.conftest import scad_index


def _unit(root: Path, name: str, homes: list[str]) -> None:
    d = root / "docs" / "projects" / name
    d.mkdir(parents=True)
    (d / MARKER).write_text(
        f"unit: {name}\nkind: project\nhomes:\n" + "".join(f"  - {h}\n" for h in homes)
    )


def _tree(tmp_path, units: dict[str, list[str]]) -> Registry:
    """Units declared in a docs root; each named home created as a bare
    directory under a code root so it resolves by name."""
    code = tmp_path / "code"
    for homes in units.values():
        for h in homes:
            (code / h).mkdir(parents=True, exist_ok=True)
    for name, homes in units.items():
        _unit(tmp_path, name, homes)
    grammar = Grammar.from_yaml(
        Path(__file__).parent.parent / "orglens" / "grammars" / "default.yaml"
    )
    return Registry([tmp_path / "docs", code], grammar)


def test_a_session_inside_one_home_belongs_to_that_unit_by_containment(tmp_path):
    registry = _tree(tmp_path, {"alpha": ["alpha-repo"]})
    index = scad_index(tmp_path, [("s1", str(tmp_path / "code" / "alpha-repo" / "src"), "x")])

    [s] = all_sessions(registry, index, tmp_path / "events")
    assert s.units == frozenset({"alpha"})
    assert s.how == "containment"


def test_a_session_in_a_shared_home_belongs_to_every_unit_sharing_it(tmp_path):
    registry = _tree(tmp_path, {"alpha": ["shared"], "beta": ["shared"]})
    index = scad_index(tmp_path, [("s1", str(tmp_path / "code" / "shared"), "x")])

    [s] = all_sessions(registry, index, tmp_path / "events")
    assert s.units == frozenset({"alpha", "beta"})


def test_an_attribution_wins_over_containment_and_narrows_to_one_unit(tmp_path):
    registry = _tree(tmp_path, {"alpha": ["shared"], "beta": ["shared"]})
    index = scad_index(tmp_path, [("s1", str(tmp_path / "code" / "shared"), "x")])
    events.append(events.Event("attributed", "beta", "s1", 100, "m"), root=tmp_path / "events")

    [s] = all_sessions(registry, index, tmp_path / "events")
    assert s.units == frozenset({"beta"})
    assert s.how == "attributed"


def test_a_session_outside_every_home_belongs_to_no_unit(tmp_path):
    registry = _tree(tmp_path, {"alpha": ["alpha-repo"]})
    index = scad_index(tmp_path, [("s1", str(tmp_path / "elsewhere"), "x")])

    [s] = all_sessions(registry, index, tmp_path / "events")
    assert s.units == frozenset()
    assert s.how is None
    assert unattributed([s]) == [s]
    assert for_unit([s], "alpha") == []


def test_a_container_cwd_matches_the_home_it_was_mounted_from(tmp_path):
    # scad mounts a home at /workspace/<repo>; a session that ran there
    # records that path, not the host one.
    registry = _tree(tmp_path, {"alpha": ["alpha-repo/docs"]})
    index = scad_index(tmp_path, [("s1", "/workspace/alpha-repo/docs/plans", "x")])

    [s] = all_sessions(registry, index, tmp_path / "events")
    assert s.units == frozenset({"alpha"})


def test_subagent_rows_are_never_listed_on_their_own(tmp_path):
    registry = _tree(tmp_path, {"alpha": ["alpha-repo"]})
    cwd = str(tmp_path / "code" / "alpha-repo")
    index = scad_index(tmp_path, [
        {"id": "main1", "kind": "main", "agent": "claude", "machine": "m", "cwd": cwd,
         "n_turns": 3, "grade": "", "source": ""},
        {"id": "sub1", "kind": "subagent", "agent": "claude", "machine": "m", "cwd": cwd,
         "n_turns": 3, "grade": "", "source": ""},
        {"id": "wf1", "kind": "workflow-agent", "agent": "claude", "machine": "m", "cwd": cwd,
         "n_turns": 3, "grade": "", "source": ""},
    ])

    assert [s.id for s in all_sessions(registry, index, tmp_path / "events")] == ["main1"]


def test_zero_turn_rows_are_hidden_unless_asked_for(tmp_path):
    registry = _tree(tmp_path, {"alpha": ["alpha-repo"]})
    cwd = str(tmp_path / "code" / "alpha-repo")
    index = scad_index(tmp_path, [
        {"id": "real", "kind": "main", "agent": "claude", "machine": "m", "cwd": cwd,
         "n_turns": 3, "grade": "", "source": ""},
        {"id": "skeleton", "kind": "main", "agent": "claude", "machine": "m", "cwd": cwd,
         "n_turns": 0, "grade": "skeleton", "source": "scad-launch"},
    ])

    assert [s.id for s in all_sessions(registry, index, tmp_path / "events")] == ["real"]
    got = all_sessions(registry, index, tmp_path / "events", include_empty=True)
    assert {s.id for s in got} == {"real", "skeleton"}


def test_a_missing_index_yields_no_sessions_not_an_error(tmp_path):
    registry = _tree(tmp_path, {"alpha": ["alpha-repo"]})
    assert all_sessions(registry, tmp_path / "absent.sqlite", tmp_path / "events") == []


def test_newest_first(tmp_path):
    registry = _tree(tmp_path, {"alpha": ["alpha-repo"]})
    cwd = str(tmp_path / "code" / "alpha-repo")
    index = scad_index(tmp_path, [
        {"id": "old", "kind": "main", "agent": "claude", "machine": "m", "cwd": cwd,
         "n_turns": 1, "grade": "", "source": "", "started": 1000, "ended": 2000},
        {"id": "new", "kind": "main", "agent": "codex", "machine": "m", "cwd": cwd,
         "n_turns": 1, "grade": "", "source": "", "started": 5000},
    ])

    assert [s.id for s in all_sessions(registry, index, tmp_path / "events")] == ["new", "old"]
