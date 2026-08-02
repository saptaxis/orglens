from __future__ import annotations

from pathlib import Path

from orglens.workflow.blocking import check


def write(tmp_path: Path, *lines: str) -> Path:
    (tmp_path / "runs.jsonl").write_text("".join(line + "\n" for line in lines))
    return tmp_path


def test_an_empty_packet_is_not_blocked(tmp_path: Path):
    assert check(tmp_path) is None


def test_an_outstanding_question_blocks(tmp_path: Path):
    write(
        tmp_path,
        '{"type":"needs_human","event_id":"n1","node":"critique",'
        '"raised_by":"node","question":"does finding 3 count?","at":"t"}',
    )
    block = check(tmp_path)
    assert block is not None
    assert block.node == "critique"
    assert block.raised_by == "node"
    assert "finding 3" in block.question


def test_resolving_unblocks(tmp_path: Path):
    write(
        tmp_path,
        '{"type":"needs_human","event_id":"n1","node":"critique",'
        '"raised_by":"node","question":"q","at":"t"}',
        '{"type":"human_resolved","event_id":"r1","resolves":"n1",'
        '"note":"yes, keep it","at":"t"}',
    )
    assert check(tmp_path) is None


def test_a_declared_review_blocks_the_same_way(tmp_path: Path):
    """human_review: true and a stuck node land in the same place."""
    write(
        tmp_path,
        '{"type":"node_completed","event_id":"c1","node":"critique","at":"t"}',
        '{"type":"needs_human","event_id":"n1","node":"critique",'
        '"raised_by":"declaration","question":"ratify the findings","at":"t"}',
    )
    block = check(tmp_path)
    assert block.raised_by == "declaration"


def test_a_second_question_blocks_again_after_the_first_is_resolved(tmp_path: Path):
    write(
        tmp_path,
        '{"type":"needs_human","event_id":"n1","node":"critique","question":"a","at":"t"}',
        '{"type":"human_resolved","event_id":"r1","resolves":"n1","note":"ok","at":"t"}',
        '{"type":"needs_human","event_id":"n2","node":"revise","question":"b","at":"t"}',
    )
    block = check(tmp_path)
    assert block.node == "revise"
    assert block.question == "b"
