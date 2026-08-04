"""CLI — click commands for orglens."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click

import time

from orglens import activity, view

from orglens.config import Config
from orglens.snapshot import generate_snapshot
from orglens.state import extract_status
from orglens.topology import Topology
from orglens.workflow.cli import workflow as workflow_group


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


cli.add_command(workflow_group, name="workflow")


def _ago(ts: int) -> str:
    """Coarse age. Precision past the hour is noise at this scale."""
    hours = (time.time() - ts) / 3600
    if hours < 24:
        return f"{hours:.0f}h"
    if hours < 24 * 60:
        return f"{hours / 24:.0f}d"
    return f"{hours / 720:.0f}mo"


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

    waiting: list[tuple[str, activity.Activity]] = []

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
            if status:
                # Truncate after first semicolon
                truncated = status.split(";")[0].strip()
                # Capitalize first letter only
                status_str = truncated or "—"
            else:
                status_str = "—"

            # Derived, not declared. The prose says why; these say where.
            act = activity.read(e.path, e.name)
            facts = []
            if act.plan:
                facts.append(f"plan {act.plan}")
            if act.touched:
                facts.append(f"{_ago(act.touched)} ago")
            if act.sessions:
                facts.append(f"{act.sessions} sessions")
            if act.packets:
                facts.append(f"{act.packets} packets")
            if act.dirty:
                facts.append(f"{act.dirty} uncommitted")

            click.echo(f"  {e.name:<32} {' · '.join(facts) or '—'}")
            if status_str != "—":
                click.echo(f"      {status_str}")
            if act.waiting:
                waiting.append((e.name, act))

    if waiting:
        click.echo("\nWaiting on you:")
        for name, act in waiting:
            if act.blocked:
                click.echo(f"  {name}: {act.blocked} packet(s) at a gate")
            for question in act.needs:
                click.echo(f"  {name}: {question.strip().splitlines()[0][:96]}")


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


@cli.command(name="view")
@click.option("--out", default="~/.orglens/view.html", help="Where to write the page.")
@click.option("--open/--no-open", "do_open", default=True, help="Open it after writing.")
def view_cmd(out: str, do_open: bool):
    """Render where every project stands, and open it.

    Joins what the tree knows (plans, packets, uncommitted work) with what scad
    knows (sessions, notes, open questions). Everything is recomputed here, so
    the page cannot drift the way a written status line does.
    """
    topo, _ = _load_topo()

    by_type: dict[str, list] = {}
    for entity in topo.list_entities():
        by_type.setdefault(entity.entity_type, []).append(entity)

    labels = {
        "research-program": "Research programs",
        "project": "Projects",
        "client": "Clients",
    }
    artifact_types = [
        (name, name.title() + "s") for name in topo.grammar.artifact_types
    ]

    groups = []
    for etype, label in labels.items():
        rows = []
        for entity in by_type.get(etype, []):
            et = topo.grammar.entity_types[etype]
            why = None
            if et.state_file and (entity.path / et.state_file).exists():
                why = extract_status((entity.path / et.state_file).read_text())
            rows.append(
                {
                    "name": entity.name,
                    "path": entity.path,
                    "why": why,
                    "activity": activity.read(entity.path, entity.name),
                    "artifacts": [
                        (heading, topo.find_artifacts(kind, entity.name))
                        for kind, heading in artifact_types
                    ],
                    # Root-level documents — backlog.md, handoffs, dated notes.
                    # The grammar has no artifact type for these, so they are
                    # invisible to `find`; they are often the entry point.
                    "docs": sorted(
                        f for f in entity.path.glob("*.md")
                        if not f.name.startswith(".")
                    ),
                    "dirs": sorted(
                        d for d in entity.path.iterdir()
                        if d.is_dir() and not d.name.startswith(".")
                    ),
                }
            )
        groups.append((label, rows))

    path = view.write(view.render(groups), Path(out))
    click.echo(f"wrote {path}")
    if do_open:
        os.system(f"open '{path}'")
