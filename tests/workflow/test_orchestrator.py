from __future__ import annotations

from pathlib import Path

from orglens.workflow.orchestrator import StepResult, step
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
    assert "read" in fact
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


def test_the_gate_is_raised_by_declaration_not_a_question(repo_packet):
    """The `elif job.human_review` branch: no `--question` was given, so the
    gate's `raised_by` pins it to the node's own declaration."""
    packet, _, _ = repo_packet
    result = run(repo_packet, writes_findings)
    assert result.status == "completed"
    last = read_entries(packet)[-1]
    assert last["type"] == "needs_human"
    assert last["raised_by"] == "declaration"


def test_a_dispatch_that_writes_nothing_still_completes(repo_packet):
    """There is no more write-existence check. A diagnosing node that
    dispatches and writes nothing is recorded with an empty `wrote` — the
    next node's guard simply will not fire, which is the stall the model
    now relies on instead of a verification step."""
    packet, _, _ = repo_packet

    def writes_nothing(job):
        pass

    result = run(repo_packet, writes_nothing)
    assert result.status == "completed"
    fact = read_entries(packet)[0]
    assert fact["type"] == "node_completed"
    assert fact["wrote"] == []


def test_the_loop_has_no_verification_status(repo_packet):
    """Protection is prose in a role card now; git is the recovery."""
    from orglens.workflow.orchestrator import StepResult
    import inspect

    src = inspect.getsource(StepResult) + inspect.getsource(step)
    for gone in ("reverted", "flagged", "unverifiable", "baseline", "check_delta"):
        assert gone not in src, gone


def test_a_pass_that_overreaches_is_recorded_not_reverted(repo_packet):
    packet, deck, wf = repo_packet
    original = (packet / "writing-brief.md").read_text()

    def overreach(job):
        Path(job.writes[0]).write_text("## Findings\n")
        (packet / "writing-brief.md").write_text(original + "\nwidened\n")

    r = run(repo_packet, overreach)
    assert r.status == "completed"
    assert "widened" in (packet / "writing-brief.md").read_text()


def test_a_terminal_packet_stops_without_dispatching(repo_packet):
    packet, _, _ = repo_packet
    (packet / "PUBLISHED").write_text("")
    calls = []
    result = run(repo_packet, lambda job: calls.append(job))
    assert result.status == "terminal"
    assert calls == []


def test_an_unrecognised_cursor_stops_without_dispatching(repo_packet):
    packet, _, _ = repo_packet
    append_fact(packet, {"type": "node_completed", "node": "a-node-not-declared-here"})
    calls = []
    result = run(repo_packet, lambda job: calls.append(job))
    assert result.status == "unknown"
    assert calls == []


def test_every_fact_the_orchestrator_writes_is_valid(repo_packet):
    packet, _, _ = repo_packet
    run(repo_packet, writes_findings)
    for entry in read_entries(packet):
        assert validate_entry(entry) == [], entry


# --- fix round 1 ------------------------------------------------------------
# Finding 3: `"read" in fact` is satisfied by `read: []`. Pin the content —
# `critique` declares two read globs and only one of them matches anything
# in the fixture packet, so this also confirms an unmatched glob contributes
# nothing to `read` rather than, say, its own literal name.


def test_the_completion_fact_names_exactly_what_was_read(repo_packet):
    packet, _, _ = repo_packet
    run(repo_packet, writes_findings)
    fact = read_entries(packet)[0]
    assert fact["read"] == ["writing-brief.md"]
