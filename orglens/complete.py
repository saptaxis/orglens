"""What the shell offers after `orglens <verb> <tab>`.

Click generates the command and option names by itself; the arguments are
the ones typed most and the only ones it cannot guess. A unit name, a
document kind and a session id are each a lookup someone otherwise does by
reading `orglens list` first.

**Every completer reads a cache, never the tree.** A completer that swept
the roots would put a 2-second pause on a keystroke, which is worse than no
completion at all: the shell would appear to hang. So unit names and kinds
come out of the snapshot (`~/.orglens/cache/snapshot.md`), which the
snapshot command already keeps, and a missing or stale snapshot completes
to nothing rather than to a wait. Session ids come from scad's export,
capped, because there is no cache for those and the export is one call.

Nothing here raises. A completer that fails takes the shell's prompt with
it, so every path returns a list.
"""

from __future__ import annotations

import re

UNIT_HEADING = re.compile(r"^### (.+)$", re.M)
KIND_LINE = re.compile(r"^\*\*(Kinds|Documents):\*\* (.+)$", re.M)
NAMED = re.compile(r"([A-Za-z0-9_-]+) \(`")

#: Enough to cover a machine's recent work without making tab feel slow.
SESSION_CAP = 300


def _snapshot_text() -> str:
    try:
        from orglens.config import Config

        return Config.load().snapshot_path.read_text()
    except Exception:
        return ""


def unit_names() -> list[tuple[str, str]]:
    """Every unit in the snapshot, with its status line as the hint.

    The heading carries both — `### name — status` — so the status comes
    free, and seeing it is most of what choosing between two units needs.
    """
    out = {}
    for heading in UNIT_HEADING.findall(_snapshot_text()):
        name, _, status = heading.strip().partition(" — ")
        name = name.strip()
        if name:
            out.setdefault(name, status.strip()[:70])
    return sorted(out.items())


def kind_names() -> list[str]:
    """The grammar's words: entity kinds and document kinds together, since
    the argument that takes one is never the argument that takes the other
    and offering both is cheaper than being clever about which."""
    out: set[str] = set()
    for _, line in KIND_LINE.findall(_snapshot_text()):
        out.update(NAMED.findall(line))
    return sorted(out)


def session_ids() -> list[tuple[str, str]]:
    """Recent session ids with what they were called, newest first."""
    try:
        from orglens.sessions import run_scad

        rows = run_scad(["session", "ls", "--kind", "main",
                         "--limit", str(SESSION_CAP)])
    except Exception:
        return []
    out = []
    for row in rows[:SESSION_CAP]:
        sid = str(row.get("id") or "")
        if sid:
            out.append((sid, str(row.get("name") or row.get("title") or "")))
    return out


def _items(pairs, incomplete: str):
    from click.shell_completion import CompletionItem

    lowered = incomplete.lower()
    return [CompletionItem(value, help=help_ or None)
            for value, help_ in pairs if value.lower().startswith(lowered)]


def units(ctx, param, incomplete):
    return _items(unit_names(), incomplete)


def kinds(ctx, param, incomplete):
    return _items(((name, "") for name in kind_names()), incomplete)


def sessions(ctx, param, incomplete):
    return _items(session_ids(), incomplete)


def units_or_sessions(ctx, param, incomplete):
    """`resume` takes either, so it offers both — units first, since a name
    is what someone types when they know what they are going back to."""
    return units(ctx, param, incomplete) + sessions(ctx, param, incomplete)
