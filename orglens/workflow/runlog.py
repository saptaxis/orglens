"""Appending past-tense facts to a packet's run log.

The only module in the workflow face that writes. It appends and never
rewrites, because a line already on disk records something that happened and
nothing later makes it false.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

RUNS = "runs.jsonl"

#: Keys that describe the present rather than the past. I1 forbids these: a
#: projection of current state duplicates what the directory already says and
#: will drift from it, which is the failure the whole design avoids.
FORBIDDEN_KEYS = frozenset({"current_state", "status", "pending", "next_node", "state"})


def workflow_version(workflow_path: Path) -> str:
    """Content address of a workflow definition.

    Every run fact names the definition it obeyed. Without it a packet stays
    reconstructible while the guard semantics that governed its earlier actions
    do not.
    """
    digest = hashlib.sha256(Path(workflow_path).read_bytes()).hexdigest()
    return f"sha256:{digest[:12]}"


def append_fact(packet: Path, fact: dict) -> None:
    """Append one past-tense fact. Never rewrites an existing line."""
    if "type" not in fact:
        raise ValueError("a run fact must declare a 'type'")

    offending = FORBIDDEN_KEYS & set(fact)
    if offending:
        raise ValueError(
            f"run facts record the past, not the present: {sorted(offending)} "
            "duplicate state that is derived from the packet"
        )

    line = json.dumps(fact, ensure_ascii=False, sort_keys=True)
    with (Path(packet) / RUNS).open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
