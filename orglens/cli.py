"""CLI — click commands for orglens."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click

from orglens.config import Config
from orglens.snapshot import generate_snapshot
from orglens.state import extract_status
from orglens.topology import Topology


def _load_config() -> Config:
    """Load config from env var or default location."""
    config_path = os.environ.get("ORGLENS_CONFIG")
    if config_path:
        return Config.from_yaml(Path(config_path))
    return Config.load()


def _load_topo() -> tuple[Topology, Config]:
    """Load config + grammar + topology."""
    config = _load_config()
    grammar = config.load_grammar()
    return Topology(config.docs_root, grammar), config


@click.group()
def cli():
    """orglens — organizational lens for AI agents."""
    pass


@cli.command()
@click.option("--type", "entity_type", default=None, help="Filter by entity type")
def list(entity_type: str | None):
    """List all entities in the topology."""
    topo, config = _load_topo()
    entities = topo.list_entities(entity_type)

    if not entities:
        click.echo("No entities found.")
        return

    # Group by type
    by_type: dict[str, list] = {}
    for e in entities:
        by_type.setdefault(e.entity_type, []).append(e)

    type_order = ["research-program", "experiment", "project", "client"]
    type_display = {
        "research-program": "Research Programs",
        "experiment": "  Experiments",
        "project": "Projects",
        "client": "Clients",
    }

    for etype in type_order:
        group = by_type.get(etype, [])
        if not group:
            continue
        click.echo(f"\n{type_display.get(etype, etype)}:")
        for e in group:
            # Read status if available
            et = topo.grammar.entity_types[etype]
            status = None
            if et.state_file:
                state_file = e.path / et.state_file
                if state_file.exists():
                    status = extract_status(state_file.read_text())
            status_str = f"  ({status})" if status else ""
            parent_str = f"  [{e.parent_name}]" if e.parent_name else ""
            click.echo(f"  {e.name}{status_str}{parent_str}")


@cli.command()
def status():
    """Show aggregated status across all entities."""
    topo, config = _load_topo()
    entities = topo.list_entities()

    by_type: dict[str, list] = {}
    for e in entities:
        by_type.setdefault(e.entity_type, []).append(e)

    type_display = {
        "research-program": "Research Programs",
        "project": "Projects",
        "client": "Clients",
    }

    for etype in ["research-program", "project", "client"]:
        group = by_type.get(etype, [])
        if not group:
            continue
        click.echo(f"\n{type_display.get(etype, etype)}:")
        for e in group:
            et = topo.grammar.entity_types[etype]
            status = None
            if et.state_file:
                state_file = e.path / et.state_file
                if state_file.exists():
                    status = extract_status(state_file.read_text())
            status_str = status.title() if status else "—"

            # Count artifacts
            plan_count = len(topo.find_artifacts("plan", e.name))
            plan_str = f"  {plan_count} plans" if plan_count else ""

            # Count child experiments for research programs
            expt_str = ""
            if etype == "research-program":
                expts = by_type.get("experiment", [])
                rp_expts = [x for x in expts if x.parent_name == e.name]
                if rp_expts:
                    expt_str = f"  {len(rp_expts)} experiments"

            click.echo(f"  {e.name:<40} {status_str:<20}{expt_str}{plan_str}")


@cli.command()
@click.argument("artifact_type")
@click.argument("entity", required=False)
def find(artifact_type: str, entity: str | None):
    """Find artifacts by type, optionally scoped to an entity."""
    topo, config = _load_topo()

    if artifact_type not in topo.grammar.artifact_types:
        click.echo(
            f"Unknown artifact type: {artifact_type}. "
            f"Available: {', '.join(topo.grammar.artifact_types.keys())}",
            err=True,
        )
        sys.exit(1)

    artifacts = topo.find_artifacts(artifact_type, entity)
    if not artifacts:
        click.echo(f"No {artifact_type}s found.")
        return

    for a in artifacts:
        rel_path = a.path.relative_to(config.docs_root)
        click.echo(f"  {a.name:<45} [{a.entity_name}]  {rel_path}")


@cli.command()
@click.argument("type_or_artifact")
@click.argument("name")
@click.argument("topic", required=False)
@click.option("--parent", default=None, help="Parent entity (for experiments)")
def new(type_or_artifact: str, name: str, topic: str | None, parent: str | None):
    """Create a new entity or artifact.

    Entity:   orglens new project my-tool
    Artifact: orglens new plan my-tool "feature design"
    """
    topo, config = _load_topo()

    # Is it an entity type?
    if type_or_artifact in topo.grammar.entity_types:
        path = topo.scaffold_entity(type_or_artifact, name, parent=parent)
        click.echo(f"Created {type_or_artifact}: {path.relative_to(config.docs_root)}")
        # Refresh snapshot
        _refresh_snapshot(topo, config)
        return

    # Is it an artifact type?
    if type_or_artifact in topo.grammar.artifact_types:
        if not topic:
            click.echo(f"Usage: orglens new {type_or_artifact} <entity> <topic>", err=True)
            sys.exit(1)
        path = topo.scaffold_artifact(type_or_artifact, name, topic)
        click.echo(f"Created {type_or_artifact}: {path.relative_to(config.docs_root)}")
        # Refresh snapshot
        _refresh_snapshot(topo, config)
        return

    click.echo(
        f"Unknown type: {type_or_artifact}. "
        f"Entity types: {', '.join(topo.grammar.entity_types.keys())}. "
        f"Artifact types: {', '.join(topo.grammar.artifact_types.keys())}.",
        err=True,
    )
    sys.exit(1)


@cli.command()
@click.option("--stdout", is_flag=True, help="Print snapshot to stdout instead of writing to file")
def snapshot(stdout: bool):
    """Generate a topology snapshot."""
    topo, config = _load_topo()

    if stdout:
        snap = generate_snapshot(topo, config)
        click.echo(snap)
    else:
        output = config.snapshot_path
        generate_snapshot(topo, config, output_path=output)
        click.echo(f"Snapshot written to {output}")


def _refresh_snapshot(topo: Topology, config: Config):
    """Silently refresh the snapshot after write operations."""
    try:
        generate_snapshot(topo, config, output_path=config.snapshot_path)
    except Exception:
        pass  # Non-critical — don't fail the main operation
