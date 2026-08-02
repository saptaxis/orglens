from __future__ import annotations

from pathlib import Path

from orglens.workflow.orchestrator import step
from orglens.workflow.runstate import append_fact, read_entries, validate_entry

from .conftest import ORCHESTRATOR_WORKFLOW as WORKFLOW

def run(repo_packet, dispatch):
    packet, deck, workflow_path = repo_packet
    return step(packet, deck, WORKFLOW, workflow_path, dispatch)


def writes_findings(job) -> None:
    Path(job.writes[0]).write_text("## Findings\n- something\n")


def test_a_clean_pass_is_recorded_with_what_it_wrote(repo_packet):
    packet, _, _ = repo_packet
    result = run(repo_packet, writes_findings)
    assert result.status == "completed"
    assert result.node == "critique"
    fact = read_entries(packet)[0]
    assert fact["type"] == "node_completed"
    assert fact["wrote"] == ["findings.md"]
    assert fact["at"] and fact["event_id"]


def test_a_declared_review_raises_a_gate_and_the_next_step_blocks(repo_packet):
    packet, _, _ = repo_packet
    run(repo_packet, writes_findings)
    kinds = [e["type"] for e in read_entries(packet)]
    assert kinds == ["node_completed", "needs_human"]

    calls = []
    result = run(repo_packet, lambda job: calls.append(job))
    assert result.status == "blocked"
    assert calls == [], "a blocked packet must not dispatch"


def test_resolving_the_gate_lets_the_loop_continue(repo_packet):
    packet, _, _ = repo_packet
    run(repo_packet, writes_findings)
    outstanding = [e for e in read_entries(packet) if e["type"] == "needs_human"][-1]
    append_fact(
        packet,
        {"type": "human_resolved", "resolves": outstanding["event_id"], "note": "ok"},
    )

    def revise(job):
        Path(job.writes[0]).write_text("revised prose\n")

    result = run(repo_packet, revise)
    assert result.status == "completed"
    assert result.node == "revise"


def test_an_undeclared_modification_is_reverted_and_blocks(repo_packet):
    """Rule 6: the orchestrator verifies. A pass that dies validates nothing."""
    packet, _, _ = repo_packet

    def overreach(job):
        writes_findings(job)
        (packet / "writing-brief.md").write_text("# Brief\n\nand a widened scope\n")

    result = run(repo_packet, overreach)
    assert result.status == "reverted"
    assert "writing-brief.md" in result.detail
    assert (packet / "writing-brief.md").read_text() == "# Brief"
    assert read_entries(packet)[-1]["type"] == "needs_human"


def test_a_missed_postcondition_raises_a_question_not_a_fourth_fact(repo_packet):
    packet, _, _ = repo_packet

    def writes_nothing(job):
        pass

    result = run(repo_packet, writes_nothing)
    assert result.status == "completed"
    last = read_entries(packet)[-1]
    assert last["type"] == "needs_human"
    assert "revise" in last["question"]
    assert {e["type"] for e in read_entries(packet)} <= {
        "node_completed",
        "needs_human",
        "human_resolved",
    }


def test_a_terminal_packet_stops_without_dispatching(repo_packet):
    packet, _, _ = repo_packet
    (packet / "writing-brief.md").write_text("---\npublished: https://x/y\n---\n# Brief")
    calls = []
    result = run(repo_packet, lambda job: calls.append(job))
    assert result.status == "terminal"
    assert calls == []


def test_an_unrecognised_layout_stops_without_dispatching(repo_packet):
    packet, _, _ = repo_packet
    (packet / "draft.md").rename(packet / "draft-v2.md")
    calls = []
    result = run(repo_packet, lambda job: calls.append(job))
    assert result.status == "unknown"
    assert calls == []


def test_every_fact_the_orchestrator_writes_is_valid(repo_packet):
    packet, _, _ = repo_packet
    run(repo_packet, writes_findings)
    for entry in read_entries(packet):
        assert validate_entry(entry) == [], entry
