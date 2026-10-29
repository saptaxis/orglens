"""Keeping the snapshot cache fresh without anyone waiting for it.

Every command scans the tree live; the snapshot (`snapshot.md` and
`snapshot.json`) is the one cache, read by completion, by editors and by an
agent at the start of a session. It goes stale whenever the tree changes.

Two parts keep it current. A command that already scans the tree, and a
completer reading the cache, each start a detached `orglens snapshot
--if-stale`: it checks, and rebuilds only when something changed. Nobody
waits on the rebuild (4 s on the real tree): the reader answers from the
cache it has, and the next read sees the new one. A lock keeps one refresh
at a time.

Not a watcher: no background process to install on every machine. One read
behind is the cost.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from orglens import documents, formats
from orglens.config import Config
from orglens.declaration import MARKER
from orglens.units import Registry

#: A refresh still holding the lock after this long is taken to have died.
LOCK_EXPIRES_S = 300


def stale(registry: Registry, config: Config, shown=str) -> str | None:
    """Why the written snapshot no longer matches the tree, or None.

    What it renders: each marker and declared document, and every document
    it lists. A directory under a home that changed is a document added,
    removed or renamed; a listed file that changed or went is an edit or a
    deletion. A missing snapshot is stale, not an error. `shown` prints a
    path.
    """
    output = config.snapshot_path
    if not output.exists():
        return f"no snapshot at {output}"
    data = config.snapshot_json_path
    if not data.exists() or data.stat().st_mtime < output.stat().st_mtime:
        return f"{data} is missing or older than {output}; completion reads it"
    written = output.stat().st_mtime

    def newer(path: Path) -> bool:
        try:
            return path.stat().st_mtime > written
        except OSError:
            return False

    for unit in registry.units():
        paths = [unit.declared_at / MARKER]
        paths += [f for p in unit.paths
                  for d in registry.grammar.documents_for(unit.kind)
                  if (f := formats.existing(p, d, registry.grammar.format)) is not None]
        for home in unit.paths:
            paths += [home, *documents._dirs_under(home)]
        for path in paths:
            if newer(path):
                return f"{shown(path)} changed after the snapshot was written"

    for path in _listed(data):
        if not path.exists():
            return f"{shown(path)} is gone since the snapshot was written"
        if newer(path):
            return f"{shown(path)} changed after the snapshot was written"
    return None


def _listed(data: Path) -> list[Path]:
    """Every document path the written JSON names."""
    import json
    try:
        units = json.loads(data.read_text()).get("units", [])
    except (OSError, ValueError):
        return []
    return [Path(f["path"]) for u in units
            for held in (u.get("files") or {}).values() for f in held]


def lock_path(config: Config) -> Path:
    return config.snapshot_path.parent / "snapshot.refreshing"


def later(config: Config | None = None) -> None:
    """Start a detached `orglens snapshot --if-stale`, unless one is running.
    Never raises and never waits: a refresh that cannot start is skipped."""
    try:
        config = config or Config.current()
        lock = lock_path(config)
        lock.parent.mkdir(parents=True, exist_ok=True)
        try:
            if time.time() - lock.stat().st_mtime < LOCK_EXPIRES_S:
                return
            lock.unlink()
        except FileNotFoundError:
            pass
        os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        subprocess.Popen(
            [sys.executable, "-m", "orglens", "snapshot", "--if-stale"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )
    except Exception:
        pass
