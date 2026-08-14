"""CLI — click commands for orglens.

Every command asks the grammar what kinds exist. None of them knows a noun:
that is what `orglens list --type deck` used to fail on, raising `KeyError`
because four modules carried their own copy of the type list.

Every command also speaks in units now, not folder position. A unit is
whatever has declared itself — via a marker, resolved through `Registry` —
and it can span several roots. Position places nothing any more; only a
declaration does.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import click

from orglens import activity, check as check_module, documents, reference, view
from orglens.config import Config
from orglens.declaration import MARKER
from orglens.snapshot import generate_snapshot
from orglens.state import read_status
from orglens.units import Registry
from orglens.workflow.cli import workflow as workflow_group


def _load_config() -> Config:
    """Load config from env var or default location."""
    config_path = os.environ.get("ORGLENS_CONFIG")
    if config_path:
        return Config.from_yaml(Path(config_path))
    return Config.load()


def _load_registry() -> tuple[Registry, Config]:
    """Load config + grammar + registry."""
    config = _load_config()
    return Registry(config.roots, config.load_grammar()), config


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


def _heading(kind: str) -> str:
    return kind.replace("-", " ").capitalize() + "s"


def _status_of(registry: Registry, unit):
    """The authored line for a unit, checked across every home in turn.

    A kind the grammar has never heard of still gets the driver document
    looked for — `documents_for` only adds detail beyond that when the
    grammar actually describes the kind.
    """
    declared = registry.grammar.documents_for(unit.kind)
    for path in unit.paths:
        status = read_status(path, declared)
        if status:
            return status
    return None


def _relative(path: Path, roots: list[Path]) -> Path:
    """`path`, relative to whichever root contains it.

    Resolved before compared: `~/Dropbox` is a symlink to
    `~/Library/CloudStorage/Dropbox` here, and an unresolved comparison would
    fail silently, falling back to the absolute path for no reason.
    """
    resolved = Path(path).resolve()
    for root in roots:
        try:
            return resolved.relative_to(Path(root).expanduser().resolve())
        except ValueError:
            continue
    return path


def _under_a_root(path: Path, roots: list[Path]) -> bool:
    """Whether `path` sits under any configured root.

    Resolved before compared, same as every other path-meets-root check here:
    `~/Dropbox` is a symlink to `~/Library/CloudStorage/Dropbox`, and an
    unresolved comparison would miss silently.
    """
    resolved = Path(path).resolve()
    return any(
        resolved == (r := Path(root).expanduser().resolve()) or resolved.is_relative_to(r)
        for root in roots
    )


def _unknown(kind: str, value: str, available) -> None:
    click.echo(
        f"Unknown {kind}: {value}. Available: {', '.join(available)}", err=True
    )
    sys.exit(1)


@cli.command()
@click.option("--type", "kind_filter", default=None, help="Filter by kind")
def list(kind_filter: str | None):
    """List everything in the tree."""
    registry, _ = _load_registry()
    units = registry.units()
    kinds_present = sorted({u.kind for u in units})

    if kind_filter is not None and kind_filter not in kinds_present:
        _unknown("kind", kind_filter, kinds_present)

    if kind_filter is not None:
        units = [u for u in units if u.kind == kind_filter]

    if not units:
        click.echo("Nothing found.")
        return

    by_kind: dict[str, list] = {}
    for unit in units:
        by_kind.setdefault(unit.kind, []).append(unit)

    for kind in sorted(by_kind):
        click.echo(f"\n{_heading(kind)}:")
        for unit in by_kind[kind]:
            status = _status_of(registry, unit)
            shown = f"  ({status.text})" if status else ""
            within = f"  [{unit.part_of}]" if unit.part_of else ""
            click.echo(f"  {unit.name}{shown}{within}")


@cli.command()
def status():
    """Where everything stands — the authored line, dated, beside derived facts."""
    registry, _ = _load_registry()
    units = registry.units()

    by_kind: dict[str, list] = {}
    for unit in units:
        by_kind.setdefault(unit.kind, []).append(unit)

    waiting = []

    for kind in sorted(by_kind):
        click.echo(f"\n{_heading(kind)}:")
        for unit in by_kind[kind]:
            act = activity.read(
                unit.paths, unit.name, home_names=[h.name for h in unit.homes]
            )
            facts = []
            # Counted from the grammar's own kinds, so a tree with different
            # documents reports on those instead of on nothing.
            for artifact_kind in registry.grammar.artifact_types:
                held = documents.find(registry, artifact_kind, unit)
                if held:
                    facts.append(
                        f"{len(held)} {artifact_kind}" + ("s" if len(held) > 1 else "")
                    )
            if act.touched:
                facts.append(f"{_ago(act.touched)} ago")
            if act.sessions:
                facts.append(f"{act.sessions} sessions")
            if act.packets:
                facts.append(f"{act.packets} packets")
            if act.dirty:
                facts.append(f"{act.dirty} uncommitted")

            click.echo(f"  {unit.name:<32} {' · '.join(facts) or '—'}")

            status_line = _status_of(registry, unit)
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
                waiting.append((unit.name, act))

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
@click.argument("unit_name", required=False)
def find(artifact_type: str, unit_name: str | None):
    """Find documents by kind, optionally scoped to one unit."""
    registry, _ = _load_registry()

    if artifact_type not in registry.grammar.artifact_types:
        _unknown("document kind", artifact_type, registry.grammar.artifact_types)

    found = documents.find(registry, artifact_type, unit_name)
    if not found:
        click.echo(f"No {artifact_type}s found.")
        return

    for item in found:
        shown = _relative(item.path, registry.roots)
        click.echo(f"  {item.name:<45} [{item.unit}]  {shown}")


def _write_marker(target: Path, name: str, kind: str | None, part_of: str | None) -> None:
    lines = [f"home: {name}", f"unit: {name}"]
    if kind:
        lines.append(f"kind: {kind}")
    if part_of:
        lines.append(f"part_of: {part_of}")
    lines.append("homes:")
    lines.append(f"  - {name}")
    (target / MARKER).write_text("\n".join(lines) + "\n")


@cli.command()
@click.argument("path")
@click.option("--kind", default=None, help="Label for this unit")
@click.option("--part-of", default=None, help="The unit this is part of")
def new(path: str, kind: str | None, part_of: str | None):
    """Create a unit: a directory, and the declaration that names it.

    Position no longer places anything — the path given is exactly where the
    directory lands. Its one home takes the directory's own name; more homes
    are a `.orglens.yml` edit away.
    """
    registry, config = _load_registry()
    target = Path(path).expanduser()

    if target.exists():
        click.echo(f"{target} already exists", err=True)
        sys.exit(1)

    target.mkdir(parents=True)
    _write_marker(target, target.name, kind, part_of)

    click.echo(f"Created {kind or 'unit'}: {target}")
    if not _under_a_root(target, registry.roots):
        # Warn, don't refuse: a unit outside every root is allowed to exist,
        # it is simply un-met until a root is added or someone works in it —
        # `Registry.at` reads a marker directly on the way up, roots or not.
        source = os.environ.get("ORGLENS_CONFIG") or "~/.config/orglens/config.yaml"
        click.echo(
            "note: this is under none of your configured roots, so `list`, "
            "`status`, `snapshot`, and `check` will not see it. Add its root "
            f"to {source}, or resolve it directly with `orglens where` while "
            "standing inside it."
        )
    _refresh_snapshot(registry, config)


def _home_line(home) -> str:
    shown = str(home.path) if home.path is not None else "absent"
    return f"{home.name:<40} {shown:<32} ({home.how})"


def _repo_line(home) -> str:
    """Whether this home's files are safely committed, and where.

    `orglens-adapt`'s precondition is exactly this: git is the whole backup
    model, and it only works if the current version is in it. A unit can
    span several repositories now, so this is one line per home rather than
    the single `repo:` line `where` used to print — dropping that block
    silently turned the safety gate into a no-op, since empty output reads
    as clean.
    """
    if home.path is None:
        return f"{home.name:<40} (home absent on this machine)"
    root = activity._repo_root(home.path)
    if root is None:
        return f"{home.name:<40} none — nothing is backing this up"
    dirty = activity._dirty(root, home.path)
    status = f"{dirty} uncommitted" if dirty else "clean"
    return f"{home.name:<40} {str(root):<32} ({status})"


@cli.command(name="where")
@click.argument("name", required=False)
def where_cmd(name: str | None):
    """Announce which roots, and which unit a name or this directory is in.

    Everything else assumes an answer to this. Anything acting on a unit — a
    skill restructuring a document, a check on whether work is committed —
    needs an absolute path and knows what it is acting on, and guessing
    either fails silently rather than loudly.
    """
    registry, _ = _load_registry()

    source = os.environ.get("ORGLENS_CONFIG") or "~/.config/orglens/config.yaml"
    click.echo(f"roots:  {registry.roots[0]}  (config: {source})")
    for extra in registry.roots[1:]:
        click.echo(f"        {extra}")

    here = Path.cwd().resolve()
    shown_here = None
    for root in registry.roots:
        try:
            shown_here = here.relative_to(Path(root).expanduser().resolve())
            break
        except ValueError:
            continue
    click.echo(
        f"here:   {shown_here}" if shown_here is not None else "here:   outside the roots"
    )

    if name:
        try:
            unit = registry.resolve(name)
        except ValueError as exc:
            click.echo(str(exc), err=True)
            sys.exit(1)
    else:
        unit = registry.at(here)
        if unit is None:
            click.echo("unit:   none — this directory is not inside a declared unit")
            return

    click.echo(f"unit:   {unit.name}  ({unit.kind})")
    if unit.part_of:
        click.echo(f"in:     {unit.part_of}")

    if not unit.homes:
        click.echo("homes:  (none declared)")
        return

    first, *rest = unit.homes
    click.echo(f"homes:  {_home_line(first)}")
    for home in rest:
        click.echo(f"        {_home_line(home)}")

    click.echo(f"repos:  {_repo_line(first)}")
    for home in rest:
        click.echo(f"        {_repo_line(home)}")


@cli.command(name="check")
def check_cmd():
    """Report where the tree has drifted from the grammar. Changes nothing."""
    registry, _ = _load_registry()
    report = check_module.run(registry)

    for drift in report.drifted:
        shown = _relative(drift.path, registry.roots)
        names = ", ".join(m.name for m in drift.missing)
        click.echo(f"{str(shown):<42} missing {names}")
        for missing in drift.missing:
            if missing.resembles:
                click.echo(
                    f"{'':<42} (has {missing.resembles} — likely the same thing)"
                )

    for path in report.undeclared:
        shown = _relative(path, registry.roots)
        click.echo(f"undeclared: {shown}")

    for unit_name, home_name in report.weak:
        click.echo(
            f"{unit_name}: home '{home_name}' resolved by directory name only "
            "— renaming it will detach"
        )

    for kind in report.unmatched:
        glob = registry.grammar.artifact_types[kind].find
        click.echo(f"no {kind} found anywhere (looked for {glob})")

    for dup in report.duplicates:
        shown = ", ".join(str(_relative(p, registry.roots)) for p in dup.paths)
        click.echo(f"{dup.name}: declared as a unit in more than one place — {shown}")

    for collision in report.collisions:
        shown = ", ".join(str(_relative(p, registry.roots)) for p in collision.paths)
        click.echo(
            f"{collision.unit}: home '{collision.home}' matches more than one "
            f"directory — {shown}"
        )

    if not report:
        click.echo("No drift.")


@cli.command()
@click.option("--stdout", is_flag=True, help="Print instead of writing")
def snapshot(stdout: bool):
    """Generate a snapshot of what is in the tree."""
    registry, config = _load_registry()

    if stdout:
        click.echo(generate_snapshot(registry, config))
        return
    output = config.snapshot_path
    generate_snapshot(registry, config, output_path=output)
    click.echo(f"Snapshot written to {output}")


@cli.command(name="reference")
@click.option("--out", default=None, help="Write here instead of printing")
def reference_cmd(out: str | None):
    """Render the grammar as the skill's vocabulary reference."""
    registry, _ = _load_registry()
    text = reference.render(registry.grammar)
    if out:
        path = Path(out).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        click.echo(f"Wrote {path}")
        return
    click.echo(text)


