"""One turn of the loop.

The orchestrator holds nothing. Every question it asks is answered by a module
that already existed — blocking, derive, job, effects, runstate — and its only
job is to ask them in the order workflow.md fixes, and to write down what
happened. Rule 6 lives here: a pass that dies validates nothing, so the caller
verifies rather than the pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from orglens.workflow import blocking, effects
from orglens.workflow.derive import derive_next_node
from orglens.workflow.job import Job, resolve_job
from orglens.workflow.result import Outcome
from orglens.workflow.runstate import append_fact, workflow_version


@dataclass
class StepResult:
    status: str
    node: str | None = None
    detail: str = ""


def _names(paths: list[str]) -> list[str]:
    return [Path(p).name for p in paths]


def step(
    packet: Path,
    deck: Path,
    workflow: dict,
    workflow_path: Path,
    dispatch: Callable[[Job], None],
) -> StepResult:
    packet = Path(packet)

    # 1. blocked? an unresolved question stops everything, and nothing else
    #    is consulted — not derivation, certainly not the guards.
    block = blocking.check(packet)
    if block is not None:
        return StepResult("blocked", block.node, block.question)

    # 2. derive
    result = derive_next_node(packet, workflow)
    if result.outcome != Outcome.RUNNABLE:
        return StepResult(str(result.outcome), result.node, result.reason)

    # 3. job
    job = resolve_job(packet, deck, workflow, result.node)
    version = workflow_version(Path(workflow_path))

    # 4. dispatch
    dispatch(job)

    # 5. verify — before recording, because an overreaching pass has not
    #    completed, it has damaged the packet. Two clauses: the declared
    #    writes exist, and nothing outside must_not_modify moved.

    missing = [n for n in job.writes if not Path(n).exists()]
    if missing:
        append_fact(
            packet,
            {
                "type": "needs_human",
                "node": job.node,
                "raised_by": "verification",
                "question": (
                    f"{job.node} did not write {', '.join(_names(missing))}, "
                    "which its declaration promised."
                ),
                "workflow_version": version,
            },
        )
        return StepResult("incomplete", job.node, ", ".join(_names(missing)))

    try:
        violations = effects.check_delta(
            packet,
            {"must_not_modify": _names(job.must_not_modify), "writes": _names(job.writes)},
        )
    except effects.VerificationUnavailable as exc:
        append_fact(
            packet,
            {
                "type": "needs_human",
                "node": job.node,
                "raised_by": "verification",
                "question": (
                    f"{job.node}'s changes could not be verified: {exc}"
                ),
                "workflow_version": version,
            },
        )
        return StepResult("unverifiable", job.node, str(exc))

    if violations:
        effects.revert(packet, violations)
        append_fact(
            packet,
            {
                "type": "needs_human",
                "node": job.node,
                "raised_by": "verification",
                "question": (
                    f"{job.node} modified {', '.join(violations)}, which its "
                    "declaration protects. The changes were reverted."
                ),
                "workflow_version": version,
            },
        )
        return StepResult("reverted", job.node, ", ".join(violations))

    # 6. record
    append_fact(
        packet,
        {
            "type": "node_completed",
            "node": job.node,
            "wrote": [n for n in _names(job.writes) if (packet / n).exists()],
            "workflow_version": version,
        },
    )

    after = derive_next_node(packet, workflow)
    derived = after.node if after.outcome == Outcome.RUNNABLE else str(after.outcome)

    if job.expect and derived != job.expect:
        # Not a fourth kind of fact. A cached derivation would drift and would
        # not stop the loop; a question does both.
        append_fact(
            packet,
            {
                "type": "needs_human",
                "node": job.node,
                "raised_by": "postcondition",
                "question": (
                    f"{job.node} expected the packet to derive to {job.expect}, "
                    f"but it derives to {derived}. What it wrote does not leave "
                    "the packet in the state the workflow expects."
                ),
                "workflow_version": version,
            },
        )
    elif job.human_review:
        append_fact(
            packet,
            {
                "type": "needs_human",
                "node": job.node,
                "raised_by": "declaration",
                "question": f"ratify {job.node}'s output before {derived} runs",
                "workflow_version": version,
            },
        )

    return StepResult("completed", job.node, derived)
