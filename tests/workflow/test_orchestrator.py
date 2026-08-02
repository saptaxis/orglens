from __future__ import annotations

import copy
from pathlib import Path

import yaml

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
    """Rule 6: the orchestrator verifies. A pass that dies validates nothing.

    C1, case 1 (clean-then-violation): the packet is clean when this pass
    starts, so any protected file it modifies is unambiguously its own
    doing, and reverting it destroys nothing but the pass's own overreach.
    """
    packet, _, _ = repo_packet

    def overreach(job):
        writes_findings(job)
        (packet / "writing-brief.md").write_text("# Brief\n\nand a widened scope\n")

    result = run(repo_packet, overreach)
    assert result.status == "reverted"
    assert "writing-brief.md" in result.detail
    assert (packet / "writing-brief.md").read_text() == "# Brief"
    assert read_entries(packet)[-1]["type"] == "needs_human"


def test_a_pre_existing_dirty_file_left_untouched_is_not_a_violation(repo_packet):
    """C1, case 2: an author's uncommitted edit to a protected file, sitting
    there before this pass ever starts and left alone by it, must not be
    attributed to the pass — and must not be reverted. Before the fix,
    `effects.check_delta` diffed only against `HEAD`, with no baseline taken
    before dispatch, so this pre-existing edit looked identical to a
    violation the pass had just made and `git checkout HEAD --` destroyed
    it."""
    packet, _, _ = repo_packet
    (packet / "draft.md").write_text("the author's own half-finished edit\n")

    result = run(repo_packet, writes_findings)

    assert result.status == "completed"
    assert (packet / "draft.md").read_text() == "the author's own half-finished edit\n"
    assert not any(
        e["type"] == "needs_human" and e.get("raised_by") == "verification"
        for e in read_entries(packet)
    )


def test_a_pre_existing_dirty_file_further_modified_is_flagged_not_reverted(repo_packet):
    """C1, case 3: the pass compounds its own change on top of an edit that
    predates it. This is a real violation — the pass touched a protected
    file — but reverting it to `HEAD` would destroy the author's
    pre-existing work along with the pass's own overreach, so it must be
    left alone and a human told, not silently wiped."""
    packet, _, _ = repo_packet
    (packet / "draft.md").write_text("the author's own half-finished edit\n")

    def compounds(job):
        writes_findings(job)
        (packet / "draft.md").write_text("the pass piled on top\n")

    result = run(repo_packet, compounds)

    assert result.status == "flagged"
    assert "draft.md" in result.detail
    assert (packet / "draft.md").read_text() == "the pass piled on top\n"
    last = [e for e in read_entries(packet) if e["type"] == "needs_human"][-1]
    assert last["raised_by"] == "verification"
    assert "draft.md" in last["question"]


def test_verification_that_cannot_run_does_not_complete(tmp_path: Path):
    """Outside a git repo, `effects.check_delta` cannot tell whether
    anything protected changed. That is ignorance, not safety — the
    orchestrator must not record the pass as completed on the strength of
    a check that never ran, even though this packet is otherwise identical
    to a real one and the pass genuinely wrote what it declared."""
    (tmp_path / "writing.yaml").write_text(
        "default: portfolio\nprofiles:\n  portfolio: {}\n"
    )
    packet = tmp_path / "a-piece"
    packet.mkdir()
    (packet / "writing-brief.md").write_text("# Brief")
    (packet / "draft.md").write_text("original prose\n")
    deck = tmp_path / "deck"
    deck.mkdir()
    for card in ("critic.md", "liner.md", "smell.md"):
        (deck / card).write_text(f"# {card}")
    workflow_path = tmp_path / "WORKFLOW.yaml"
    workflow_path.write_text(yaml.safe_dump(WORKFLOW))
    # Deliberately no `git init` — this is the whole point of the test.

    result = step(packet, deck, WORKFLOW, workflow_path, writes_findings)
    assert result.status != "completed"
    assert "node_completed" not in {e["type"] for e in read_entries(packet)}
    last = read_entries(packet)[-1]
    assert last["type"] == "needs_human"
    assert last["raised_by"] == "verification"


def test_a_dispatch_that_writes_nothing_does_not_complete(repo_packet):
    """The other half of verify: declared writes must exist. A diagnosing
    node that dispatches and writes nothing must not be recorded as a
    completed pass — that is a silent no-op wearing a success status."""
    packet, deck, workflow_path = repo_packet

    def writes_nothing(job):
        pass

    result = run(repo_packet, writes_nothing)
    assert result.status != "completed"
    assert "node_completed" not in {e["type"] for e in read_entries(packet)}
    last = read_entries(packet)[-1]
    assert last["type"] == "needs_human"
    assert "findings.md" in last["question"]


def test_a_missed_postcondition_raises_a_question_not_a_fourth_fact(repo_packet):
    """Genuinely trips the postcondition branch: the dispatch writes
    everything critique declares (so verification's write-existence check
    passes and a completion fact is recorded), but the workflow's own
    `expect` is deliberately wrong against what the sequence predicates
    actually derive — the same technique a lying node's declaration would
    produce. `raised_by` pins this to the postcondition branch so it can
    never be confused with the ratification gate (`raised_by: "declaration"`),
    which both fire a `needs_human` and both can mention the derived node."""
    packet, deck, workflow_path = repo_packet

    lying_workflow = copy.deepcopy(WORKFLOW)
    lying_workflow["nodes"]["critique"]["expect"] = "audit"  # real derivation is "revise"

    result = step(packet, deck, lying_workflow, workflow_path, writes_findings)
    assert result.status == "completed"
    assert read_entries(packet)[0]["type"] == "node_completed"

    last = read_entries(packet)[-1]
    assert last["type"] == "needs_human"
    assert last["raised_by"] == "postcondition"
    assert "revise" in last["question"]
    assert {e["type"] for e in read_entries(packet)} <= {
        "node_completed",
        "needs_human",
        "human_resolved",
    }


def test_the_ratification_gate_is_raised_by_declaration(repo_packet):
    """The other branch of the same if/elif: `expect` matches the real
    derivation, so it is `human_review` alone that raises the gate. Pinned
    on `raised_by` so this can never be mistaken for the postcondition
    branch above, even though both mention the same derived node."""
    packet, _, _ = repo_packet
    result = run(repo_packet, writes_findings)
    assert result.status == "completed"
    last = read_entries(packet)[-1]
    assert last["type"] == "needs_human"
    assert last["raised_by"] == "declaration"


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
