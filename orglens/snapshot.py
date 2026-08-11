"""What is in the tree right now, materialized so agents read instead of scan.

Everything here comes from the filesystem and the grammar's patterns. Nothing
is filtered: an entity appears whether or not it is complete, and a document
appears whatever it is called.

The subdirectory listing matters more than it looks. The grammar can only say
what a part is *for*; entities grow directories nobody declared — `archive/`,
`infrastructure/`, `presentation/` — and an agent navigating by the grammar
alone would confidently miss all of them.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from orglens.config import Config
from orglens.state import read_status
from orglens.topology import Topology


def generate_snapshot(
    topo: Topology, config: Config, output_path: Path | None = None
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Topology Snapshot",
        "",
        f"> Generated: {now}",
        f"> Docs root: `{config.docs_root}`",
        "",
        "---",
        "",
        "## Grammar",
        "",
        "**Kinds:** "
        + ", ".join(
            f"{name} (`{et.pattern}`)"
            for name, et in topo.grammar.entity_types.items()
        ),
        "",
        "**Documents:** "
        + ", ".join(
            f"{name} (`{at.find}`)"
            for name, at in topo.grammar.artifact_types.items()
        ),
        "",
        "---",
        "",
    ]

    entities = topo.list_entities()
    by_type: dict[str, list] = {}
    for entity in entities:
        by_type.setdefault(entity.entity_type, []).append(entity)

    for type_name in topo.grammar.entity_types:
        group = by_type.get(type_name, [])
        if not group:
            continue

        lines += [f"## {_heading(type_name)}", ""]
        for entity in group:
            status = read_status(entity.path, topo.grammar.documents_for(type_name))
            suffix = f" — {status.text}" if status else ""
            lines += [f"### {entity.name}{suffix}", ""]
            if entity.parent_name:
                lines += [f"In: {entity.parent_name}", ""]
            lines += [f"Path: `{_relative(entity.path, config.docs_root)}`", ""]

            children = [
                e for e in entities
                if e.parent_name == entity.name and e.path.parent == entity.path
            ]
            if children:
                lines += ["**Contains:**", ""]
                lines += [f"- {c.name} ({c.entity_type})" for c in children]
                lines.append("")

            directories = [d.name for d in topo.subdirectories(entity)]
            if directories:
                lines += ["**Directories:** " + ", ".join(f"`{d}/`" for d in directories), ""]

            documents = [d.name for d in topo.documents(entity)]
            if documents:
                lines += ["**Documents:** " + ", ".join(f"`{d}`" for d in documents), ""]

            for name in topo.grammar.artifact_types:
                held = [
                    a for a in topo.find_artifacts(name, entity.name)
                    if a.entity_name == entity.name
                ]
                if held:
                    lines.append(f"**{name.title()}s:** {len(held)}")
                    lines += [f"- `{a.name}`" for a in held[-3:]]
                    lines.append("")

        lines += ["---", ""]

    snapshot = "\n".join(lines)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(snapshot)
    return snapshot


def _heading(type_name: str) -> str:
    return type_name.replace("-", " ").capitalize() + "s"


def _relative(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path