def _refresh_snapshot(registry: Registry, config: Config):
    """Silently refresh the snapshot after write operations."""
    try:
        generate_snapshot(registry, config, output_path=config.snapshot_path)
    except Exception:
        pass  # Non-critical — don't fail the main operation


@cli.command(name="view")
@click.option("--out", default="~/.orglens/view.html", help="Where to write the page.")
@click.option("--open/--no-open", "do_open", default=True, help="Open it after writing.")
@click.option("--base-url", default=None,
              help="Where the docs are served. Defaults to config docs_base_url.")
def view_cmd(out: str, do_open: bool, base_url: str | None):
    """Render where every unit stands, and open it.

    Joins what the tree knows (plans, packets, uncommitted work) with what scad
    knows (sessions, notes, open questions). Everything is recomputed here, so
    the page cannot drift the way a written status line does.
    """
    registry, config = _load_registry()

    by_kind: dict[str, list] = {}
    for unit in registry.units():
        by_kind.setdefault(unit.kind, []).append(unit)

    headings = [
        (kind, kind.title() + "s") for kind in registry.grammar.artifact_types
    ]

    groups = []
    for kind in sorted(by_kind):
        rows = []
        for unit in by_kind[kind]:
            status = _status_of(registry, unit)
            rows.append(
                {
                    "name": unit.name,
                    "path": unit.declared_at,
                    "why": status.text if status else None,
                    "activity": activity.read(
                        unit.paths, unit.name,
                        home_names=[h.name for h in unit.homes],
                    ),
                    "artifacts": [
                        (heading, documents.find(registry, artifact_kind, unit))
                        for artifact_kind, heading in headings
                    ],
                    # Top-level documents — backlogs, handoffs, dated notes. No
                    # document kind claims them, and they are often the way in.
                    "docs": documents.loose(unit),
                    "dirs": documents.subdirectories(unit),
                }
            )
        if rows:
            groups.append((_heading(kind), rows))

    ctx = {"docs_roots": registry.roots, "base_url": base_url or config.docs_base_url}
    path = view.write(view.render(groups, ctx), Path(out))
    click.echo(f"wrote {path}")
    if do_open:
        os.system(f"open '{path}'")
