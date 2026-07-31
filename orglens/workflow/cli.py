"""CLI for the workflow face.

`derive` is what role files call to check their own postcondition before
exiting, so --json is the primary interface.
"""

from __future__ import annotations

import json as json_module
from pathlib import Path

import click

from orglens.workflow.definition import load_workflow
from orglens.workflow.derive import derive_next_node
from orglens.workflow.result import Outcome
from orglens.workflow.runlog import append_fact, workflow_version
from orglens.workflow.validate import validate_definition

FAILING = {Outcome.MALFORMED, Outcome.AMBIGUOUS, Outcome.UNKNOWN}


@click.group()
def workflow():
    """Derive and validate filesystem-native workflows."""


@workflow.command()
@click.argument("packet", type=click.Path(exists=True, file_okay=False))
@click.option("--workflow", "workflow_path", required=True,
              help="Path to WORKFLOW.yaml.")
@click.option("--json", "as_json", is_flag=True, help="Emit the full result as JSON.")
def derive(packet: str, workflow_path: str, as_json: bool):
    """Report which node runs next for PACKET."""
    try:
        definition = load_workflow(Path(workflow_path))
    except FileNotFoundError as exc:
        click.echo(str(exc))
        raise SystemExit(2)

    result = derive_next_node(Path(packet), definition)

    if as_json:
        click.echo(json_module.dumps(result.to_dict(), indent=2))
    else:
        click.echo(f"{result.outcome}: {result.node or '-'}")
        click.echo(f"  {result.reason}")

    raise SystemExit(1 if result.outcome in FAILING else 0)


@workflow.command()
@click.option("--workflow", "workflow_path", required=True,
              help="Path to WORKFLOW.yaml.")
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
              help="Path to WORKFLOW.yaml.")
@click.option("--node", required=True, help="The node that just ran.")
@click.option("--agent", default=None, help="Which family performed the pass.")
@click.option("--session", default=None, help="Session id of the performer.")
def record(packet: str, workflow_path: str, node: str, agent: str | None,
           session: str | None):
    """Record a completed pass, then confirm the packet derives to `expect`.

    A node that writes files and exits has no idea whether what it wrote is
    well-formed. This is where it finds out, while the context that could fix
    it still exists.
    """
    try:
        definition = load_workflow(Path(workflow_path))
    except FileNotFoundError as exc:
        click.echo(str(exc))
        raise SystemExit(2)

    spec = definition.get("nodes", {}).get(node)
    if spec is None:
        click.echo(f"no node {node!r} in this workflow")
        raise SystemExit(2)

    fact = {
        "type": "node_completed",
        "node": node,
        "workflow_version": workflow_version(Path(workflow_path)),
    }
    if agent:
        fact["agent"] = agent
    if session:
        fact["by"] = session
    append_fact(Path(packet), fact)

    result = derive_next_node(Path(packet), definition)
    expected = spec.get("expect")
    if expected is None:
        click.echo(f"recorded {node}; no expect declared, nothing to check")
        raise SystemExit(0)

    actual = result.node if result.outcome == Outcome.RUNNABLE else str(result.outcome)
    if actual == expected:
        click.echo(f"recorded {node}; packet derives to {actual} as expected")
        raise SystemExit(0)

    click.echo(f"POSTCONDITION FAILED for {node}")
    click.echo(f"  expected {expected}, got {actual}")
    click.echo(f"  derivation: {result.outcome} {result.node or '-'}")
    click.echo(f"  {result.reason}")
    click.echo("  the output this pass wrote does not leave the packet in the")
    click.echo("  state the workflow expects. Fix it and re-derive.")
    raise SystemExit(1)
