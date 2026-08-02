"""One turn of the loop.

The orchestrator holds nothing. Every question it asks is answered by a
module that already exists — blocking, derive, job, runstate — and its only
job is to ask them in the order the definition fixes, and to write down what
happened.

There is no verification step here anymore. Protection is a sentence in a
role card now, and recovery from a pass that overreaches is git, not this
module: nothing here takes a snapshot before a dispatch or inspects what
changed afterward. If a pass writes nothing it declared, the next node's
guard simply does not fire and the packet stalls in a visible, diagnosable
way — the guard graph is the check.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from orglens.workflow import blocking
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


def record(
    packet: Path,
    workflow: dict,
    workflow_path: Path,
    job: Job,
    *,
    agent: str | None = None,
    by: str | None = None,
    question: str | None = None,
) -> StepResult:
    """Write down that a pass ran — the one implementation of the
    completion fact, shared by `step` (which just dispatched the pass
    itself) and the CLI's own `record` verb (a pass reporting itself after
    running entirely outside this loop's view).

    The fact carries `wrote` — the node's declared writes that exist right
    now — and `read` — the files this job actually handed the pass to read.
    `read` has to be captured here rather than recomputed later: the
    directory keeps changing underneath a packet, so which files a pass saw
    is a fact about the past, not something derivable from the packet's
    current shape.

    Raises exactly one gate after recording: `question` if the caller gave
    one, otherwise the node's declared review gate. Never both, and this
    function never re-derives to check anything — there is no postcondition
    left to fail.
    """
    packet = Path(packet)
    version = workflow_version(Path(workflow_path))

    fact = {
        "type": "node_completed",
        "node": job.node,
        "wrote": [n for n in _names(job.writes) if (packet / n).exists()],
        "read": _names(job.reads),
        "workflow_version": version,
    }
    if agent:
        fact["agent"] = agent
    if by:
        fact["by"] = by
    append_fact(packet, fact)

    result = StepResult("completed", job.node)

    if question is not None:
        append_fact(
            packet,
            {
                "type": "needs_human",
                "node": job.node,
                "raised_by": "node",
                "question": question,
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
                "question": f"{job.node} is declared for human review before the next node runs",
                "workflow_version": version,
            },
        )

    return result


def step(
    packet: Path,
    deck: Path,
    workflow: dict,
    workflow_path: Path,
    dispatch: Callable[[Job], None],
) -> StepResult:
    """One turn: blocked? -> derive -> job -> dispatch -> record."""
    packet = Path(packet)

    # 1. blocked? an unresolved question stops everything, and nothing else
    #    is consulted — not derivation, not a guard.
    block = blocking.check(packet)
    if block is not None:
        return StepResult("blocked", block.node, block.question)

    # 2. derive
    result = derive_next_node(packet, workflow)
    if result.outcome != Outcome.RUNNABLE:
        return StepResult(str(result.outcome), result.node, result.reason)

    # 3. job
    resolved = resolve_job(packet, deck, workflow, result.node)

    # 4. dispatch
    dispatch(resolved)

    # 5. record — the shared completion-fact path.
    return record(packet, workflow, workflow_path, resolved)
