"""CLI — click commands for orglens.

Every command asks the grammar what kinds exist. None of them knows a noun:
that is what `orglens list --type deck` used to fail on, raising `KeyError`
because four modules carried their own copy of the type list.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import click

from orglens import activity, check as check_module, reference, view
from orglens.config import Config
from orglens.snapshot import generate_snapshot
from orglens.state import read_status
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
    return Topology(config.docs_root, config.load_grammar()), config


@click.group()
def cli():
    """orglens — organizational lens for AI agents."""
    pass


cli.add_command(workflow_group, name="workflow")


def _ago(ts: float) -> str:
    """Coarse age. Precision past the hour is noise at this scale."""
    hours = (time.time() - ts) / 3600
    if hours < 24:
        return f"{hours:.0f}h"
    if hours < 24 * 60:
        return f"{hours / 24:.0f}d"
    return f"{hours / 720:.0f}mo"


def _heading(type_name: str) -> str:
    return type_name.replace("-", " ").capitalize() + "s"


def _status_of(topo: Topology, entity):
    return read_status(entity.path, topo.grammar.documents_for(entity.entity_type))


def _unknown(kind: str, value: str, available) -> None:
    click.echo(
        f"Unknown {kind}: {value}. Available: {', '.join(available)}", err=True
    )
    sys.exit(1)


@cli.command()
@click.option("--type", "entity_type", default=None, help="Filter by kind")
def list(entity_type: str | None):
    """List everything in the tree."""
    topo, _ = _load_topo()

    if entity_type is not None and entity_type not in topo.grammar.entity_types:
        _unknown("kind", entity_type, topo.grammar.entity_types)

    entities = topo.list_entities(entity_type)
    if not entities:
        click.echo("Nothing found.")
        return

    by_type: dict[str, list] = {}
    for entity in entities:
        by_type.setdefault(entity.entity_type, []).append(entity)

    for type_name in topo.grammar.entity_types:
        group = by_type.get(type_name, [])
        if not group:
            continue
        click.echo(f"\n{_heading(type_name)}:")
        for entity in group:
            status = _status_of(topo, entity)
            shown = f"  ({status.text})" if status else ""
            within = f"  [{entity.parent_name}]" if entity.parent_name else ""
            click.echo(f"  {entity.name}{shown}{within}")



@cli.command()
def status():
    """Where everything stands — the authored line, dated, beside derived facts."""
    topo, _ = _load_topo()
    entities = topo.list_entities()

    by_type: dict[str, list] = {}
    for entity in entities:
        by_type.setdefault(entity.entity_type, []).append(entity)

    waiting = []

    for type_name in topo.grammar.entity_types:
        group = by_type.get(type_name, [])
        if not group:
            continue
        click.echo(f"\n{_heading(type_name)}:")
        for entity in group:
            act = activity.read(entity.path, entity.name)
            facts = []
            # Counted from the grammar's own kinds, so a tree with different
            # documents reports on those instead of on nothing.
            for kind in topo.grammar.artifact_types:
                held = topo.find_artifacts(kind, entity.name)
                if held:
                    facts.append(f"{len(held)} {kind}" + ("s" if len(held) > 1 else ""))
            if act.touched:
                facts.append(f"{_ago(act.touched)} ago")
            if act.sessions:
                facts.append(f"{act.sessions} sessions")
            if act.packets:
                facts.append(f"{act.packets} packets")
            if act.dirty:
                facts.append(f"{act.dirty} uncommitted")

            click.echo(f"  {entity.name:<32} {' · '.join(facts) or '—'}")

            status_line = _status_of(topo, entity)
            if status_line:
                # Dated, because three of these are five months behind the tree.
                # A stale line is then a quote, not a claim about today.
                age = (
                    f"  [{_ago(status_line.edited)} old]"
                    if status_line.edited
                    else ""
                )
                click.echo(f'      "{status_line.text}"{age}')

            if act.waiting:
                waiting.append((entity.name, act))

    if waiting:
        click.echo("\nWaiting on you:")
        for name, act in waiting:
            if act.blocked:
                click.echo(f"  {name}: {act.blocked} packet(s) at a gate")
            for ask in act.needs:
                when = f" ({_ago(ask['at'])} ago)" if ask["at"] else ""
                first = ask["question"].strip().splitlines()[0]
                click.echo(f"  {name}: {first[:88]}{when}")


@cli.command()
@click.argument("artifact_type")
@click.argument("entity", required=False)
def find(artifact_type: str, entity: str | None):
    """Find documents by kind, optionally scoped to one entity."""
    topo, config = _load_topo()

    if artifact_type not in topo.grammar.artifact_types:
        _unknown("document kind", artifact_type, topo.grammar.artifact_types)

    artifacts = topo.find_artifacts(artifact_type, entity)
    if not artifacts:
        click.echo(f"No {artifact_type}s found.")
        return

    for artifact in artifacts:
        try:
            shown = artifact.path.relative_to(config.docs_root)
        except ValueError:
            shown = artifact.path
        click.echo(f"  {artifact.name:<45} [{artifact.entity_name}]  {shown}")


@cli.command()
@click.argument("entity_type")
@click.argument("name")
@click.option("--parent", default=None, help="Create it inside this entity")
def new(entity_type: str, name: str, parent: str | None):
    """Create an entity: a directory, plus whatever the grammar says it holds.

    Documents are written directly — the grammar describes how to name them and
    nothing parses a filename, so there is nothing for a command to compute.
    """
    topo, config = _load_topo()

    if entity_type not in topo.grammar.entity_types:
        _unknown("kind", entity_type, topo.grammar.entity_types)

    try:
        path = topo.scaffold_entity(entity_type, name, parent=parent)
    except ValueError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    try:
        shown = path.relative_to(config.docs_root)
    except ValueError:
        shown = path
    click.echo(f"Created {entity_type}: {shown}")
    _refresh_snapshot(topo, config)


@cli.command(name="where")
@click.argument("name", required=False)
def where_cmd(name: str | None):
    """Announce which tree, and which entity a name or this directory is in.

    Everything else assumes an answer to this. Anything acting on an entity —
    a skill restructuring a document, a check on whether work is committed —
    needs an absolute path and the repository holding it, and guessing either
    fails silently rather than loudly.
    """
    topo, config = _load_topo()

    source = os.environ.get("ORGLENS_CONFIG") or "~/.config/orglens/config.yaml"
    click.echo(f"tree:   {config.docs_root}  (config: {source})")

    here = Path.cwd().resolve()
    try:
        click.echo(f"here:   {here.relative_to(config.docs_root.resolve())}")
    except ValueError:
        click.echo("here:   outside the tree")

    if name:
        try:
            entity = topo.resolve(name)
        except ValueError as exc:
            click.echo(str(exc), err=True)
            sys.exit(1)
    else:
        entity = topo.at(here)
        if entity is None:
            click.echo("entity: none — this directory is not inside one")
            return

    click.echo(f"entity: {entity.name}  ({entity.entity_type})")
    if entity.parent_name:
        click.echo(f"in:     {entity.parent_name}")
    click.echo(f"path:   {entity.path}")

    root = activity._repo_root(entity.path)
    if root is None:
        click.echo("repo:   none — nothing is backing this up")
        return
    dirty = activity._dirty(root, entity.path)
    click.echo(f"repo:   {root}  ({dirty} uncommitted)" if dirty else f"repo:   {root}  (clean)")


@cli.command(name="check")
def check_cmd():
    """Report where the tree has drifted from the grammar. Changes nothing."""
    topo, config = _load_topo()
    report = check_module.run(topo)

    for drift in report.drifted:
        try:
            shown = drift.path.relative_to(config.docs_root)
        except ValueError:
            shown = drift.path
        names = ", ".join(m.name for m in drift.missing)
        click.echo(f"{str(shown):<42} missing {names}")
        for missing in drift.missing:
            if missing.resembles:
                click.echo(
                    f"{'':<42} (has {missing.resembles} — likely the same thing)"
                )

    for barren in report.barren:
        click.echo(f"pattern matches nothing: {barren}")

    if not report:
        click.echo("No drift.")


@cli.command()
@click.option("--stdout", is_flag=True, help="Print instead of writing")
def snapshot(stdout: bool):
    """Generate a snapshot of what is in the tree."""
    topo, config = _load_topo()

    if stdout:
        click.echo(generate_snapshot(topo, config))
        return
    output = config.snapshot_path
    generate_snapshot(topo, config, output_path=output)
    click.echo(f"Snapshot written to {output}")


@cli.command(name="reference")
@click.option("--out", default=None, help="Write here instead of printing")
def reference_cmd(out: str | None):
    """Render the grammar as the skill's vocabulary reference."""
    topo, _ = _load_topo()
    text = reference.render(topo.grammar)
    if out:
        path = Path(out).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        click.echo(f"Wrote {path}")
        return
    click.echo(text)


