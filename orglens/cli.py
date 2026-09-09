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

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import click

from orglens import activity, check as check_module, documents, reference, view
from orglens.config import Config
from orglens.declaration import MARKER
from orglens.events import EVENTS_DIR, Event, append, attributions, this_machine
from orglens.homes import Home
from orglens.propose import Proposal, propose
from orglens.scadconfig import render as render_scadconfig
from orglens.snapshot import generate_snapshot
from orglens.state import read_status
from orglens.units import Registry, Unit
from orglens.workflow.cli import workflow as workflow_group

#: Where a rendered config lands unless `--out` says otherwise. A module-level
#: constant, not inlined, so a test can monkeypatch it rather than write to
#: the real `~/.scad`.
SCAD_CONFIGS_DIR = Path.home() / ".scad" / "configs"


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
    Mirrors the reasoning in `view.py`'s card: a clock within an hour of one
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

    # Read once, not once per unit: `attributions` walks every shard, and a
    # loop over thirty units would re-read the whole log thirty times for the
    # same answer.
    attributed = attributions(root=EVENTS_DIR)

    # `peek`, not `read`: the per-home git calls `read` makes for the last
    # commit and the dirty count are the entire gap between `list` at 1.9s
    # and `status` at 5.5s on the real tree, and sorting needs neither.
    acts = {
        unit: activity.peek(unit.paths, unit.name, home_names=[h.name for h in unit.homes],
                             attributed=attributed)
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
def status():
    """Where everything stands — the authored line, dated, beside derived facts."""
    registry, _ = _load_registry()
    units = registry.units()

    # Read once, not once per unit: `attributions` walks every shard, and a
    # loop over thirty units would re-read the whole log thirty times for the
    # same answer.
    attributed = attributions(root=EVENTS_DIR)

    acts = {
        unit: activity.read(unit.paths, unit.name, home_names=[h.name for h in unit.homes],
                             attributed=attributed)
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


def _write_declaration(proposal: Proposal, path: Path) -> None:
    """Write the marker. Field order is the reading order, not alphabetical.

    `home:` names this exact directory — `propose._home_name` already worked
    out what it is, and writing that fact down promotes it to the `marker`
    rung of `homes.resolve_home`'s ladder. Without it, the ladder re-derives
    a name from scratch and can land this directory on the same name as a
    same-named sibling code home, collapsing both proposed homes onto one
    directory and losing the other.
    """
    lines = [f"home: {proposal.homes[0]}", f"unit: {proposal.unit}"]
    if proposal.kind:
        lines.append(f"kind: {proposal.kind}")
    if proposal.part_of:
        lines.append(f"part_of: {proposal.part_of}")
    lines.append("homes:")
    lines += [f"  - {h}" for h in proposal.homes]
    (path / MARKER).write_text("\n".join(lines) + "\n")


def _show(proposal: Proposal) -> None:
    """Show the inference and what each part was inferred from.

    A human confirming a guess needs to see the guess's reasoning, or they are
    not confirming — they are trusting.
    """
    click.echo(f"  unit:    {proposal.unit}")
    click.echo(f"  kind:    {proposal.kind or '(unknown)':<24}"
               f"  {proposal.why.get('kind', '')}")
    if proposal.part_of:
        click.echo(f"  part_of: {proposal.part_of:<24}"
                   f"  {proposal.why.get('part_of', '')}")
    click.echo(f"  homes:   {proposal.why.get('homes', '')}")
    for home in proposal.homes:
        click.echo(f"    - {home}")


@cli.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option("--yes", is_flag=True, help="Write it without asking.")
def declare(path: str, yes: bool):
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

    if not yes and not click.confirm("write this?", default=True):
        click.echo("nothing written.")
        return

    _write_declaration(proposal, target)
    click.echo(f"declared {proposal.unit}")


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


def _repo_keys(unit: Unit) -> list[str]:
    """The repository names `render` would produce, in first-seen order —
    used only to validate `--workdir` before writing, never by `render`
    itself, which stays pure.
    """
    keys: list[str] = []
    for home in unit.homes:
        if home.path is None:
            continue
        key = home.name.split("/")[0]
        if key not in keys:
            keys.append(key)
    return keys


@cli.command(name="config")
@click.argument("unit_name")
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

    # Read once, not once per unit: `attributions` walks every shard, and a
    # loop over thirty units would re-read the whole log thirty times for the
    # same answer.
    attributed = attributions(root=EVENTS_DIR)

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
                        attributed=attributed,
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


def _session_id_from(output: str) -> str | None:
    """The id scad's own launch record names, or None.

    `--json` makes scad's own words the read: with the flag, its record's
    `session_id` field is a contract it publishes, not prose we scrape a
    line out of. The one thing orglens needs from scad is this id, and
    reading it from the record makes the join exact — a newest-file scan of
    `~/.scad/launches/` would be a guess, and this system does not guess
    about attribution. A malformed or id-less record degrades to None here
    rather than raising, same as every other derived source.
    """
    try:
        record = json.loads(output)
    except ValueError:
        return None
    if not isinstance(record, dict):
        return None
    return record.get("session_id") or None


def _launch(cwd: Path, agent: str, prompt: str | None) -> str | None:
    """Start a session through scad and return the id it minted. Never raises."""
    argv = ["scad", "session", "launch", "--agent", agent, "--cwd", str(cwd), "--json"]
    if prompt:
        argv += ["--prompt", prompt]
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    click.echo(done.stdout, nl=False)
    if done.stderr:
        click.echo(done.stderr, nl=False, err=True)
    # A launch that yields no id exits non-zero — failure is signalled, not
    # inferred from an absent field.
    if done.returncode != 0:
        return None
    try:
        return _session_id_from(done.stdout)
    except ValueError:
        return None


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

    driver = registry.grammar.driver
    for path in unit.paths:
        if (path / driver).exists():
            lines.append("")
            lines.append(f"Read `{path / driver}` first — it says where this stands.")
            break

    status = _status_of(registry, unit)
    if status:
        lines.append(f'Its last written status: "{status.text}"')

    return "\n".join(lines)


@cli.command()
@click.argument("unit_name")
@click.option("--home", default=None, help="Which home to work in.")
@click.option("--agent", default="claude",
              type=click.Choice(["claude", "codex", "kimi"]),
              help="Which agent family to launch.")
@click.option("--prompt", default=None, help="The session's first turn.")
@click.option("--dry-run", is_flag=True, help="Say what would happen; launch nothing.")
def start(unit_name: str, home: str | None, agent: str, prompt: str | None,
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
        if not click.confirm("declare it and start?", default=True):
            return
        _write_declaration(proposal, match)
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

    if dry_run:
        click.echo(f"would launch {agent} in {chosen.path} for {unit.name}")
        return

    session = _launch(chosen.path, agent, prompt or _arrival(unit, chosen, registry))
    if session is None:
        click.echo("scad returned no session id — the session is not attributed. "
                   "Attribute it later, or start it again through orglens.")
        return

    append(Event(kind="attributed", unit=unit.name, session=session,
                 at=int(time.time()), machine=this_machine()),
           root=EVENTS_DIR)
    click.echo(f"attributed session {session} to {unit.name}")
