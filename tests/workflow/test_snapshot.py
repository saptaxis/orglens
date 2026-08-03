from __future__ import annotations

from pathlib import Path

from orglens.workflow.snapshot import PacketSnapshot, read_packet


def test_an_empty_packet(tmp_path: Path):
    snap = read_packet(tmp_path)
    assert snap.files == [] and snap.runs == []


def test_a_missing_directory_is_empty_not_an_error(tmp_path: Path):
    assert read_packet(tmp_path / "nope").files == []


def test_files_are_listed_sorted(tmp_path: Path):
    for name in ("zeta.txt", "alpha.md", "mid.yaml"):
        (tmp_path / name).write_text("x")
    assert read_packet(tmp_path).files == ["alpha.md", "mid.yaml", "zeta.txt"]


def test_directories_are_not_files(tmp_path: Path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.md").write_text("x")
    assert read_packet(tmp_path).files == ["a.md"]


def test_the_snapshot_takes_no_workflow(tmp_path: Path):
    """A packet's shape does not depend on the definition."""
    import inspect

    params = list(inspect.signature(read_packet).parameters)
    assert params == ["root"]


def test_no_file_is_opened_but_run_state(tmp_path: Path):
    """The body of a deck's file is never read — not even its first line."""
    (tmp_path / "draft.md").write_text("---\npublished: yes\n---\n# Title\n")
    snap = read_packet(tmp_path)
    assert snap.files == ["draft.md"]
    assert not hasattr(snap, "frontmatter")
    assert not any("published" in str(v) for v in vars(snap).values())


def test_run_state_is_read(tmp_path: Path):
    (tmp_path / "runs.jsonl").write_text(
        '{"type":"node_completed","node":"draft","at":"t","event_id":"1"}\n'
    )
    assert read_packet(tmp_path).runs[0]["node"] == "draft"


def test_the_snapshot_has_exactly_three_fields():
    import dataclasses

    assert [f.name for f in dataclasses.fields(PacketSnapshot)] == [
        "root",
        "files",
        "runs",
    ]
