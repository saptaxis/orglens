"""CLI — click commands for orglens.

Every command asks the grammar what kinds exist. None of them knows a noun:
`orglens list --type <kind>` used to raise `KeyError` for any kind the grammar
declared but the code did not, because four modules carried their own copy of
the type list.

Every command also speaks in units now, not folder position. A unit is
whatever has declared itself — via a marker, resolved through `Registry` —
and it can span several roots. Position places nothing any more; only a
declaration does.
"""

from __future__ import annotations

import builtins
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import click

from orglens import (activity, check as check_module, complete, documents, formats,
                     reference, sessions, tree as tree_mod, view)
from orglens.config import ORGLENS_HOME, Config
from orglens.declaration import MARKER
from orglens.events import (ATTRIBUTED, DISMISSED, EVENTS_DIR, Event, append,
                            this_machine)
from orglens.homes import Home, repo_of
from orglens.propose import Proposal, home_name, propose
from orglens.scadconfig import render as render_scadconfig
from orglens.snapshot import generate_snapshot, snapshot_data
from orglens.state import unit_status
from orglens.units import Registry, Unit
from orglens.workflow.cli import workflow as workflow_group

#: Where a rendered config lands unless `--out` says otherwise. A module-level
#: constant, not inlined, so a test can monkeypatch it rather than write to
#: the real `~/.scad`.
SCAD_CONFIGS_DIR = Path.home() / ".scad" / "configs"


def _load_config() -> Config:
    """Load config from env var or default location."""
    return Config.current()


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


def _count(n: int, noun: str) -> str:
    """`1 session`, not `1 sessions`. The counts sit inline in a dense line,
    where a wrong plural reads as a bug in the number rather than the grammar.
    """
    return f"{n} {noun}" + ("s" if n != 1 else "")


def _heading(kind: str) -> str:
    return kind.replace("-", " ").capitalize() + "s"


def _grouped(units: list, acts: dict) -> list[tuple[str, list]]:
    """Units by kind, most-recent-first within each group, and the groups
    themselves led by whichever holds the newest member.

    The question `list` and `status` answer is "what was I last working on",
    so alphabetical order is wrong at both levels: the kind that happens to
    sort first has no reason to be the one with live work in it. `acts` maps
    each unit to its `Activity` however it was obtained — `read` or the
    cheaper `peek` — so one ordering serves both commands. A unit missing
    from `acts` is not an error, just one with nothing to sort by.
    """
    by_kind: dict[str, list] = {}
    for unit in units:
        by_kind.setdefault(unit.kind, []).append(unit)
    for members in by_kind.values():
        members.sort(
            key=lambda u: activity.recency(acts.get(u, activity.Activity())),
            reverse=True,
        )
    ordered_kinds = sorted(
        by_kind,
        key=lambda k: activity.recency(acts.get(by_kind[k][0], activity.Activity())),
        reverse=True,
    )
    return [(kind, by_kind[kind]) for kind in ordered_kinds]


def _dated(act: activity.Activity) -> list[str]:
    """Each clock that says something the others don't, labelled.

    A bare `26d ago` never says which clock it is — commit, edit, or session
    — and printing two labels for the same moment is noise, not information.
    Mirrors the reasoning in `view.py`'s program: a clock within an hour of one
    already shown adds nothing.
    """
    clocks = []
    if act.touched:
        clocks.append(("committed", act.touched))
    if act.modified:
        clocks.append(("edited", act.modified))
    spoke = (act.last_turn or {}).get("at") or act.last_session
    if spoke:
        clocks.append(("session", spoke))
    shown: list[tuple[str, int]] = []
    out = []
    for label, ts in clocks:
        if any(abs(ts - t) <= 3600 for _, t in shown):
            continue
        shown.append((label, ts))
        out.append(f"{label} {_ago(ts)} ago")
    return out



def _sessions_by_unit(registry: Registry) -> tuple[list, dict[str, list]]:
    """Every session, and every unit's, from one pass over scad's export and
    the event log.

    One pass, not one per unit: `attributions` walks every shard and the
    export is one call, so a loop over thirty units would do the same work
    thirty times for the same answer.
    """
    every = sessions.all_sessions(registry, EVENTS_DIR)
    return every, {unit.name: sessions.for_unit(every, unit.name) for unit in registry.units()}


def _git_paths(registry: Registry, units: list) -> list[Path]:
    """Every path `status`/`view` will ask git about: each home, and each
    document the status line may be read from."""
    out: list[Path] = []
    for unit in units:
        out.extend(unit.paths)
        for home in unit.paths:
            for d in registry.grammar.documents_for(unit.kind):
                found = formats.existing(home, d, registry.grammar.format)
                if found is not None:
                    out.append(found)
    return out


def _warm(registry: Registry, units: list, every: list) -> dict[str, list[dict]]:
    """Everything `status` and `view` will ask a subprocess or a file walk
    for, fetched at once: git per home and driver document, the newest
    mtime per home, and `scad notes ls --about` per unit. Independent and
    mostly waiting, so one pool runs them side by side; in series they were
    most of a 10s `status`. Returns the notes by unit; the rest is cached.
    """
    # One read of scad's notes export for the whole tree, joined here. It
    # was one `--about` subprocess per unit, which is 31 launches to read
    # one file; the join itself needs the sessions, so the caller passes
    # them in.
    notes: dict[str, list[dict]] = {}

    def fetch(_: None = None) -> None:
        notes.update(activity.notes_by_unit([u.name for u in units], every))

    activity.prefetch(_git_paths(registry, units), extra=[(fetch, None)])
    return notes


def _status_of(registry: Registry, unit):
    """The authored line for a unit: the driver in any home first, then any
    other document (`state.unit_status`).

    A kind the grammar has never heard of still gets the driver document
    looked for — `documents_for` only adds detail beyond that when the
    grammar actually describes the kind.
    """
    declared = registry.grammar.documents_for(unit.kind)
    return unit_status(unit.paths, declared, registry.grammar.format)


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


def _under(registry: Registry, name: str | None) -> list[Unit]:
    """Every unit, or one unit and its subtree. An unknown name is the same
    error `resolve` gives everywhere else."""
    if name is None:
        return registry.units()
    try:
        return registry.below(name)
    except ValueError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)


UNDER_HELP = "Only this unit and the units under it in the tree."


@cli.command()
@click.option("--type", "kind_filter", default=None, help="Filter by kind")
@click.option("--under", default=None, metavar="UNIT", help=UNDER_HELP,
              shell_complete=complete.units)
def list(kind_filter: str | None, under: str | None):
    """List everything in the tree."""
    registry, _ = _load_registry()
    units = _under(registry, under)
    kinds_present = sorted({u.kind for u in registry.units()})

    if kind_filter is not None and kind_filter not in kinds_present:
        _unknown("kind", kind_filter, kinds_present)

    if kind_filter is not None:
        units = [u for u in units if u.kind == kind_filter]

    if not units:
        click.echo("Nothing found.")
        return

    every, by_unit = _sessions_by_unit(registry)

    # `peek`, not `read`: the per-home git calls `read` makes for the last
    # commit and the dirty count are the entire gap between `list` at 1.9s
    # and `status` at 5.5s on the real tree, and sorting needs neither.
    acts = {
        unit: activity.peek(unit.paths, unit.name, sessions=by_unit[unit.name])
        for unit in units
    }

    for kind, members in _grouped(units, acts):
        click.echo(f"\n{_heading(kind)}:")
        for unit in members:
            status = _status_of(registry, unit)
            shown = f"  ({status.text})" if status else ""
            within = f"  [{unit.part_of}]" if unit.part_of else ""
            dated = _dated(acts[unit])
            when = f"  {' · '.join(dated)}" if dated else ""
            click.echo(f"  {unit.name}{shown}{within}{when}")


