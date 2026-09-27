"""`orglens workflow <verb> <packet>`: next, done, note, goto.

The packet is a directory. The workflow comes from the log's `workflow` line;
`--workflow` overrides it and, on a packet with no log yet, writes that line.

Exit codes: 0 for `next` on a runnable node, complete, or waiting; 1 for a
log naming a node the workflow no longer has; 2 for a bad workflow or a refused
write. Programs and dispatchers read `--json`; humans read the text.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from orglens import complete, formats
from orglens.workflow import session
from orglens.workflow.definition import Workflow, WorkflowError, load_workflow
from orglens.workflow.session import Position, State


def _fail(message: str, code: int = 2) -> None:
    click.echo(message, err=True)
    sys.exit(code)


def _load(packet: Path, workflow_opt: str | None) -> tuple[Workflow, list[dict]]:
    """The workflow and the log. Binds the packet when `--workflow` names a workflow it
    has none of; refuses a second, different binding."""
    facts = session.read(packet)
    bound = session.workflow_path(facts)
    if workflow_opt is not None:
        given = Path(workflow_opt).expanduser().resolve()
        if bound is None:
            session.bind(packet, given)
            facts = session.read(packet)
        elif bound.resolve() != given:
            _fail(f"{packet} is bound to {bound}; --workflow names {given}")
        path = given
    elif bound is not None:
        path = bound
    else:
        _fail("no workflow bound: pass --workflow once to bind this packet")
    try:
        return load_workflow(path), facts
    except WorkflowError as exc:
        _fail(str(exc))
    raise AssertionError("unreachable")


def _preferred_format() -> str:
    """The format new packet files are written in: the configured grammar's.
    Markdown when there is no config, as in a test or a fresh machine."""
    try:
        from orglens.config import Config
        return Config.current().load_grammar().format
    except Exception:
        return "md"


def _output(packet: Path, writes: str) -> Path:
    """The file a node writes. A name with a suffix is used as written, as
    every workflow did before R24. A stem is the file that exists in any
    format, else a new one in the grammar's format."""
    if Path(writes).suffix in formats.SUFFIXES:
        return packet / writes
    prefer = _preferred_format()
    found = formats.existing(packet, writes, prefer)
    return found if found is not None else packet / f"{writes}{formats.get(prefer).suffix}"


def _describe(packet: Path, pos: Position) -> dict:
    return {
        "state": pos.state.value,
        "node": pos.node.name if pos.node else None,
        "program": str(pos.node.program) if pos.node else None,
        "write": str(_output(packet, pos.node.writes)) if pos.node else None,
        "note": pos.note,
    }


@click.group()
def workflow():
    """A line of nodes over one packet, with a human between."""


@workflow.command(name="next")
@click.argument("packet", type=click.Path(file_okay=False, path_type=Path),
                shell_complete=complete.packets)
@click.option("--workflow", "workflow_opt", default=None, help="Bind or override the workflow.")
@click.option("--json", "as_json", is_flag=True)
def next_cmd(packet: Path, workflow_opt: str | None, as_json: bool):
    """What to run next, or why nothing can run."""
    workflow, facts = _load(packet, workflow_opt)
    pos = session.next_node(workflow, facts)

    if as_json:
        out = _describe(packet, pos)
        if pos.state == State.WAITING:
            out["question"] = pos.question
        click.echo(json.dumps(out))
        sys.exit(1 if pos.state == State.UNKNOWN else 0)

    if pos.state == State.RUNNABLE:
        click.echo(f"node: {pos.node.name}")
        click.echo(f"program: {pos.node.program}")
        click.echo(f"write: {_output(packet, pos.node.writes)}")
        if pos.note:
            click.echo(f"note:  {json.dumps(pos.note)}")
    elif pos.state == State.WAITING:
        click.echo(f"waiting on: {pos.question}            (after node {pos.after})")
    elif pos.state == State.COMPLETE:
        click.echo("complete")
    else:
        _fail(f"unknown node in session: {pos.after}", code=1)


@workflow.command()
@click.argument("packet", type=click.Path(file_okay=False, path_type=Path),
                shell_complete=complete.packets)
@click.option("--node", required=True, shell_complete=complete.nodes)
@click.option("--agent", required=True, help="Who performed the program: claude, codex, ...")
@click.option("--question", default=None, help="Ask the human before the next node.")
@click.option("--workflow", "workflow_opt", default=None)
@click.option("--force", is_flag=True, help="Finish a node the workflow is not on.")
def done(packet: Path, node: str, agent: str, question: str | None,
         workflow_opt: str | None, force: bool):
    """Record that a node finished. Refuses a node the workflow is not on."""
    workflow, facts = _load(packet, workflow_opt)
    target = workflow.node(node)
    if target is None:
        _fail(f"'{node}' is not a node of {workflow.name}: "
              + ", ".join(s.name for s in workflow.nodes))
    pos = session.next_node(workflow, facts)
    if not force:
        if pos.state == State.WAITING:
            _fail(f"waiting on: {pos.question} (after node {pos.after}); "
                  "answer it with `note`, or move with `goto`")
        if pos.state == State.COMPLETE:
            _fail(f"{workflow.name} is complete; `goto` a node to run it again")
        if pos.node is None or pos.node.name != node:
            on = pos.node.name if pos.node else pos.after
            _fail(f"the workflow is on {on}, not {node}; --force records it anyway")

    out = _output(packet, target.writes)
    fact = {"type": "done", "node": node, "agent": agent,
            "wrote": [out.name] if out.exists() else []}
    if question:
        fact["question"] = question
    if force:
        fact["forced"] = True
    session.append(packet, fact)
    click.echo(f"done: {node}" + (f" (asks: {question})" if question else ""))


@workflow.command()
@click.argument("packet", type=click.Path(file_okay=False, path_type=Path),
                shell_complete=complete.packets)
@click.argument("text")
def note(packet: Path, text: str):
    """Answer the open gate. The text is handed to the next program verbatim."""
    workflow, facts = _load(packet, None)
    pos = session.next_node(workflow, facts)
    if pos.state != State.WAITING:
        _fail("no gate is open")
    last = [f for f in facts if f["type"] in session.ROUTING][-1]
    session.append(packet, {"type": "note", "resolves": last["id"], "text": text})
    click.echo(f"noted; next: {pos.node.name if pos.node else 'complete'}")


@workflow.command()
@click.argument("packet", type=click.Path(file_okay=False, path_type=Path),
                shell_complete=complete.packets)
@click.option("--node", required=True, help="The node to run next.",
              shell_complete=complete.nodes)
@click.option("--why", required=True)
@click.option("--workflow", "workflow_opt", default=None)
def goto(packet: Path, node: str, why: str, workflow_opt: str | None):
    """Point the workflow at a node. Clears any open gate; `why` is the note."""
    workflow, _ = _load(packet, workflow_opt)
    if workflow.node(node) is None:
        _fail(f"'{node}' is not a node of {workflow.name}: "
              + ", ".join(s.name for s in workflow.nodes))
    session.append(packet, {"type": "goto", "node": node, "why": why})
    click.echo(f"next: {node}")

