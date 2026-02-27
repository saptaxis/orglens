"""Snapshot generation — materialize topology + state as a markdown document."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from orglens.config import Config
from orglens.state import extract_status
from orglens.topology import Topology


def generate_snapshot(topo: Topology, config: Config, output_path: Path | None = None) -> str:
    """Generate a markdown snapshot of the full topology and state.

    If output_path is provided, also writes the snapshot to that file.
    """
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append("# Topology Snapshot")
    lines.append("")
    lines.append(f"> Generated: {now}")
    lines.append(f"> Docs root: `{config.docs_root}`")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Grammar summary
    lines.append("## Grammar")
    lines.append("")
    lines.append("**Entity Types:** " + ", ".join(topo.grammar.entity_types.keys()))
    lines.append("")
    lines.append("**Artifact Types:** " + ", ".join(
        f"{k} (`{v.directory}/`, `{v.pattern}`)"
        for k, v in topo.grammar.artifact_types.items()
    ))
    lines.append("")
    lines.append("---")
    lines.append("")

    # Group entities by type
    all_entities = topo.list_entities()
    by_type: dict[str, list] = {}
    for entity in all_entities:
        by_type.setdefault(entity.entity_type, []).append(entity)

    # Render each entity type section
    type_display = {
        "research-program": "Research Programs",
        "experiment": "Experiments",
        "project": "Projects",
        "client": "Clients",
    }

    for etype in ["research-program", "project", "client"]:
        entities = by_type.get(etype, [])
        if not entities:
            continue

        lines.append(f"## {type_display.get(etype, etype)}")
        lines.append("")

        for entity in entities:
            status = _read_entity_status(entity.path, topo.grammar.entity_types[etype])
            status_str = f" — {status}" if status else ""
            lines.append(f"### {entity.name}{status_str}")
            lines.append("")
            lines.append(f"Path: `{entity.path.relative_to(config.docs_root)}`")
            lines.append("")

            # List child experiments inline for research programs
            if etype == "research-program":
                children = by_type.get("experiment", [])
                rp_children = [c for c in children if c.parent_name == entity.name]
                if rp_children:
                    lines.append("**Experiments:**")
                    lines.append("")
                    for child in rp_children:
                        child_status = _read_entity_status(
                            child.path, topo.grammar.entity_types["experiment"]
                        )
                        child_status_str = f" — {child_status}" if child_status else ""
                        lines.append(f"- {child.name}{child_status_str}")
                    lines.append("")

            # List recent artifacts
            for at_name, at in topo.grammar.artifact_types.items():
                artifacts = topo._find_artifacts_in(at, entity.path, entity.name)
                if artifacts:
                    lines.append(f"**{at_name.title()}s:** {len(artifacts)}")
                    # Show most recent 3
                    for a in artifacts[-3:]:
                        lines.append(f"- `{a.name}`")
                    lines.append("")

        lines.append("---")
        lines.append("")

    snapshot = "\n".join(lines)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(snapshot)

    return snapshot


def _read_entity_status(entity_path: Path, entity_type) -> str | None:
    """Read status from an entity's state file."""
    if not entity_type.state_file:
        return None
    state_file = entity_path / entity_type.state_file
    if not state_file.exists():
        return None
    content = state_file.read_text()
    return extract_status(content)
