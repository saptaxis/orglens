"""What is in the tree right now, materialized so agents read instead of scan.

Everything here comes from the units the tree has declared and the grammar's
own vocabulary. Nothing is filtered: a unit appears whether or not it is
complete, and a document appears whatever it is called.

The directory listing matters more than it looks. The grammar can only say
what a part is *for*; units grow directories nobody declared — `archive/`,
`infrastructure/`, `presentation/` — and an agent navigating by the grammar
alone would confidently miss all of them.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from orglens import documents
from orglens.config import Config
from orglens.state import unit_status
from orglens.units import Registry


def generate_snapshot(
    registry: Registry, config: Config, output_path: Path | None = None,
    kind: str | None = None, unit: str | None = None,
) -> str:
    """The tree as one document. `kind` or `unit` narrows it to the units a
    session is about: a projects task need not load every client and
    experiment, and on the real tree that was half the tokens read."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Topology Snapshot",
        "",
        f"> Generated: {now}",
        # Resolved, as every home path below is: `~/Dropbox` is a symlink to
        # `~/Library/CloudStorage/Dropbox` here, and a header spelling the
        # root one way above homes spelled the other made a reader assume.
        "> Roots: " + ", ".join(f"`{Path(r).expanduser().resolve()}`" for r in registry.roots),
        "",
        "---",
        "",
        "## Grammar",
        "",
        "**Kinds:** "
        + ", ".join(
            f"{name} (`{et.pattern}`)"
            for name, et in registry.grammar.entity_types.items()
        ),
        "",
        "**Documents:** "
        + ", ".join(
            f"{name} (`{at.find}`)"
            for name, at in registry.grammar.artifact_types.items()
        ),
        "",
        "---",
        "",
    ]

    units = _selected(registry, kind, unit)
    by_kind: dict[str, list] = {}
    for u in units:
        by_kind.setdefault(u.kind, []).append(u)

    for kind in sorted(by_kind):
        lines += [f"## {_heading(kind)}", ""]
        for unit in by_kind[kind]:
            status = _status_of(registry, unit)
            suffix = f" — {status.text}" if status else ""
            lines += [f"### {unit.name}{suffix}", ""]
            if unit.part_of:
                lines += [f"In: {unit.part_of}", ""]
            lines += ["Homes: " + ", ".join(f"`{p}`" for p in unit.paths), ""]

            children = registry.parts_of(unit)
            if children:
                lines += ["**Contains:**", ""]
                lines += [f"- {c.name} ({c.kind})" for c in children]
                lines.append("")

            directories = [d.name for d in documents.subdirectories(unit)]
            if directories:
                lines += ["**Directories:** " + ", ".join(f"`{d}/`" for d in directories), ""]

            loose_docs = [d.name for d in documents.loose(unit)]
            if loose_docs:
                lines += ["**Documents:** " + ", ".join(f"`{d}`" for d in loose_docs), ""]

            for artifact_kind in registry.grammar.artifact_types:
                held = documents.find(registry, artifact_kind, unit)
                if held:
                    lines.append(f"**{artifact_kind.title()}s:** {len(held)}")
                    lines += [f"- `{a.name}`" for a in held[-3:]]
                    lines.append("")

        lines += ["---", ""]

    snapshot = "\n".join(lines)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(snapshot)
    return snapshot


def _selected(registry: Registry, kind: str | None, unit: str | None) -> list:
    """The units a snapshot covers. One selection, so the markdown and the
    JSON can never disagree about what `--unit` means."""
    units = registry.units()
    if kind is not None:
        units = [u for u in units if u.kind == kind]
    if unit is not None:
        subtree = {u.name for u in registry.below(unit)}
        units = [u for u in units if u.name in subtree]
    return units


def snapshot_data(
    registry: Registry, config: Config,
    kind: str | None = None, unit: str | None = None,
) -> dict:
    """The same facts `generate_snapshot` renders, as data.

    Two readers, one selection. The markdown is for a session to read and the
    JSON is for a program to compose with — and the narrowing is the reason
    this is worth having: a caller that wants one unit's homes and documents
    should not parse headings out of 637 lines of prose to get them.
    """
    units = _selected(registry, kind, unit)
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "roots": [str(Path(r).expanduser().resolve()) for r in registry.roots],
        "kinds": {name: et.pattern
                  for name, et in registry.grammar.entity_types.items()},
        "documents": {name: at.find
                      for name, at in registry.grammar.artifact_types.items()},
        "units": [_unit_data(registry, u) for u in units],
    }


def _unit_data(registry: Registry, unit) -> dict:
    status = _status_of(registry, unit)
    return {
        "name": unit.name,
        "kind": unit.kind,
        "part_of": unit.part_of,
        "status": status.text if status else None,
        "homes": [str(p) for p in unit.paths],
        "contains": [c.name for c in registry.parts_of(unit)],
        "directories": [d.name for d in documents.subdirectories(unit)],
        "documents": [d.name for d in documents.loose(unit)],
        "artifacts": {
            artifact_kind: [a.name for a in held]
            for artifact_kind in registry.grammar.artifact_types
            if (held := documents.find(registry, artifact_kind, unit))
        },
    }


def _heading(kind: str) -> str:
    return kind.replace("-", " ").capitalize() + "s"


def _status_of(registry: Registry, unit):
    declared = registry.grammar.documents_for(unit.kind)
    return unit_status(unit.paths, declared, registry.grammar.format)