@cli.command()
@click.option("--under", default=None, metavar="UNIT", help=UNDER_HELP,
              shell_complete=complete.units)
def status(under: str | None):
    """Where everything stands — the authored line, dated, beside derived facts."""
    registry, _ = _load_registry()
    units = _under(registry, under)

    every, by_unit = _sessions_by_unit(registry)
    notes = _warm(registry, units, every)
    acts = {
        unit: activity.read(unit.paths, unit.name, sessions=by_unit[unit.name],
                            notes=notes[unit.name])
        for unit in units
    }

    waiting = []

    for kind, members in _grouped(units, acts):
        click.echo(f"\n{_heading(kind)}:")
        for unit in members:
            act = acts[unit]
            facts = []
            # Counted from the grammar's own kinds, so a tree with different
            # documents reports on those instead of on nothing.
            for artifact_kind in registry.grammar.artifact_types:
                held = documents.find(registry, artifact_kind, unit)
                if held:
                    facts.append(
                        _count(len(held), artifact_kind)
                    )
            facts.extend(_dated(act))
            if act.sessions:
                facts.append(_count(act.sessions, "session"))
            if act.packets:
                facts.append(_count(act.packets, "packet"))
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


@cli.command(name="tree")
@click.argument("unit_name", required=False, shell_complete=complete.units)
@click.option("--json", "as_json", is_flag=True,
              help="The same tree as nested data.")
def tree_cmd(unit_name: str | None, as_json: bool):
    """The units as a tree: each under the unit its `part_of` names.

    Every top-level unit and what is under it, or one unit's subtree. A
    `part_of` naming no unit, and a cycle, leave a unit top-level and are
    marked; `check` reports both.
    """
    registry, _ = _load_registry()
    units = registry.units()
    if not units:
        click.echo("Nothing found.")
        return
    by_name: dict[str, Unit] = {}
    for u in units:
        by_name.setdefault(u.name, u)
    shape = registry.tree()
    start = None
    if unit_name is not None:
        try:
            start = registry.resolve(unit_name).name
        except ValueError as exc:
            click.echo(str(exc), err=True)
            sys.exit(1)

    def status_of(name: str) -> str | None:
        found = _status_of(registry, by_name[name])
        return found.text if found else None

    if as_json:
        def node(name: str) -> dict:
            return {"name": name, "kind": by_name[name].kind, "status": status_of(name)}
        tops = [start] if start is not None else shape.top
        click.echo(json.dumps([tree_mod.nested(shape, t, node) for t in tops], indent=2))
        return

    def label(name: str) -> str:
        kind = by_name[name].kind
        text = f"{name}  ({kind})" if kind else name
        status = status_of(name)
        return f"{text}  {status}" if status else text

    width = shutil.get_terminal_size().columns if sys.stdout.isatty() else None
    for line in tree_mod.draw(shape, label, start=start):
        click.echo(line[:width] if width else line)


@cli.command()
@click.argument("artifact_type", shell_complete=complete.kinds)
@click.argument("unit_name", required=False, shell_complete=complete.units)
@click.option("--in", "within", default=None, metavar="DIR",
              help="Scope to directories of this name instead of the kind's own container.")
@click.option("--grep", "pattern", default=None, metavar="TEXT",
              help="Only documents whose text contains this; shows the matching lines.")
@click.option("--since", "window", default=None, metavar="WINDOW",
              help="Only documents touched within this long: 2w, 90d, 6h.")
@click.option("--waiting", is_flag=True,
              help="Only packets with a gate open, with the question.")
@click.option("--under", default=None, metavar="UNIT", help=UNDER_HELP,
              shell_complete=complete.units)
@click.option("--json", "as_json", is_flag=True)
def find(artifact_type: str, unit_name: str | None, within: str | None,
         pattern: str | None, window: str | None, waiting: bool, under: str | None,
         as_json: bool):
    """Find documents by kind, optionally scoped to one unit.

    The kind is the grammar's word for where to look; `--in` is the tree's
    word for a directory the grammar has no name for yet. `--grep` reads the
    documents found and keeps the ones that mention the text.
    """
    registry, _ = _load_registry()

    if artifact_type not in registry.grammar.artifact_types:
        _unknown("document kind", artifact_type, registry.grammar.artifact_types)

    if unit_name is not None and under is not None:
        raise click.UsageError("give a unit, or --under a unit, not both")
    try:
        if under is not None:
            found = [d for one in _under(registry, under)
                     for d in documents.find(registry, artifact_type, one, within=within)]
        else:
            found = documents.find(registry, artifact_type, unit_name, within=within)
    except ValueError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)
    if pattern is not None:
        found = documents.grep(found, pattern)
    if window is not None:
        try:
            found = documents.since(found, documents.parse_window(window))
        except ValueError as exc:
            click.echo(str(exc), err=True)
            sys.exit(1)
    if waiting:
        found = documents.waiting(found)

    if as_json:
        click.echo(json.dumps([
            {"name": d.name, "kind": d.kind, "unit": d.unit, "path": str(d.path),
             "matches": [*d.matches]}
            for d in found
        ]))
        return
    if not found:
        click.echo(f"No {artifact_type}s found.")
        return

    for item in found:
        shown = _relative(item.path, registry.roots)
        click.echo(f"  {item.name:<45} [{item.unit}]  {shown}")
        for hit in item.matches[:5]:
            where = Path(hit["file"]).name if item.path.is_dir() else ""
            click.echo(f"      {where}:{hit['line']}  {hit['text'][:100]}")
        if len(item.matches) > 5:
            click.echo(f"      +{len(item.matches) - 5} more")


def _write_declaration(proposal: Proposal, path: Path, part_of: str | None) -> None:
    """A confirmed proposal, written as a marker, with the parent the person
    gave (`_parent_for`) rather than the one position suggested."""
    _write_marker(
        path,
        home=proposal.homes[0],
        unit=proposal.unit,
        kind=proposal.kind,
        part_of=part_of,
        homes=proposal.homes,
    )


def _seed(target: Path, kind: str | None, registry: Registry, fmt, driver: str) -> None:
    """Every file the kind's `structure:` declares, other than the driver,
    seeded with a title and what it is for --- the grammar's own words --- so
    whoever opens the folder knows where things go. Folders are not made."""
    declared = registry.grammar.entity_types.get(kind or "")
    if declared is None:
        return
    for key, means in declared.files.items():
        stem = formats.stem(key)
        if stem == driver:
            continue
        path = target / f"{stem}{fmt.suffix}"
        if not path.exists():
            title = stem.replace("-", " ").capitalize()
            path.write_text(fmt.seed(title, " ".join((means or "").split())))


def _interactive() -> bool:
    """Whether a person is at the other end. An agent or a script is not,
    and gets no parent it did not pass."""
    return sys.stdin.isatty()


def _parent_for(path: Path, registry: Registry, given: str | None) -> str | None:
    """The `part_of` to write for a new marker at `path`.

    Position suggests, a person decides. `--part-of` is written as given (a
    unit that does not exist is refused, as a typo would be). Otherwise, when
    a unit contains the folder and a person is at the terminal, they are
    asked, default no. Otherwise none: membership is never inferred.
    """
    if given is not None:
        try:
            return registry.resolve(given).name
        except ValueError as exc:
            click.echo(str(exc), err=True)
            sys.exit(1)
    above = path.parent
    container = registry.at(above) if above != path else None
    if container is None or not _interactive():
        return None
    kind = f" ({container.kind})" if container.kind else ""
    asked = f"{path.name} sits inside {container.name}{kind}. Part of {container.name}?"
    return container.name if click.confirm(asked, default=False) else None


