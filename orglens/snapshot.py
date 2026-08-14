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
from orglens.state import read_status
from orglens.units import Registry


def generate_snapshot(
    registry: Registry, config: Config, output_path: Path | None = None
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Topology Snapshot",
        "",
        f"> Generated: {now}",
        "> Roots: " + ", ".join(f"`{r}`" for r in registry.roots),
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

    units = registry.units()
    by_kind: dict[str, list] = {}
    for unit in units:
        by_kind.setdefault(unit.kind, []).append(unit)

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
                held = documents.find(registry, artifact_kind, unit.name)
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


def _heading(kind: str) -> str:
    return kind.replace("-", " ").capitalize() + "s"


def _status_of(registry: Registry, unit):
    declared = (
        registry.grammar.documents_for(unit.kind)
        if unit.kind in registry.grammar.entity_types
        else [registry.grammar.driver]
    )
    for path in unit.paths:
        status = read_status(path, declared)
        if status:
            return status
    return None