def _refresh_snapshot(topo: Topology, config: Config):
    """Silently refresh the snapshot after write operations."""
    try:
        generate_snapshot(topo, config, output_path=config.snapshot_path)
    except Exception:
        pass  # Non-critical — don't fail the main operation


@cli.command(name="view")
@click.option("--out", default="~/.orglens/view.html", help="Where to write the page.")
@click.option("--open/--no-open", "do_open", default=True, help="Open it after writing.")
@click.option("--base-url", default=None,
              help="Where the docs are served. Defaults to config docs_base_url.")
def view_cmd(out: str, do_open: bool, base_url: str | None):
    """Render where every entity stands, and open it.

    Joins what the tree knows (plans, packets, uncommitted work) with what scad
    knows (sessions, notes, open questions). Everything is recomputed here, so
    the page cannot drift the way a written status line does.
    """
    topo, config = _load_topo()

    by_type: dict[str, list] = {}
    for entity in topo.list_entities():
        by_type.setdefault(entity.entity_type, []).append(entity)

    headings = [
        (name, name.title() + "s") for name in topo.grammar.artifact_types
    ]

    groups = []
    for type_name in topo.grammar.entity_types:
        rows = []
        for entity in by_type.get(type_name, []):
            status = _status_of(topo, entity)
            rows.append(
                {
                    "name": entity.name,
                    "path": entity.path,
                    "why": status.text if status else None,
                    "activity": activity.read(entity.path, entity.name),
                    "artifacts": [
                        (heading, topo.find_artifacts(kind, entity.name))
                        for kind, heading in headings
                    ],
                    # Top-level documents — backlogs, handoffs, dated notes. No
                    # document kind claims them, and they are often the way in.
                    "docs": topo.documents(entity),
                    "dirs": topo.subdirectories(entity),
                }
            )
        if rows:
            groups.append((_heading(type_name), rows))

    ctx = {"docs_root": config.docs_root, "base_url": base_url or config.docs_base_url}
    path = view.write(view.render(groups, ctx), Path(out))
    click.echo(f"wrote {path}")
    if do_open:
        os.system(f"open '{path}'")
