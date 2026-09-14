"""Which units a session belongs to, defined once."""

from pathlib import Path

from orglens import events
from orglens.declaration import MARKER
from orglens.grammar import Grammar
from orglens.sessions import all_sessions, for_unit, unattributed
from orglens.units import Registry
from tests.conftest import export_row, fake_scad


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


def _sessions(monkeypatch, registry, rows, tmp_path):
    monkeypatch.setattr("orglens.sessions.run_scad", fake_scad(rows))
    return all_sessions(registry, tmp_path / "events")


def test_a_session_inside_one_home_belongs_to_that_unit_by_containment(tmp_path, monkeypatch):
    registry = _tree(tmp_path, {"alpha": ["alpha-repo"]})
    [s] = _sessions(monkeypatch, registry, [export_row("s1", str(tmp_path / "code" / "alpha-repo" / "src"))], tmp_path)
    assert s.units == frozenset({"alpha"})
    assert s.how == "containment"


def test_a_session_in_a_shared_home_belongs_to_every_unit_sharing_it(tmp_path, monkeypatch):
    registry = _tree(tmp_path, {"alpha": ["shared"], "beta": ["shared"]})
    [s] = _sessions(monkeypatch, registry, [export_row("s1", str(tmp_path / "code" / "shared"))], tmp_path)
    assert s.units == frozenset({"alpha", "beta"})


def test_an_attribution_wins_over_containment_and_narrows_to_one_unit(tmp_path, monkeypatch):
    registry = _tree(tmp_path, {"alpha": ["shared"], "beta": ["shared"]})
    events.append(events.Event("attributed", "beta", "s1", 100, "m"), root=tmp_path / "events")
    [s] = _sessions(monkeypatch, registry, [export_row("s1", str(tmp_path / "code" / "shared"))], tmp_path)
    assert s.units == frozenset({"beta"})
    assert s.how == "attributed"


def test_a_session_outside_every_home_belongs_to_no_unit(tmp_path, monkeypatch):
    registry = _tree(tmp_path, {"alpha": ["alpha-repo"]})
    [s] = _sessions(monkeypatch, registry, [export_row("s1", str(tmp_path / "elsewhere"))], tmp_path)
    assert s.units == frozenset()
    assert s.how is None
    assert unattributed([s]) == [s]
    assert for_unit([s], "alpha") == []


def test_a_container_cwd_matches_the_home_it_was_mounted_from(tmp_path, monkeypatch):
    # scad mounts a home at /workspace/<repo>; a session that ran there
    # records that path, not the host one.
    registry = _tree(tmp_path, {"alpha": ["alpha-repo/docs"]})
    [s] = _sessions(monkeypatch, registry, [export_row("s1", "/workspace/alpha-repo/docs/plans")], tmp_path)
    assert s.units == frozenset({"alpha"})


def test_only_main_sessions_are_asked_for(tmp_path, monkeypatch):
    # Subagents and workflow agents belong to their parent. The export is
    # asked with `--kind main`; this pins the argv, since a missing flag
    # returns every kind.
    from orglens import sessions
    seen = []
    def run(argv):
        seen.append(argv); return []
    monkeypatch.setattr(sessions, "run_scad", run)
    registry = _tree(tmp_path, {"alpha": ["alpha-repo"]})
    all_sessions(registry, tmp_path / "events")
    [argv] = seen
    assert argv[:2] == ["session", "ls"] and "--kind" in argv and argv[argv.index("--kind") + 1] == "main"


def test_zero_turn_rows_are_included_a_launched_session_has_none_yet(tmp_path, monkeypatch):
    registry = _tree(tmp_path, {"alpha": ["alpha-repo"]})
    cwd = str(tmp_path / "code" / "alpha-repo")
    got = _sessions(monkeypatch, registry, [
        export_row("real", cwd, n_turns=3), export_row("skeleton", cwd, n_turns=0, grade="skeleton"),
    ], tmp_path)
    assert {s.id: s.turns for s in got} == {"real": 3, "skeleton": 0}


def test_no_scad_yields_no_sessions_not_an_error(tmp_path, monkeypatch):
    registry = _tree(tmp_path, {"alpha": ["alpha-repo"]})
    monkeypatch.setattr("orglens.sessions.run_scad", lambda argv: [])
    assert all_sessions(registry, tmp_path / "events") == []


def test_newest_first(tmp_path, monkeypatch):
    registry = _tree(tmp_path, {"alpha": ["alpha-repo"]})
    cwd = str(tmp_path / "code" / "alpha-repo")
    got = _sessions(monkeypatch, registry, [
        export_row("old", cwd, started=1000, ended=2000),
        export_row("new", cwd, agent="codex", started=5000),
    ], tmp_path)
    assert [s.id for s in got] == ["new", "old"]


def test_a_running_session_is_live_and_named_from_the_registry(tmp_path, monkeypatch):
    registry = _tree(tmp_path, {"alpha": ["alpha-repo"]})
    cwd = str(tmp_path / "code" / "alpha-repo")
    [s] = _sessions(monkeypatch, registry, [
        export_row("s1", cwd, n_turns=0, live={"pid": 1, "name": "what-i-called-it", "status": "busy", "waiting_for": ""}),
    ], tmp_path)
    assert s.live is True
    assert s.label == "what-i-called-it"


def test_the_index_name_is_used_when_nothing_is_live(tmp_path, monkeypatch):
    registry = _tree(tmp_path, {"alpha": ["alpha-repo"]})
    cwd = str(tmp_path / "code" / "alpha-repo")
    [s] = _sessions(monkeypatch, registry, [export_row("s1", cwd, name="", title="a title")], tmp_path)
    assert s.live is False and s.label == "a title"


def test_last_turn_and_needs_ride_along(tmp_path, monkeypatch):
    registry = _tree(tmp_path, {"alpha": ["alpha-repo"]})
    cwd = str(tmp_path / "code" / "alpha-repo")
    [s] = _sessions(monkeypatch, registry, [
        export_row("s1", cwd, last_turn={"ts": 1700000000000, "role": "user", "text": "hi"}, needs="which way?"),
    ], tmp_path)
    assert s.last_turn == {"ts": 1700000000000, "role": "user", "text": "hi"}
    assert s.needs == "which way?"


def test_a_cwd_recorded_through_a_symlinked_root_still_matches(tmp_path, monkeypatch):
    # `~/Dropbox` is a symlink to `~/Library/CloudStorage/Dropbox`; most
    # sessions record the resolved form, some the symlink form. A home
    # reached through a root given as the symlink matches both.
    real = tmp_path / "real"
    (real / "alpha-repo").mkdir(parents=True)
    link = tmp_path / "via-link"
    link.symlink_to(real)
    _unit(tmp_path, "alpha", ["alpha-repo"])
    grammar = Grammar.from_yaml(
        Path(__file__).parent.parent / "orglens" / "grammars" / "default.yaml"
    )
    registry = Registry([tmp_path / "docs", link], grammar)
    got = {s.id: s.units for s in _sessions(monkeypatch, registry, [
        export_row("s-resolved", str(real / "alpha-repo" / "src")),
        export_row("s-linked", str(link / "alpha-repo" / "src")),
    ], tmp_path)}
    assert got == {"s-resolved": frozenset({"alpha"}), "s-linked": frozenset({"alpha"})}
