"""The durable half of `~/.orglens` — what someone asserted, and when.

Everything else orglens knows is derived: scan the tree again and it comes
back. This does not. An attribution exists *because* nothing could compute it
— the filesystem could not say which unit a session in a shared directory was
for, so a human said. Losing that loses something real, which is why this is
the one thing under `~/.orglens` that is not a cache.

Sharded per session, and that is not organisational tidiness: it is what makes
merging free. Two writers never touch one file, so no sync mechanism — git,
Dropbox, rsync — can conflict, and reading is concatenate-and-sort rather than
a merge algorithm anyone has to write. A finished session's file never changes
again, and an immutable file is the one thing every sync tool handles
perfectly.

Events carry names and times, never paths. A path is true on one machine.
"""

from __future__ import annotations

import json
import os
import socket
from dataclasses import asdict, dataclass
from pathlib import Path

EVENTS_DIR = Path.home() / ".orglens" / "events"


@dataclass(frozen=True)
class Event:
    kind: str
    unit: str
    session: str | None
    at: int
    machine: str


def this_machine() -> str:
    """A stable name for this host, for events that belong to no session."""
    return os.environ.get("ORGLENS_MACHINE") or socket.gethostname().split(".")[0]


def _shard(event: Event, root: Path) -> Path:
    """One file per writer. A session writes its own; anything else writes the
    machine's, because a command run from a shell belongs to no session."""
    return Path(root) / f"{event.session or event.machine}.jsonl"


def append(event: Event, root: Path = EVENTS_DIR) -> None:
    """Add one event. Append-only: nothing here is ever rewritten."""
    path = _shard(event, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(asdict(event), sort_keys=True) + "\n")


def read_all(root: Path = EVENTS_DIR) -> list[Event]:
    """Every event, oldest first. Never raises.

    A malformed line is skipped rather than fatal: a log that refuses to be
    read because one line is broken loses everything for the sake of one
    record.
    """
    found: list[Event] = []
    try:
        shards = sorted(Path(root).rglob("*.jsonl"))
    except OSError:
        return []
    for shard in shards:
        try:
            lines = shard.read_text().splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                data = json.loads(line)
                found.append(Event(**data))
            except (ValueError, TypeError):
                continue
    return sorted(found, key=lambda e: e.at)


def attributions(root: Path = EVENTS_DIR) -> dict[str, str]:
    """session id -> unit name, latest assertion winning.

    Someone can change their mind, and both events stay on disk. What is read
    back is the latest; what is kept is the history of having changed it.
    """
    out: dict[str, str] = {}
    for event in read_all(root):
        if event.kind == "attributed" and event.session:
            out[event.session] = event.unit
    return out
