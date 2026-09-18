"""Load and validate a `WORKFLOW.yaml`.

Validation is all of it: nodes non-empty, names unique, every program a file
that exists, every node naming what it writes. Nothing else is declared —
no guards, no reads, no roots. A program says in its own prose what it loads.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


class WorkflowError(ValueError):
    """A workflow file the engine will not run. Raised at load, never later."""


@dataclass(frozen=True)
class Node:
    name: str
    #: Resolved against the workflow directory at load; exists, or the load failed.
    program: Path
    #: The one file this node produces, relative to the packet.
    writes: str
    #: Finishing this node opens a gate.
    review: bool = False


@dataclass(frozen=True)
class Workflow:
    name: str
    path: Path
    nodes: tuple[Node, ...]

    def node(self, name: str) -> Node | None:
        return next((s for s in self.nodes if s.name == name), None)

    def after(self, name: str) -> Node | None:
        """The node following `name`, or None if it is the last."""
        names = [s.name for s in self.nodes]
        i = names.index(name)
        return self.nodes[i + 1] if i + 1 < len(self.nodes) else None


def load_workflow(path: Path) -> Workflow:
    path = Path(path).expanduser()
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except OSError as exc:
        raise WorkflowError(f"cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise WorkflowError(f"{path} is not valid YAML: {exc}") from exc

    nodes_raw = raw.get("nodes") or []
    if not nodes_raw:
        raise WorkflowError(f"{path}: no nodes")

    here = path.parent
    nodes: list[Node] = []
    seen: set[str] = set()
    for i, item in enumerate(nodes_raw):
        if not isinstance(item, dict) or not item.get("name"):
            raise WorkflowError(f"{path}: node {i + 1} has no name")
        name = str(item["name"])
        if name in seen:
            raise WorkflowError(f"{path}: node name '{name}' appears twice")
        seen.add(name)
        if not item.get("program"):
            raise WorkflowError(f"{path}: node '{name}' has no program")
        program = (here / str(item["program"])).resolve()
        if not program.is_file():
            raise WorkflowError(f"{path}: node '{name}' names a program that does not exist: {item['program']}")
        if not item.get("writes"):
            raise WorkflowError(f"{path}: node '{name}' does not say what it writes")
        nodes.append(Node(
            name=name, program=program, writes=str(item["writes"]),
            review=bool(item.get("review", False)),
        ))
    return Workflow(name=str(raw.get("workflow") or path.parent.name), path=path, nodes=tuple(nodes))
