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
