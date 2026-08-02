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
    # Set only on a "completed" result whose postcondition check failed —
    # `cli.record`'s own reporting needs to know this without re-deriving.
    postcondition_failed: bool = False
    expect: list[str] | None = None


def _names(paths: list[str]) -> list[str]:
    return [Path(p).name for p in paths]


def _expect_options(expect: str | list[str] | None) -> list[str]:
    """`expect` may name a single successor or a list of acceptable ones —
    see I1: a node with two legitimate successors (a diagnostic that can be
    followed by either of two cycles) cannot be pinned to just one."""
    if expect is None:
        return []
    return list(expect) if isinstance(expect, list) else [expect]


def _verify_delta(
    packet: Path,
    job: Job,
    workflow_path: Path,
    baseline: frozenset[str],
    baseline_hashes: dict[str, str | None],
) -> StepResult | None:
    """Check what a dispatch just changed against the node's declaration.

    Only `step` calls this — it is the half of rule 6 that requires a
    "before" state to judge against, and `step` is the only caller that has
    one, taken as `baseline` before it dispatched. Returns a `StepResult`
    if verification stops here (unverifiable, or a violation reverted or
    flagged), or `None` if the pass's changes were clean and recording may
    proceed.
    """
    version = workflow_version(Path(workflow_path))

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
                "question": f"{job.node}'s changes could not be verified: {exc}",
                "workflow_version": version,
            },
        )
        return StepResult("unverifiable", job.node, str(exc))

    # Partition against the baseline: new violations are this pass's doing
    # and safe to revert; a file already dirty and further modified is also
    # this pass's doing, but reverting it would destroy the pre-existing
    # edit too, so it is flagged instead; a file already dirty and left
    # alone is not a violation at all.
    reverted: list[str] = []
    flagged: list[str] = []
    for name in violations:
        if name not in baseline:
            reverted.append(name)
        elif effects.file_hash(packet, name) != baseline_hashes.get(name):
            flagged.append(name)

    if reverted:
        effects.revert(packet, reverted)
        append_fact(
            packet,
            {
                "type": "needs_human",
                "node": job.node,
                "raised_by": "verification",
                "question": (
                    f"{job.node} modified {', '.join(reverted)}, which its "
                    "declaration protects. The changes were reverted."
                ),
                "workflow_version": version,
            },
        )

    if flagged:
        append_fact(
            packet,
            {
                "type": "needs_human",
                "node": job.node,
                "raised_by": "verification",
                "question": (
                    f"{', '.join(flagged)} was already modified before {job.node} ran, "
                    f"and {job.node} modified it further. Its declaration protects it, "
                    "but reverting would destroy the changes that predate the pass, so "
                    "it was left alone for a human to sort out."
                ),
                "workflow_version": version,
            },
        )

    if reverted:
        return StepResult("reverted", job.node, ", ".join(reverted))
    if flagged:
        return StepResult("flagged", job.node, ", ".join(flagged))
    return None


def record_and_verify(
    packet: Path,
    workflow: dict,
    workflow_path: Path,
    job: Job,
    *,
    agent: str | None = None,
    by: str | None = None,
    question: str | None = None,
) -> StepResult:
    """Record that a pass ran and confirm the packet still derives where the
    workflow expects — the "record" step of the loop, and the half of rule
    6 both callers share.

    This does not check what the pass changed against its declaration —
    that is `step`'s job alone (see `_verify_delta`), because it needs a
    "before" state to judge against and this function is invoked only
    *after* a pass has already written, whether that pass was dispatched
    under `step`'s control (which has already run `_verify_delta` by the
    time this runs) or driven by hand through `cli.record` (which has no
    "before" state to have taken a baseline in, and trusts the pass to have
    respected its own declaration).

    Raises exactly one gate after recording: `question` if the caller gave
    one, otherwise the node's declared `human_review` gate. Never both — a
    single pass raising two near-identical `needs_human` facts would leave
    the packet blocked after the author's one `resolve`.
    """
    packet = Path(packet)
    version = workflow_version(Path(workflow_path))

    fact = {
        "type": "node_completed",
        "node": job.node,
        "wrote": [n for n in _names(job.writes) if (packet / n).exists()],
        "workflow_version": version,
    }
    if agent:
        fact["agent"] = agent
    if by:
        fact["by"] = by
    append_fact(packet, fact)

    after = derive_next_node(packet, workflow)
    derived = after.node if after.outcome == Outcome.RUNNABLE else str(after.outcome)
    options = _expect_options(job.expect)

    step_result = StepResult("completed", job.node, derived, expect=options or None)

    if options and derived not in options:
        # Not a fourth kind of fact. A cached derivation would drift and would
        # not stop the loop; a question does both.
        append_fact(
            packet,
            {
                "type": "needs_human",
                "node": job.node,
                "raised_by": "postcondition",
                "question": (
                    f"{job.node} expected the packet to derive to "
                    f"{' or '.join(options)}, but it derives to {derived}. What it "
                    "wrote does not leave the packet in the state the workflow expects."
                ),
                "workflow_version": version,
            },
        )
        step_result.postcondition_failed = True
    elif question is not None:
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
                "question": f"ratify {job.node}'s output before {derived} runs",
                "workflow_version": version,
            },
        )

    return step_result


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

    # Baseline taken before dispatch (C1): what is already dirty right now
    # was not caused by the pass about to run, so a violation found after
    # dispatch must be judged against this, not against HEAD alone.
    try:
        baseline = effects.dirty_files(packet)
        baseline_hashes = {name: effects.file_hash(packet, name) for name in baseline}
    except effects.VerificationUnavailable as exc:
        append_fact(
            packet,
            {
                "type": "needs_human",
                "node": job.node,
                "raised_by": "verification",
                "question": f"{job.node}'s changes could not be verified: {exc}",
                "workflow_version": version,
            },
        )
        return StepResult("unverifiable", job.node, str(exc))

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

    # 6. verify what changed against the declaration — the half of rule 6
    #    only `step` can do, since only `step` has a baseline to judge
    #    against (C1).
    delta_result = _verify_delta(packet, job, workflow_path, baseline, baseline_hashes)
    if delta_result is not None:
        return delta_result

    # 7. record — the completion-fact and postcondition-check logic, shared
    #    with `cli.record` (I2).
    return record_and_verify(packet, workflow, workflow_path, job)
