"""CLI for the workflow face.

`derive` is what a role card checks to confirm its own next step before
exiting, so --json is the primary interface.
"""

from __future__ import annotations

import json as json_module
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

import click

from orglens.workflow import blocking, orchestrator
from orglens.workflow.definition import load_workflow
from orglens.workflow.derive import derive_next_node
from orglens.workflow.job import resolve_job
from orglens.workflow.result import Outcome
from orglens.workflow.runstate import (
    append_fact,
    read_entries,
    unresolved_needs_human,
)
from orglens.workflow.validate import validate_definition

FAILING = {Outcome.AMBIGUOUS, Outcome.UNKNOWN}

DEFAULT_MAX_TURNS = 200


def _load_workflow_or_exit(workflow_path: str) -> dict:
    """Read and validate a workflow definition, or exit with a clean message.

    Shared by every command that derives against a definition: a missing
    file or a definition that names an unknown predicate must be reported,
    never crash the caller with a raw traceback (a definition problem like
    that is exactly what `validate_definition` exists to catch).
    """
    try:
        definition = load_workflow(Path(workflow_path))
    except FileNotFoundError as exc:
        click.echo(str(exc))
        raise SystemExit(2)

    problems = validate_definition(definition)
    if problems:
        click.echo(f"{workflow_path} has problems:")
        for problem in problems:
            click.echo(f"  {problem}")
        raise SystemExit(2)

    return definition


@click.group()
def workflow():
    """Derive and validate filesystem-native workflows."""


@workflow.command()
@click.argument("packet", type=click.Path(exists=True, file_okay=False))
@click.option("--workflow", "workflow_path", required=True,
              help="Path to the workflow definition.")
@click.option("--json", "as_json", is_flag=True, help="Emit the full result as JSON.")
def derive(packet: str, workflow_path: str, as_json: bool):
    """Report which node runs next for PACKET."""
    definition = _load_workflow_or_exit(workflow_path)

    result = derive_next_node(Path(packet), definition)

    block = blocking.check(Path(packet))
    payload = result.to_dict()
    payload["blocked"] = block is not None
    payload["block"] = (
        {
            "question": block.question,
            "node": block.node,
            "raised_by": block.raised_by,
            "event_id": block.event_id,
        }
        if block
        else None
    )

    if as_json:
        click.echo(json_module.dumps(payload, indent=2))
    else:
        click.echo(f"{result.outcome}: {result.node or '-'}")
        click.echo(f"  {result.reason}")
        if block:
            click.echo(f"  blocked on {block.node}: {block.question}")

    raise SystemExit(1 if result.outcome in FAILING else 0)


@workflow.command()
@click.option("--workflow", "workflow_path", required=True,
              help="Path to the workflow definition.")
def check(workflow_path: str):
    """Validate a workflow definition's structure."""
    try:
        definition = load_workflow(Path(workflow_path))
    except FileNotFoundError as exc:
        click.echo(str(exc))
        raise SystemExit(2)

    problems = validate_definition(definition)
    if not problems:
        click.echo("no problems found")
        raise SystemExit(0)

    for problem in problems:
        click.echo(f"  {problem}")
    raise SystemExit(1)


@workflow.command()
@click.argument("packet", type=click.Path(exists=True, file_okay=False))
@click.option("--workflow", "workflow_path", required=True,
              help="Path to the workflow definition.")
@click.option("--deck", required=True, help="Deck root, for role and read resolution.")
@click.option("--node", required=True, help="The node that just ran.")
@click.option("--agent", default=None, help="Which family performed the pass.")
@click.option("--session", default=None, help="Session id of the performer.")
@click.option("--question", default=None,
              help="Raise a gate after recording — how a stuck pass blocks itself.")
def record(packet: str, workflow_path: str, deck: str, node: str, agent: str | None,
           session: str | None, question: str | None):
    """Record a completed pass.

    Invoked after a pass that already ran outside this loop's view, once it
    is done writing. Writes the completion fact — what it wrote, and what it
    read — then raises exactly one gate: `--question` if given, otherwise
    the node's declared review gate, never both.

    Unlike `step`, which resolves a job's reads before dispatching it, this
    command has no "before" to resolve against — it only runs after the
    pass is already done. Its "read" is therefore resolved against the
    directory as it stands right now, at record time, which can include
    something the pass itself just wrote, not a snapshot of what the pass
    actually had in front of it when it ran.
    """
    definition = _load_workflow_or_exit(workflow_path)

    if node not in definition.get("nodes", {}):
        click.echo(f"no node {node!r} in this workflow")
        raise SystemExit(2)

    resolved = resolve_job(Path(packet), Path(deck), definition, node)
    result = orchestrator.record(
        Path(packet), definition, Path(workflow_path), resolved,
        agent=agent, by=session, question=question,
    )

    click.echo(f"recorded {result.node}")
    if result.gate == "question":
        click.echo(f"raised a gate: {question}")
    elif result.gate == "declaration":
        click.echo("raised the declared review gate")

    raise SystemExit(0)


@workflow.command()
@click.argument("packet", type=click.Path(exists=True, file_okay=False))
@click.option("--workflow", "workflow_path", required=True,
              help="Path to the workflow definition.")
