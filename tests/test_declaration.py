from pathlib import Path
from orglens.declaration import MARKER, read_marker


def test_reads_a_full_declaration(tmp_path):
    (tmp_path / MARKER).write_text(
        "home: traitful-docs/docs/projects/orglens\n"
        "unit: orglens\n"
        "kind: project\n"
        "part_of: traitful-workflow-ecosystem\n"
        "homes:\n"
        "  - orglens\n"
        "  - traitful-docs/docs/projects/orglens\n"
    )
    marker = read_marker(tmp_path)
    assert marker.unit == "orglens"
    assert marker.kind == "project"
    assert marker.part_of == "traitful-workflow-ecosystem"
    assert marker.homes == ("orglens", "traitful-docs/docs/projects/orglens")
    assert marker.home == "traitful-docs/docs/projects/orglens"
    assert marker.path == tmp_path
    assert marker.declares is True


def test_reads_an_identity_only_marker(tmp_path):
    (tmp_path / MARKER).write_text("home: world-model-ladder\n")
    marker = read_marker(tmp_path)
    assert marker.home == "world-model-ladder"
    assert marker.unit is None
    assert marker.homes == ()
    assert marker.declares is False


def test_absent_marker_is_none_not_an_error(tmp_path):
    assert read_marker(tmp_path) is None


def test_malformed_marker_is_none_not_an_error(tmp_path):
    (tmp_path / MARKER).write_text("this: [is not\n  valid yaml\n")
    assert read_marker(tmp_path) is None


def test_a_declaration_always_includes_its_own_home(tmp_path):
    (tmp_path / MARKER).write_text(
        "home: a\nunit: u\nkind: project\nhomes:\n  - b\n"
    )
    marker = read_marker(tmp_path)
    assert "a" in marker.homes


def test_a_marker_with_invalid_utf8_is_none_not_an_error(tmp_path):
    (tmp_path / MARKER).write_bytes(b"home: \xff\xfe\n")
    assert read_marker(tmp_path) is None