def _show(proposal: Proposal) -> None:
    """Show the inference and what each part was inferred from.

    A human confirming a guess needs to see the guess's reasoning, or they are
    not confirming — they are trusting.
    """
    click.echo(f"  unit:    {proposal.unit}")
    click.echo(f"  kind:    {proposal.kind or '(unknown)':<24}"
               f"  {proposal.why.get('kind', '')}")
    click.echo(f"  homes:   {proposal.why.get('homes', '')}")
    for home in proposal.homes:
        click.echo(f"    - {home}")


@cli.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option("--yes", is_flag=True, help="Write it without asking.")
@click.option("--part-of", default=None, metavar="UNIT", shell_complete=complete.units,
              help="The unit this is part of. Never taken from position unasked.")
def declare(path: str, yes: bool, part_of: str | None):
    """Declare an existing directory as a unit, from what it looks like.

    Everything proposed comes from position, which is a good suggestion and a
    bad fact — so it is shown with its reasoning and confirmed, never written
    unattended.
    """
    registry, _ = _load_registry()
    target = Path(path).expanduser().resolve()

    if (target / MARKER).exists():
        click.echo(f"{target} is already declared.", err=True)
        sys.exit(1)

    proposal = propose(target, registry)
    _show(proposal)
    parent = _parent_for(target, registry, part_of)

    if not yes and not click.confirm("write this?", default=True):
        click.echo("nothing written.")
        return

    _write_declaration(proposal, target, parent)
    click.echo(f"declared {proposal.unit}")


def _write_marker(
    target: Path,
    *,
    home: str,
    unit: str,
    kind: str | None,
    part_of: str | None,
    homes: tuple[str, ...],
) -> None:
    """Write the marker. Field order is the reading order, not alphabetical.

    `home:` names this exact directory, and writing that fact down promotes it
    to the `marker` rung of `homes.resolve_home`'s ladder. Without it the
    ladder re-derives a name from scratch, and can land this directory on the
    same name as a same-named sibling home — collapsing two homes onto one
    directory and losing the other.

    One writer for both `new` and `declare`, because they write the same file
    format and had drifted into two shapes.
    """
    lines = [f"home: {home}", f"unit: {unit}"]
    if kind:
        lines.append(f"kind: {kind}")
    if part_of:
        lines.append(f"part_of: {part_of}")
    lines.append("homes:")
    lines += [f"  - {h}" for h in homes]
    (target / MARKER).write_text("\n".join(lines) + "\n")


@cli.command()
@click.argument("path")
@click.option("--kind", default=None, help="Label for this unit")
@click.option("--part-of", default=None, help="The unit this is part of")
@click.option("--home", "extra_homes", multiple=True,
              help="Another home this unit lives in. Repeatable.")
def new(path: str, kind: str | None, part_of: str | None, extra_homes: tuple[str, ...]):
    """Create a unit: a directory, and the declaration that names it.

    Position no longer places anything — the path given is exactly where the
    directory lands.

    The directory names itself the way `declare` would — repository-relative,
    so a unit inside a checkout is `<repo>/<path within it>`. Pass `--home`
    for each further place the work lives; a unit findable from both its code
    and its documents is the shape the model is for, and it should not need a
    hand-edit afterwards.
    """
    registry, config = _load_registry()
    target = Path(path).expanduser()

    if target.exists():
        click.echo(f"{target} already exists", err=True)
        sys.exit(1)
    # Asked before anything is created, so a refused `--part-of` leaves
    # nothing behind.
    parent = _parent_for(target.resolve(), registry, part_of)

    target.mkdir(parents=True)
    # Derived after the directory exists: the name depends on the repository
    # it landed in, which is a fact about the filesystem, not the argument.
    mine = home_name(target.resolve(), registry)
    homes = (mine,) + tuple(h for h in extra_homes if h != mine)
    _write_marker(target, home=mine, unit=target.name, kind=kind,
                  part_of=parent, homes=homes)
    # The driver in the grammar's format (R3, R12). The stub and the status
    # reader come from the same format module, so they cannot drift (R8).
    fmt = formats.get(registry.grammar.format)
    base = formats.stem(registry.grammar.driver)
    driver = target / f"{base}{fmt.suffix}"
    driver.write_text(fmt.stub(base.replace("-", " ").capitalize(), target.name,
                               time.strftime("%Y-%m-%d")))
    _seed(target, kind, registry, fmt, base)
    registered = _register_in_nav(target)

    click.echo(f"Created {kind or 'unit'}: {target}")
    click.echo("next:")
    click.echo(f"  write {driver.name}: the status line, what it is, where its state lives")
    if registered is not None:
        click.echo(f"  added to {registered}" if registered else
                   "  the parent .nav.yml lists children by name; add this one")
    click.echo(f"  orglens start {target.name}   # a session on it, attributed before its first turn")
    if not _under_a_root(target, registry.roots):
        # Warn, don't refuse: a unit outside every root is allowed to exist,
        # it is simply un-met until a root is added or someone works in it —
        # `Registry.at` reads a marker directly on the way up, roots or not.
        source = os.environ.get("ORGLENS_CONFIG") or str(ORGLENS_HOME / "config.yaml")
        click.echo(
            "note: this is under none of your configured roots, so `list`, "
            "`status`, `snapshot`, and `check` will not see it. Add its root "
            f"to {source}, or resolve it directly with `orglens where` while "
            "standing inside it."
        )
    _refresh_snapshot(registry, config)


def _register_in_nav(target: Path) -> str | bool | None:
    """Add the unit to a parent `.nav.yml` that lists children by name.

    mkdocs-awesome-nav: a parent nav with an explicit list has no glob, so
    a new unit is invisible to the site until it is added, and nothing said
    so. Returns the nav's path when the line was added, False when the nav
    is explicit but could not be edited safely, None when there is no such
    nav or it carries a glob and needs nothing.
    """
    nav = target.parent / ".nav.yml"
    if not nav.is_file():
        return None
    try:
        text = nav.read_text()
    except OSError:
        return None
    lines = text.splitlines(keepends=True)
    items = [l for l in lines if l.startswith("  - ")]
    if not items or any("*" in l for l in items):
        return None
    if any(l.strip() == f"- {target.name}" for l in items):
        return None
    if not all(l.rstrip("\n").startswith("  - ") and ":" not in l for l in items):
        return False
    last = max(i for i, l in enumerate(lines) if l.startswith("  - "))
    lines.insert(last + 1, f"  - {target.name}\n")
    nav.write_text("".join(lines))
    return str(nav)


#: Why a home resolves nowhere. With roots listed one by one, the likely cause
#: is a repository left off the list; a home not cloned here is legitimate.
ABSENT = ("is under none of your roots on this machine — "
          "list its repository in roots, or it is not cloned here")


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
        return f"{home.name:<40} ({ABSENT})"
    root = activity._repo_root(home.path)
    if root is None:
        return f"{home.name:<40} none — nothing is backing this up"
    dirty = activity._dirty(root, home.path)
    status = f"{dirty} uncommitted" if dirty else "clean"
    return f"{home.name:<40} {str(root):<32} ({status})"