@click.option("--node", required=True, help="Where the cursor moves to.")
@click.option("--note", required=True, help="Why a human moved it. Free text.")
def goto(packet: str, workflow_path: str, node: str, note: str):
    """Move the cursor by hand — jump forward, skip a stage, or redo one.

    Appends a `resumed_at` fact naming NODE as the new cursor. The only
    thing this refuses is a target that is not declared; moving backwards to
    redo a stage is ordinary use, not a special case. The only thing this
    forbids outright is moving without a reason, which is why --note is
    required.
    """
    definition = _load_workflow_or_exit(workflow_path)

    if node not in definition.get("nodes", {}):
        click.echo(f"no node {node!r} in this workflow")
        raise SystemExit(2)

    append_fact(Path(packet), {"type": "resumed_at", "node": node, "note": note})
    click.echo(f"cursor moved to {node}: {note}")
    raise SystemExit(0)


@workflow.command()
@click.argument("packet", type=click.Path(exists=True, file_okay=False))
@click.option("--workflow", "workflow_path", required=True)
@click.option("--deck", required=True, help="Deck root, for role and read resolution.")
@click.option("--dispatch", "dispatch_cmd", default=None,
              help="Command receiving the job as JSON on stdin. Omit to print and stop.")
@click.option("--once", is_flag=True, help="One turn, then exit.")
@click.option("--max-turns", "max_turns", default=DEFAULT_MAX_TURNS, show_default=True,
              help="Stop after this many turns rather than loop forever.")
def run(packet: str, workflow_path: str, deck: str, dispatch_cmd: str | None, once: bool,
        max_turns: int):
    """Drive the loop until it stops. The driver holds nothing."""
    definition = _load_workflow_or_exit(workflow_path)

    if dispatch_cmd is None:
        result = derive_next_node(Path(packet), definition)
        if result.outcome != Outcome.RUNNABLE:
            click.echo(f"{result.outcome}: {result.reason}")
            raise SystemExit(0)
        resolved = resolve_job(Path(packet), Path(deck), definition, result.node)
        click.echo(json_module.dumps(resolved.to_dict(), indent=2))
        click.echo("no dispatcher configured; pass --dispatch to execute")
        raise SystemExit(0)

    def dispatch(job):
        subprocess.run(
            [dispatch_cmd],
            input=json_module.dumps(job.to_dict()),
            text=True,
            check=True,
        )

    turns = 0
    while True:
        turns += 1
        if turns > max_turns:
            click.echo(
                f"stopped after {max_turns} turns without completing; a guard that "
                "never changes under its own node's completion would otherwise "
                "dispatch forever unattended. Pass --max-turns to raise the bound."
            )
            raise SystemExit(1)

        outcome = orchestrator.step(
            Path(packet), Path(deck), definition, Path(workflow_path), dispatch
        )
        click.echo(f"{outcome.status}: {outcome.node or '-'}  {outcome.detail}")
        if outcome.status != "completed" or once:
            raise SystemExit(0 if outcome.status in ("completed", "terminal", "blocked") else 1)


@workflow.command()
@click.argument("packet", type=click.Path(exists=True, file_okay=False))
@click.option("--workflow", "workflow_path", required=True)
@click.option("--deck", required=True, help="Deck root, for role and read resolution.")
@click.option("--node", default=None, help="Override; otherwise derive.")
@click.option("--json", "as_json", is_flag=True)
def job(packet: str, workflow_path: str, deck: str, node: str | None, as_json: bool):
    """Emit a fully resolved job for PACKET — absolute paths, no templates."""
    definition = _load_workflow_or_exit(workflow_path)
    chosen = node
    if chosen is None:
        result = derive_next_node(Path(packet), definition)
        if result.outcome != Outcome.RUNNABLE:
            click.echo(f"{result.outcome}: {result.reason}")
            raise SystemExit(1)
        chosen = result.node
    elif chosen not in definition.get("nodes", {}):
        click.echo(f"no node {chosen!r} in this workflow")
        raise SystemExit(2)

    resolved = resolve_job(Path(packet), Path(deck), definition, chosen)
    if as_json:
        click.echo(json_module.dumps(resolved.to_dict(), indent=2))
        raise SystemExit(0)

    click.echo(f"node:   {resolved.node}")
    click.echo(f"role:   {resolved.role}")

    # Every declared glob's outcome, reported against `Job.unmatched` — the
    # same verdict `resolve_job` already reached — rather than a second,
    # independent match computed here. A glob that resolved is re-listed
    # through the identical call `resolve_job` made (`Path.glob`, not a
    # basename comparison), so a glob naming a subdirectory reports
    # correctly instead of always missing.
    declared_reads = definition.get("nodes", {}).get(chosen, {}).get("reads") or []
    packet_path = Path(packet)
    for glob in declared_reads:
        if glob in resolved.unmatched:
            click.echo(f"read:   {glob} (no match)")
            continue
        for path in sorted(str(p.resolve()) for p in packet_path.glob(glob)):
            click.echo(f"read:   {glob} -> {path}")

    for path in resolved.writes:
        click.echo(f"write:  {path}")
    raise SystemExit(0)


@workflow.command()
@click.argument("packet", type=click.Path(exists=True, file_okay=False))
@click.option("--note", required=True, help="What you decided. Free text.")
def resolve(packet: str, note: str):
    """Clear the outstanding question with a free-text note."""
    outstanding = unresolved_needs_human(read_entries(Path(packet)))
    if outstanding is None:
        click.echo("nothing outstanding to resolve")
        raise SystemExit(1)

    append_fact(
        Path(packet),
        {
            "type": "human_resolved",
            "event_id": uuid.uuid4().hex[:12],
            "at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "resolves": outstanding.get("event_id"),
            "note": note,
        },
    )
    click.echo(f"resolved {outstanding.get('event_id')}")
    raise SystemExit(0)
