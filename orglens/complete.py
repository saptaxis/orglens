"""What the shell offers after `orglens <verb> <tab>`.

Click generates the command and option names by itself; the arguments are
the ones typed most and the only ones it cannot guess. A unit name, a
document kind and a session id are each a lookup someone otherwise does by
reading `orglens list` first.

**Every completer reads a cache, never the tree.** A completer that swept
the roots would put a 2-second pause on a keystroke, which is worse than no
completion at all: the shell would appear to hang. So unit names and kinds
come out of the snapshot's data (`~/.orglens/cache/snapshot.json`, written
beside the markdown snapshot), which the snapshot command already keeps, and a missing or stale snapshot completes
to nothing rather than to a wait. Session ids come from scad's export,
capped, because there is no cache for those and the export is one call.

Nothing here raises. A completer that fails takes the shell's prompt with
it, so every path returns a list.
"""

from __future__ import annotations

#: Enough to cover a machine's recent work without making tab feel slow.
SESSION_CAP = 300


def _snapshot_data() -> dict:
    try:
        import json
        from orglens.config import Config

        return json.loads(Config.current().snapshot_json_path.read_text())
    except Exception:
        return {}


def unit_names() -> list[tuple[str, str]]:
    """Every unit in the snapshot, with its status line as the hint —
    seeing it is most of what choosing between two units needs."""
    out = {}
    for unit in _snapshot_data().get("units", []):
        name = str(unit.get("name") or "").strip()
        if name:
            out.setdefault(name, str(unit.get("status") or "")[:70])
    return sorted(out.items())


def kind_names() -> list[str]:
    """The grammar's words: entity kinds and document kinds together, since
    the argument that takes one is never the argument that takes the other
    and offering both is cheaper than being clever about which."""
    data = _snapshot_data()
    return sorted(set(data.get("kinds", {})) | set(data.get("documents", {})))


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


def packets(ctx, param, incomplete):
    """Directories that hold a `session.jsonl`, under the roots.

    A packet is not in the snapshot — it is a directory with a session file,
    which nothing renders — so this is the one completer that looks at the
    tree. It stays cheap by looking only for the session file itself rather
    than reading every file: one filename, looked for under the roots without
    entering the folders `skip.py` names.
    """
    from pathlib import Path

    try:
        from orglens.config import Config
        from orglens import skip
        from orglens.workflow.session import SESSION_FILE

        roots = [Path(r).expanduser() for r in Config.current().roots]
    except Exception:
        return []
    found = []
    for root in roots:
        try:
            found += [str(p.parent) for p in skip.walk_files(root, SESSION_FILE)]
        except OSError:
            continue
    return _items(((path, "") for path in sorted(set(found))), incomplete)


def nodes(ctx, param, incomplete):
    """The node names in the workflow this packet is bound to.

    The packet is the command's own argument, so the workflow is knowable
    without asking: read the binding fact out of its session file, load that
    `WORKFLOW.yaml`, and offer its nodes. No packet on the line yet means no
    completions, which is correct — the nodes depend on which workflow.
    """
    from pathlib import Path

    packet = (ctx.params or {}).get("packet")
    if not packet:
        return []
    try:
        from orglens.workflow.definition import load_workflow
        from orglens.workflow.session import read, workflow_path

        bound = workflow_path(read(Path(packet)))
        if bound is None:
            return []
    except Exception:
        return []
    try:
        workflow = load_workflow(bound)
        # `program` is resolved to an absolute path by the loader; the hint
        # wants the word the workflow wrote, not a line of filesystem.
        pairs = [(node.name, Path(node.program).name if node.program else "")
                 for node in workflow.nodes]
    except Exception:
        # The loader validates — a node's program has to exist on disk — and
        # that is right for the engine and wrong here: a workflow being edited
        # would stop completing at the moment you most need the node names.
        # Names come straight out of the YAML when validation fails.
        pairs = _names_in(bound)
    return _items(pairs, incomplete)


def _names_in(path) -> list[tuple[str, str]]:
    """Node names read without validating anything."""
    try:
        import yaml

        raw = yaml.safe_load(open(path).read()) or {}
        nodes = raw.get("nodes") or []
        return [(str(n["name"]), str(n.get("program") or ""))
                for n in nodes if isinstance(n, dict) and n.get("name")]
    except Exception:
        return []


def units_or_sessions(ctx, param, incomplete):
    """`resume` takes either, so it offers both — units first, since a name
    is what someone types when they know what they are going back to."""
    return units(ctx, param, incomplete) + sessions(ctx, param, incomplete)