@cli.command(name="where")
@click.argument("name", required=False, shell_complete=complete.units)
def where_cmd(name: str | None):
    """Announce which roots, and which unit a name or this directory is in.

    Everything else assumes an answer to this. Anything acting on a unit — a
    skill restructuring a document, a check on whether work is committed —
    needs an absolute path and knows what it is acting on, and guessing
    either fails silently rather than loudly.
    """
    registry, _ = _load_registry()

    source = os.environ.get("ORGLENS_CONFIG") or str(ORGLENS_HOME / "config.yaml")
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
    report = check_module.run(registry, sessions.all_sessions(registry, EVENTS_DIR))

    for drift in report.drifted:
        names = ", ".join(m.name for m in drift.missing)
        click.echo(f"{drift.entity:<42} missing {names}")
        for missing in drift.missing:
            if missing.resembles:
                click.echo(
                    f"{'':<42} (has {missing.resembles} — likely the same thing)"
                )

    for path in report.undeclared:
        shown = _relative(path, registry.roots)
        click.echo(f"undeclared: {shown}")

    for unit_name, home_name, how in report.weak:
        if how == "remote":
            click.echo(
                f"{unit_name}: home '{home_name}' resolved by a git remote's "
                "repository name only — an owner collision would resolve silently"
            )
        else:
            click.echo(
                f"{unit_name}: home '{home_name}' resolved by directory name only "
                "— renaming it will detach"
            )

    for unit_name, home_name in report.absent:
        click.echo(f"{unit_name}: home '{home_name}' {ABSENT}")

    for unit_name, parent in report.unknown_parents:
        click.echo(f"{unit_name}: part_of '{parent}' is no unit")
    for loop in report.cycles:
        click.echo("part_of cycle: " + " > ".join([*loop, loop[0]]))
    for unit_name, container, parent in report.misplaced:
        said = f"says part_of {parent}" if parent else "states no parent"
        click.echo(f"{unit_name}: sits inside {container}'s home, but {said}")

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

    for shared in report.shared:
        names = " and ".join([", ".join(shared.units[:-1]), shared.units[-1]])
        click.echo(
            f"home '{shared.home}' is declared on {names} — inside it, "
            f"`where` answers {shared.units[0]}"
        )

    for row in report.unlisted:
        click.echo(
            f"{row.unit}: not in {_relative(row.nav, registry.roots)}, which lists "
            "its siblings by name; the site will not show it"
        )

    for row in report.stale:
        click.echo(
            f"{row.unit}: the status line is {row.days} days older than the newest edit; "
            "rewrite it if it is no longer true"
        )

    for row in report.held:
        click.echo(
            f"{row.session[:8]}: open in more than one process "
            f"({', '.join(row.panes)}); two writers on one transcript fork it"
        )

    for row in report.undescribed:
        shown = _relative(row.path, registry.roots)
        click.echo(
            f"{row.unit}: {shown} holds {_count(row.count, 'document')} the grammar "
            "has no word for; they are found, without a kind"
        )

    for row in report.twins:
        shown = _relative(row.path, registry.roots)
        click.echo(
            f"{row.unit}: {shown} is written in two formats; only the "
            f"{registry.grammar.format} one is read — keep one"
        )

    if not report:
        click.echo("No drift.")


@cli.command()
@click.option("--stdout", is_flag=True, help="Print instead of writing")
@click.option("--check", is_flag=True,
              help="Say whether the written snapshot is older than the tree; exit 1 if so.")
@click.option("--type", "kind", default=None, help="Only units of this kind.",
              shell_complete=complete.kinds)
@click.option("--unit", "unit_name", default=None, help="Only this unit and the units under it.",
              shell_complete=complete.units)
@click.option("--json", "as_json", is_flag=True,
              help="The same facts as data, for a program to compose with.")
def snapshot(stdout: bool, check: bool, kind: str | None, unit_name: str | None,
             as_json: bool):
    """Generate a snapshot of what is in the tree.

    `--type` and `--unit` narrow it; a narrowed snapshot goes to stdout,
    never to the cache, which always holds the whole tree.
    """
    registry, config = _load_registry()

    if check:
        sys.exit(_snapshot_check(registry, config))
    if kind is not None and kind not in {u.kind for u in registry.units()}:
        _unknown("kind", kind, sorted({u.kind for u in registry.units()}))
    if as_json:
        # Always to stdout: the cache holds the document a session reads, and
        # a second file to keep in step with it would be one more thing that
        # can be stale.
        try:
            data = snapshot_data(registry, config, kind=kind, unit=unit_name)
        except ValueError as exc:
            click.echo(str(exc), err=True)
            sys.exit(1)
        click.echo(json.dumps(data, indent=2))
        return
    if stdout or kind is not None or unit_name is not None:
        try:
            click.echo(generate_snapshot(registry, config, kind=kind, unit=unit_name))
        except ValueError as exc:
            click.echo(str(exc), err=True)
            sys.exit(1)
        return
    output = _write_snapshot(registry, config)
    click.echo(f"Snapshot written to {output}")


def _snapshot_check(registry: Registry, config: Config) -> int:
    """Whether the snapshot predates any declaration or driver document.

    Those are what the snapshot renders; a document deeper in a unit
    changes nothing it shows. A missing snapshot is stale, not an error.
    """
    output = config.snapshot_path
    if not output.exists():
        click.echo(f"stale: no snapshot at {output}")
        return 1
    data = config.snapshot_json_path
    if not data.exists() or data.stat().st_mtime < output.stat().st_mtime:
        click.echo(f"stale: {data} is missing or older than {output}; completion reads it")
        return 1
    written = output.stat().st_mtime
    newest: tuple[float, Path] | None = None
    for unit in registry.units():
        candidates = [unit.declared_at / MARKER]
        candidates += [f for p in unit.paths
                       for d in registry.grammar.documents_for(unit.kind)
                       if (f := formats.existing(p, d, registry.grammar.format)) is not None]
        for path in candidates:
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if newest is None or mtime > newest[0]:
                newest = (mtime, path)
    if newest is not None and newest[0] > written:
        shown = _relative(newest[1], registry.roots)
        click.echo(f"stale: {shown} changed after the snapshot was written")
        return 1
    click.echo(f"fresh: {output}")
    return 0


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


def _repo_keys(unit: Unit) -> list[str]:
    """The repository names `render` would produce, in first-seen order —
    used only to validate `--workdir` before writing, never by `render`
    itself, which stays pure.
    """
    keys: list[str] = []
    for home in unit.homes:
        if home.path is None:
            continue
        key = repo_of(home.name)
        if key not in keys:
            keys.append(key)
    return keys


@cli.command(name="config")
@click.argument("unit_name", shell_complete=complete.units)
@click.option("--workdir", default=None, help="Which repository is the workdir.")
@click.option("--out", default=None, help="Write here instead of ~/.scad/configs/<unit>.yml")
def config_cmd(unit_name: str, workdir: str | None, out: str | None):
    """Render a unit's homes into the scad config for a container.

    The one thing orglens writes under `~/.scad`: a config file scad reads,
    never its index or its launch records. Every other command in this tree
    only reads scad's records — this is the deliberate exception, made once,
    here.
    """
    registry, _ = _load_registry()
    try:
        unit = registry.resolve(unit_name)
    except ValueError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    repos = _repo_keys(unit)
    if workdir is not None and workdir not in repos:
        click.echo(
            f"Unknown repository '{workdir}'. {unit.name} has: "
            + ", ".join(repos),
            err=True,
        )
        sys.exit(1)

    text = render_scadconfig(unit, workdir=workdir)

    if out:
        path = Path(out).expanduser()
    else:
        path = SCAD_CONFIGS_DIR / f"{unit.name}.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    click.echo(str(path))


def _write_snapshot(registry: Registry, config: Config) -> Path:
    """The snapshot for sessions to read, and beside it the same facts as
    JSON for completion to read (R14)."""
    output = config.snapshot_path
    generate_snapshot(registry, config, output_path=output)
    config.snapshot_json_path.write_text(json.dumps(snapshot_data(registry, config)))
    return output


def _refresh_snapshot(registry: Registry, config: Config):
    """Silently refresh the snapshot after write operations."""
    try:
        _write_snapshot(registry, config)
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

    every, by_unit = _sessions_by_unit(registry)
    notes = _warm(registry, [u for us in by_kind.values() for u in us], every)

    groups = []
    for kind in sorted(by_kind):
        rows = []
        for unit in by_kind[kind]:
            status = _status_of(registry, unit)
            rows.append(
                {
                    "name": unit.name,
                    "kind": unit.kind,
                    "part_of": unit.part_of,
                    "path": unit.declared_at,
                    "why": status.text if status else None,
                    "why_edited": status.edited if status else None,
                    "activity": activity.read(
                        unit.paths, unit.name, sessions=by_unit[unit.name],
                        notes=notes[unit.name],
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

    ctx = {"docs_roots": registry.roots, "base_url": base_url or config.docs_base_url,
           "link": config.view_link}
    page = view.render(groups, ctx, unattributed=sessions.unattributed(every))
    path = view.write(page, Path(out))
    click.echo(f"wrote {path}")
    if do_open:
        os.system(f"open '{path}'")


# ── sessions ─────────────────────────────────────────────────────────────


def _scad(argv: list[str]) -> int:
    """Run scad with the terminal attached, and return its exit code.

    Not captured: `session resume` attaches a tmux pane or execs the agent,
    and either needs the tty. A missing scad is an ordinary failure here,
    reported by exit code rather than raised.
    """
    try:
        return subprocess.run(["scad", *argv]).returncode
    except OSError:
        click.echo("scad is not installed, or not on PATH.", err=True)
        return 1


def _find_session(every: list, prefix: str):
    """The one session whose id is `prefix` or starts with it.

    Returns `(session, [])` on a unique match, `(None, matches)` otherwise:
    the caller says which ids matched, and refuses. Prefix matching is what
    lets a human type the eight characters a listing shows.
    """
    exact = [s for s in every if s.id == prefix]
    if exact:
        return exact[0], []
    matches = [s for s in every if s.id.startswith(prefix)]
    if len(matches) == 1:
        return matches[0], []
    return None, matches


def _session_line(s, show_how: bool = True, short: dict | None = None) -> str:
    when = _ago(s.when // 1000) + " ago" if s.when else "—"
    sid = (short or {}).get(s.id, s.id[:8])
    if s.live:
        state = "● live"
    elif s.open:
        state = "resumable"
    else:
        state = ""
    how = (s.how or "") if show_how else ""
    return (
        f"  {sid:<10} {s.agent:<6} {when:>8} {_count(s.turns, 'turn'):>10}  "
        f"{how:<12} {state:<10} {s.label or ''}"
    )


def _why_line(s) -> str | None:
    """The person's own words about this session, wherever it is listed.

    `_session_detail` carries it for the unclaimed, where a second line is
    always printed. An attributed session gets one line, so the why needs its
    own or the field is visible only until it is answered — which is the
    write-only defect it was added to fix.
    """
    return f"{'':<13}why: {s.why[:110]}" if s.why else None


def _session_detail(s) -> str:
    """A second line for a session nobody has claimed: where it ran and
    the last thing said, which is what deciding whose it is needs.

    A `--why` outranks the last turn when there is one. The person wrote it
    about this session on purpose; the last turn is only the newest thing
    that happened to be said.
    """
    said = (s.last_turn or {}).get("text") or ""
    said = " ".join(said.split())[:110]
    line = f"{'':<13}{sessions.where(s.cwd)}"
    if s.why:
        line += f"  ·  why: {s.why[:110]}"
    elif said:
        line += f"  ·  {said}"
    return line


@cli.command(name="notes")
@click.argument("unit_name", required=False, shell_complete=complete.units)
@click.option("--mentions/--no-mentions", "want_mentions", default=True,
              help="Include notes that only name the unit. On by default.")
def notes_cmd(unit_name: str | None, want_mentions: bool):
    """What was written down about a unit, newest first.

    Three ways a note reaches a unit, shown per row. *written here* is the
    exact one: the note's session is the unit's, by attribution or by
    containment. *filed here* is scad's project for it, a directory name.
    *mentions this* is the name in the note's topic, tags or entities —
    the weakest, and the only one before this.

    The notes themselves stay in scad; this reads its export and joins.
    """
    registry, _ = _load_registry()
    every = sessions.all_sessions(registry, EVENTS_DIR)

    if unit_name:
        try:
            unit = registry.resolve(unit_name)
        except ValueError as exc:
            click.echo(str(exc), err=True)
            sys.exit(1)
        names = [unit.name]
    else:
        names = [u.name for u in registry.units()]

    found = activity.notes_by_unit(names, every)
    shown = 0
    for name in names:
        rows = [n for n in found[name]
                if want_mentions or n.get("how") != activity.MENTIONS]
        if not rows:
            continue
        shown += len(rows)
        click.echo(f"\n{name}:")
        for n in rows:
            when = _ago(n["at"]) if n.get("at") else "—"
            click.echo(
                f"  {str(n['topic'] or ''):<28} {when:>8}  "
                f"{str(n.get('how') or ''):<13} {str(n['title'] or '')[:88]}"
            )
    if not shown:
        click.echo(f"{unit_name or 'every unit'}: no notes")


@cli.command(name="sessions")
@click.argument("unit_name", required=False, shell_complete=complete.units)
@click.option("--none", "only_none", is_flag=True,
              help="Only the sessions that belong to no unit.")
@click.option("--all", "everything", is_flag=True,
              help="Include sessions with no turns yet.")
@click.option("--triage", is_flag=True,
              help="Decide the unclaimed sessions, grouped by directory.")
@click.option("--one-by-one", "one_by_one", is_flag=True,
              help="With --triage: a prompt per session instead of per group.")
@click.option("--groups", "as_groups", is_flag=True,
              help="Count the unclaimed by the directory they ran in.")
@click.option("--dismissed", "only_dismissed", is_flag=True,
              help="The sessions someone said belong to no unit.")
@click.option("--from", "from_file", default=None, metavar="FILE",
              help="Apply decisions from a `--none --json` file you edited.")
@click.option("--json", "as_json", is_flag=True,
              help="The rows as JSON, each with a `unit` to fill in.")
def sessions_cmd(unit_name: str | None, only_none: bool, everything: bool,
                 triage: bool, one_by_one: bool, as_groups: bool,
                 only_dismissed: bool, from_file: str | None, as_json: bool):
    """List a unit's sessions, or every unit's, newest first.

    A session is a unit's because `orglens start` or `orglens attribute`
    said so, or because it ran inside one of the unit's homes. A home
    shared by two units lists its sessions under both.

    `--triage` and `--from` decide the unclaimed ones: at a prompt, or in
    an editor over the JSON. Neither proposes a unit; both only record.
    """
    registry, _ = _load_registry()
    every = sessions.all_sessions(registry, EVENTS_DIR)
    short = sessions.short_ids([s.id for s in every])

    if only_dismissed:
        # A dismissal is an assertion like any other and has to be auditable:
        # without this, a mistaken one is invisible outside the event log, and
        # `attribute` is the only way back from something you cannot see.
        rows = [row for row in sessions.unattributed(every, everything=True)
                if row.dismissed is not None]
        if not rows:
            click.echo("nothing dismissed")
            return
        for row in sessions.listed(rows, everything):
            click.echo(_session_line(row, short=short))
            click.echo(_session_detail(row))
        return

    if triage or from_file or as_groups:
        loose = sessions.listed(sessions.unattributed(every), everything)
        if not loose:
            click.echo("nothing unclaimed.")
            return
        if as_groups:
            groups = sessions.by_directory(loose)
            click.echo(f"{len(loose)} unclaimed in {len(groups)} directories:")
            for where, group in groups:
                click.echo(f"  {len(group):>4}  {sessions.where(where)}")
            return
        if from_file:
            _triage_from_file(registry, loose, from_file)
        else:
            _triage(registry, loose, by_group=not one_by_one)
        return

    if as_json:
        if only_none:
            rows = sessions.unattributed(every)
        elif unit_name is not None:
            rows = sessions.for_unit(every, registry.resolve(unit_name).name)
        else:
            rows = every
        click.echo(json.dumps(
            [_session_row(s) for s in sessions.listed(rows, everything)], indent=2))
        return

    if unit_name is not None and not only_none:
        try:
            unit = registry.resolve(unit_name)
        except ValueError as exc:
            click.echo(str(exc), err=True)
            sys.exit(1)
        rows = sessions.listed(sessions.for_unit(every, unit.name), everything)
        if not rows:
            click.echo(f"{unit.name}: no sessions")
            return
        for s in rows:
            click.echo(_session_line(s, short=short))
            if (why := _why_line(s)):
                click.echo(why)
        return

    groups: list[tuple[str, list]] = []
    if not only_none:
        for unit in registry.units():
            rows = sessions.listed(sessions.for_unit(every, unit.name), everything)
            if rows:
                groups.append((unit.name, rows))
    loose = sessions.listed(sessions.unattributed(every), everything)
    if loose:
        groups.append(("unattributed", loose))
    if not groups:
        click.echo("no sessions")
        return
    for label, rows in groups:
        click.echo(f"\n{label}:")
        for s in rows:
            loose = label == "unattributed"
            click.echo(_session_line(s, show_how=not loose, short=short))
            if loose:
                click.echo(_session_detail(s))
            elif (why := _why_line(s)):
                click.echo(why)


@cli.command()
@click.argument("target", shell_complete=complete.units_or_sessions)
@click.option("--prompt", default=None,
              help="Send this as the next turn instead of going in yourself.")
@click.option("--print", "print_only", is_flag=True,
              help="Print the resume command instead of running it.")
def resume(target: str, prompt: str | None, print_only: bool):
    """Resume a session by id, or a unit's newest open session.

    Hands the id to `scad session resume`, which knows where the session
    ran; orglens does no working-directory work of its own.
    """
    registry, _ = _load_registry()
    every = sessions.all_sessions(registry, EVENTS_DIR)

    session, matches = _find_session(every, target)
    if session is None and matches:
        click.echo(f"'{target}' matches more than one session:", err=True)
        for s in matches:
            click.echo(_session_line(s), err=True)
        sys.exit(1)
    if session is None:
        try:
            unit = registry.resolve(target)
        except ValueError:
            click.echo(f"'{target}' is neither a session id nor a unit.", err=True)
            sys.exit(1)
        mine = sessions.listed(sessions.for_unit(every, unit.name), everything=False)
        open_ = [s for s in mine if s.open]
        if not open_:
            click.echo(f"{unit.name}: nothing open to resume. Newest:", err=True)
            for s in mine[:3]:
                click.echo(_session_line(s), err=True)
            sys.exit(1)
        session = open_[0]

    if prompt:
        # A turn into the open pane, rather than a terminal to type it in.
        # scad pastes and submits it; `send-keys` is not a substitute, it
        # lost the first 200 characters of a 1.4k prompt.
        sys.exit(_scad(["session", "send", session.id, prompt]))

    _warn_if_held_twice(session)
    argv = ["session", "resume", session.id] + (["--print"] if print_only else [])
    sys.exit(_scad(argv))


def _warn_if_held_twice(session) -> None:
    """Say so when another process already has this session open.

    Measured on this machine 2026-09-24: six ids each held by two live
    processes, two of the transcripts genuinely forked and one carrying
    seven interrupted-turn repairs. scad refuses a second process where it
    can; this is the case it cannot see from one id, and a person about to
    resume is the one who can decide.
    """
    held = getattr(session, "also_held_by", ()) or ()
    if not held:
        return
    click.echo(f"{session.id[:8]} is already open in "
               f"{len(held)} other process(es):", err=True)
    for holder in held:
        where = holder.get("pane") or "pane unknown"
        click.echo(f"  pid {holder.get('pid')}  {where}  "
                   f"{holder.get('name') or ''}".rstrip(), err=True)
    click.echo("Go to that one rather than opening a second writer on it.",
               err=True)


def _attribute(session_id: str, unit: str, why: str | None = None) -> None:
    """One attribution, the single writer for every path that makes one."""
    append(Event(kind=ATTRIBUTED, unit=unit, session=session_id,
                 at=int(time.time()), machine=this_machine(), why=why),
           root=EVENTS_DIR)


def _dismiss(session_id: str, why: str | None = None) -> None:
    """Say a session is nobody's. The unit is empty because there is none."""
    append(Event(kind=DISMISSED, unit="", session=session_id,
                 at=int(time.time()), machine=this_machine(), why=why),
           root=EVENTS_DIR)


@cli.command()
@click.argument("session_id", required=False, shell_complete=complete.sessions)
@click.option("--under", default=None, metavar="PATH",
              help="Dismiss every unclaimed session that ran at or below PATH.")
@click.option("--why", default=None, help="Why it is nobody's, in your words.")
def dismiss(session_id: str | None, under: str | None, why: str | None):
    """Say a session belongs to no unit and never will.

    Without this the pile never empties. A scratch session in `/tmp` was
    never anyone's work, and with only `attribute` to say things with it
    sits in `sessions --none` forever, asked about every time. A later
    `attribute` takes it back.
    """
    registry, _ = _load_registry()
    every = sessions.all_sessions(registry, EVENTS_DIR)

    if under:
        # Only the unclaimed: a path can contain a unit's home, and dismissing
        # a session someone attributed on purpose is not what this is for.
        rows = sessions.under(sessions.unattributed(every), under)
        if not rows:
            click.echo(f"nothing unclaimed under {under}")
            return
        for row in rows:
            _dismiss(row.id, why)
        click.echo(f"dismissed {_count(len(rows), 'session')} under {under}")
        return
    if not session_id:
        click.echo("give a session id, or --under PATH.", err=True)
        sys.exit(1)

    session, matches = _find_session(every, session_id)
    if session is None:
        if matches:
            click.echo(f"'{session_id}' matches more than one session:", err=True)
            for s in matches:
                click.echo(_session_line(s), err=True)
        else:
            click.echo(f"No session '{session_id}' in the index.", err=True)
        sys.exit(1)
    _dismiss(session.id, why)
    click.echo(f"dismissed session {session.id}")


def _session_row(s) -> dict:
    """One session as JSON: what deciding whose it is needs, plus the empty
    `unit` and `why` to fill in and hand back through `--from`."""
    said = (s.last_turn or {}).get("text") or ""
    return {
        "id": s.id,
        "agent": s.agent,
        "cwd": s.cwd,
        "turns": s.turns,
        "when": s.when,
        "label": s.label,
        "how": s.how,
        "units": sorted(s.units),
        "dismissed": s.dismissed,
        "said": " ".join(said.split())[:200] or None,
        "unit": "",
        "why": "",
    }


def _triage(registry: Registry, rows: list, by_group: bool = True) -> None:
    """Walk the unclaimed sessions and decide them, in groups by default.

    `attribute` one at a time is the only tool without this, and 201
    invocations is not a method — the pile grows faster than that clears it.
    Grouping by the directory above each cwd collapses most of it: six
    directories held ~95 of 201 on 2026-09-25. What makes either cheap is
    that everything needed to decide is on screen — where it ran, what was
    said last. Nothing is guessed: a session at a shared root could be any
    of seventeen units, and proposing one from its title is the containment
    mistake one layer up.
    """
    names = sorted(u.name for u in registry.units())
    click.echo(f"{len(rows)} unclaimed. Units: {', '.join(names)}")
    if not by_group:
        _triage_each(registry, rows)
        return

    groups = sessions.by_directory(rows)
    click.echo(f"{len(groups)} directories. A unit name applies to the whole "
               "group; `d` dismisses it, `s` skips, `e` takes the group one "
               "session at a time, `q` stops.\n")
    for i, (where, group) in enumerate(groups, 1):
        click.echo(f"[{i}/{len(groups)}] {_count(len(group), 'session')}  "
                   f"{sessions.where(where)}")
        for session in group[:3]:
            click.echo(f"    {_session_line(session)}")
        if len(group) > 3:
            click.echo(f"    … and {len(group) - 3} more")
        answer = click.prompt("  unit", default="s", show_default=False).strip()
        if answer in ("q", "quit"):
            click.echo("stopped.")
            return
        if answer in ("", "s", "skip"):
            continue
        if answer in ("e", "each"):
            _triage_each(registry, group)
            continue
        if answer in ("d", "dismiss"):
            why = click.prompt("  why", default="", show_default=False).strip()
            for session in group:
                _dismiss(session.id, why or None)
            click.echo(f"  dismissed {_count(len(group), 'session')}")
            continue
        try:
            unit = registry.resolve(answer)
        except ValueError as exc:
            click.echo(f"  {exc} — skipped")
            continue
        why = click.prompt("  why", default="", show_default=False).strip()
        for session in group:
            _attribute(session.id, unit.name, why or None)
        click.echo(f"  attributed {_count(len(group), 'session')} to {unit.name}")


def _triage_each(registry: Registry, rows: list) -> None:
    """One session at a time, newest first."""
    click.echo("A unit name, `s` to skip, `d` to dismiss, `q` to stop.\n")
    for i, session in enumerate(rows, 1):
        click.echo(f"[{i}/{len(rows)}] {_session_line(session)}")
        click.echo(_session_detail(session))
        answer = click.prompt("  unit", default="s", show_default=False).strip()
        if answer in ("q", "quit"):
            click.echo("stopped.")
            return
        if answer in ("", "s", "skip"):
            continue
        if answer in ("d", "dismiss"):
            why = click.prompt("  why", default="", show_default=False).strip()
            _dismiss(session.id, why or None)
            click.echo("  dismissed")
            continue
        try:
            unit = registry.resolve(answer)
        except ValueError as exc:
            click.echo(f"  {exc} — skipped")
            continue
        why = click.prompt("  why", default="", show_default=False).strip()
        _attribute(session.id, unit.name, why or None)
        click.echo(f"  attributed to {unit.name}")


def _triage_from_file(registry: Registry, rows: list, path: str) -> None:
    """The same decisions, made in an editor instead of at a prompt.

    `sessions --none --json` out, a `unit` added per row, this back in —
    for the person who would rather do fifty at once than answer fifty
    prompts. A row with no `unit` is left undecided, which is how a file
    can be filled in over several sittings.
    """
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        click.echo(f"cannot read {path}: {exc}", err=True)
        sys.exit(1)
    # `list` is a command in this module and shadows the builtin, so the
    # type has to be named explicitly. See the `[*x]` note in `find`.
    if not isinstance(data, builtins.list):
        click.echo(f"{path}: expected a list of session rows.", err=True)
        sys.exit(1)

    known = {s.id: s for s in rows}
    done = skipped = 0
    for row in data:
        if not isinstance(row, dict):
            continue
        sid = str(row.get("id") or row.get("session") or "")
        unit_name = (row.get("unit") or "").strip()
        if not sid or not unit_name:
            skipped += 1
            continue
        if sid not in known:
            click.echo(f"  {sid[:8]}: not in the unclaimed list — left alone")
            skipped += 1
            continue
        why = (row.get("why") or "").strip() or None
        if unit_name in ("d", "dismiss", "dismissed"):
            _dismiss(sid, why)
        else:
            try:
                unit = registry.resolve(unit_name)
            except ValueError as exc:
                click.echo(f"  {sid[:8]}: {exc}")
                skipped += 1
                continue
            _attribute(sid, unit.name, why)
        done += 1
    click.echo(f"{done} decided, {skipped} left alone")


@cli.command()
@click.argument("session_id", shell_complete=complete.sessions)
@click.argument("unit_name", shell_complete=complete.units)
@click.option("--why", default=None,
              help="What the session was for, in your words.")
def attribute(session_id: str, unit_name: str, why: str | None):
    """Say which unit a session was for, after the fact.

    The same event `start` writes before a session's first turn. A later
    attribution of the same session replaces the earlier one when read,
    and both stay on disk. This is also how a session in a home shared by
    two units is narrowed to one.
    """
    registry, _ = _load_registry()
    every = sessions.all_sessions(registry, EVENTS_DIR)

    session, matches = _find_session(every, session_id)
    if session is None:
        if matches:
            click.echo(f"'{session_id}' matches more than one session:", err=True)
            for s in matches:
                click.echo(_session_line(s), err=True)
        else:
            click.echo(f"No session '{session_id}' in the index.", err=True)
        sys.exit(1)
    try:
        unit = registry.resolve(unit_name)
    except ValueError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    _attribute(session.id, unit.name, why)
    click.echo(f"attributed session {session.id} to {unit.name}")


def _launch_record(output: str) -> dict | None:
    """scad's launch record, or None when there is no usable one.

    `--json` makes scad's own words the read: with the flag, the record's
    `session_id` field is a contract it publishes, not prose we scrape a
    line out of. The pane (`tmux`) rides along, which is how `start` tells
    the person the way back in. A malformed or id-less record degrades to
    None rather than raising, same as every other derived source.
    """
    try:
        record = json.loads(output)
    except ValueError:
        return None
    if not isinstance(record, dict) or not record.get("session_id"):
        return None
    return record


def _launch(cwd: Path, agent: str, prompt: str | None,
            window: str | None = None, name: str | None = None) -> dict | None:
    """Start a session through scad and return its launch record — at least
    `session_id`, and the `tmux` pane when scad names one. Never raises."""
    argv = ["scad", "session", "launch", "--agent", agent, "--cwd", str(cwd), "--json"]
    if prompt:
        argv += ["--prompt", prompt]
    # The unit name is the one thing orglens knows and scad does not, so it
    # is what the window and the session are called. `--window` lands the
    # pane in the tmux session the person is already watching instead of a
    # detached sibling; without it scad behaves as before.
    if window:
        argv += ["--window", window]
    if name:
        argv += ["--name", name]
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    # `--json` moved scad's human-facing output to stderr and made stdout the
    # launch record alone, so echoing stdout here would print a JSON blob at
    # the person running `orglens start` — the words they should see arrive
    # on stderr now. Do not restore an echo of `done.stdout`.
    if done.stderr:
        click.echo(done.stderr, nl=False, err=True)
    # A launch that yields no id exits non-zero — failure is signalled, not
    # inferred from an absent field.
    if done.returncode != 0:
        return None
    return _launch_record(done.stdout)


#: Session names follow what the person already writes by hand: a unit, an
#: optional word or two of context, and the day. Nine of the eleven named
#: sessions in the index on 2026-09-25 were shaped this way —
#: `orglens-feats-sep23`, `cribsheet-sep18` — and the two on one day
#: (`orglens-backlog-feats-sep11`, `orglens-writing-skill-sep11`) are told
#: apart by the context, not the date.
def _slug(text: str, words: int = 2) -> str:
    """One or two lowercase words, safe in a name and in a tmux window."""
    parts = re.findall(r"[A-Za-z0-9]+", text.lower())
    return "-".join(parts[:words])


def _session_name(unit: str, about: str | None, taken=(), now=None) -> str:
    """`unit[-about]-sepDD`, uniquified.

    The bare unit name is not enough and is worse than scad's own default,
    which at least appends two characters: two sessions on one unit would
    both be called `orglens` and neither listing nor `/resume` picker could
    tell them apart. The date anchors, the context distinguishes.
    """
    stamp = time.strftime("%b%d", now or time.localtime()).lower()
    middle = _slug(about) if about else ""
    base = "-".join(x for x in (unit, middle, stamp) if x)
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def _arrival(unit: Unit, chosen: Home, registry: Registry) -> str:
    """What the session is told before its first turn.

    On this machine every home is already reachable, so this is not about
    access — it is about knowledge. A session that woke up in one directory
    has no way to learn the work spans three, or that its overview lives in a
    different repository entirely. Told once, up front, it does.

    Deliberately short. This is a first turn, not a briefing: it names the
    unit, its homes, and where to read more, and then gets out of the way.
    """
    lines = [f"You are working on the unit `{unit.name}` ({unit.kind})."]
    if unit.part_of:
        lines.append(f"It is part of `{unit.part_of}`.")

    lines.append("")
    lines.append(f"You are standing in `{chosen.path}`. Its homes are:")
    for home in unit.homes:
        where = home.path if home.path is not None else "not on this machine"
        here = "  <- you are here" if home.path == chosen.path else ""
        lines.append(f"  {home.name}  ->  {where}{here}")

    for path in unit.paths:
        driver = formats.existing(path, registry.grammar.driver, registry.grammar.format)
        if driver is not None:
            lines.append("")
            lines.append(f"Read `{driver}` first — it says where this stands.")
            break

    status = _status_of(registry, unit)
    if status:
        lines.append(f'Its last written status: "{status.text}"')

    return "\n".join(lines)


@cli.command()
@click.argument("unit_name", shell_complete=complete.units)
@click.option("--home", default=None, help="Which home to work in.")
@click.option("--agent", default="claude",
              type=click.Choice(["claude", "codex", "kimi"]),
              help="Which agent family to launch.")
@click.option("--prompt", default=None, help="The session's first turn.")
@click.option("--window", is_flag=True,
              help="Land it as a window in your tmux, named for the unit.")
@click.option("--about", default=None, metavar="WORDS",
              help="A word or two of context, for the session's name and window.")
@click.option("--name", default=None, metavar="TEXT",
              help="The session's name. Composed from the unit, --about and the "
                   "day when not given.")
@click.option("--no-name", "no_name", is_flag=True,
              help="Launch the session unnamed.")
@click.option("--dry-run", is_flag=True, help="Say what would happen; launch nothing.")
def start(unit_name: str, home: str | None, agent: str, prompt: str | None,
          window: bool, about: str | None, name: str | None, no_name: bool,
          dry_run: bool):
    """Start a session for a unit, attributed before its first turn.

    The unit is what you asked for and the working directory is a consequence,
    which inverts the problem rather than solving it: nothing has to work out
    afterwards which unit a session was for. Sessions started any other way are
    still attributed by containment where that is unambiguous, and sit
    unattributed where it is not.
    """
    registry, _ = _load_registry()
    try:
        unit = registry.resolve(unit_name)
    except ValueError as exc:
        match = next((c for c in registry.candidates() if c.name == unit_name), None)
        if match is None:
            click.echo(str(exc), err=True)
            sys.exit(1)
        # Starting work is when you actually know what the work is, so this is
        # the cheapest moment to say so — rather than a chore left for later.
        click.echo(f"{unit_name} is not declared. It looks like this:")
        proposal = propose(match, registry)
        _show(proposal)
        parent = _parent_for(match, registry, None)
        if not click.confirm("declare it and start?", default=True):
            return
        _write_declaration(proposal, match, parent)
        registry = Registry(registry.roots, registry.grammar)   # re-sweep
        unit = registry.resolve(unit_name)

    present = [h for h in unit.homes if h.path is not None]
    if not present:
        click.echo(f"{unit.name} has no home on this machine.", err=True)
        sys.exit(1)

    if home is not None:
        chosen = next((h for h in present if h.name == home), None)
        if chosen is None:
            click.echo(f"Unknown home '{home}'. {unit.name} has: "
                       + ", ".join(h.name for h in present), err=True)
            sys.exit(1)
    elif len(present) == 1:
        chosen = present[0]
    else:
        # Which home to work in is a choice about the task, not about the
        # unit, so it is not orglens's to make. Naming them is the answer.
        click.echo(f"{unit.name} has several homes — choose one with --home:")
        for h in present:
            click.echo(f"  {h.name:<40} {h.path}")
        sys.exit(1)

    first_turn = prompt or _arrival(unit, chosen, registry)
    if no_name:
        chosen_name = None
    else:
        taken = {s.label for s in sessions.all_sessions(registry, EVENTS_DIR) if s.label}
        chosen_name = name or _session_name(unit.name, about, taken)
    window_name = (_slug(about) if about else unit.name) if window else None

    if dry_run:
        where = f"as a window `{window_name}` in your tmux" if window else "detached in tmux"
        click.echo(f"would launch {agent} in {chosen.path} for {unit.name}, "
                   f"{where} via `scad session launch`; this command "
                   "returns at once and leaves your terminal alone.")
        click.echo(f"session name: {chosen_name or '(unnamed)'}")
        click.echo("first turn:")
        for line in first_turn.splitlines():
            click.echo(f"  {line}")
        return

    record = _launch(chosen.path, agent, first_turn,
                     window=window_name, name=chosen_name)
    if record is None:
        click.echo("scad returned no session id — the session is not attributed. "
                   "Attribute it later, or start it again through orglens.")
        return
    session = record["session_id"]

    _attribute(session, unit.name)
    click.echo(f"attributed session {session} to {unit.name}")
    # The session is running detached; say how to get back to it. scad
    # printed the pane on stderr, which is easy to miss, and never said
    # `orglens resume`, which it cannot know about.
    pane = record.get("tmux")
    click.echo(f"running detached in {pane or 'tmux'}; your terminal is free.")
    if pane:
        click.echo(f"  watch it:   tmux attach -t {pane.split(':')[0]}")
    click.echo(f"  come back:  orglens resume {unit.name}")
