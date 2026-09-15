"""A document belongs to a home by containment, not by glob depth.

The old globs reached exactly one level: `plans/*.md` relative to an entity.
That worked only because every folder holding plans happened to be an entity,
and it failed the moment one was not — measured on physics-priors-latent-space,
81 plans on disk and 75 visible: two in `infrastructure/plans/`, which matches
no pattern, and four in `plans/archive/`, one level too deep.

Containment is also what makes regrouping free. Leave a group of experiments
undeclared and the programme owns their documents; declare them later and the
documents follow, with nothing renamed.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from orglens.units import Registry, Unit


@dataclass(frozen=True)
class Document:
    name: str
    kind: str
    path: Path
    unit: str
    #: What a matcher found, when one ran: {"file", "line", "text"} each.
    #: Empty when `find` was only scoped, never matched.
    matches: tuple[dict, ...] = ()


def _claimed_by(registry: Registry, unit: Unit) -> list[Path]:
    """Home paths this unit's documents must not claim.

    Two different reasons a directory is someone else's: it declared
    `part_of` this unit — the roll-up relationship, unaffected by where the
    directories actually sit — or its home simply lies inside this unit's
    own home, regardless of whether `part_of` was ever written. The spec
    says a unit's documents are "everything matching under its homes, minus
    whatever a nested unit's home claims" — containment, not only declared
    parentage, decides ownership. A unit declared nested in another's home
    without `part_of` used to have its documents counted by both; this is
    what stops that. A home identical to one of this unit's own (the
    ordinary shared-home case) is deliberately left unclaimed here — only a
    genuinely nested *other* home is excluded.
    """
    own = {p.resolve() for p in unit.paths}
    claimed = {p.resolve() for part in registry.parts_of(unit) for p in part.paths}
    for other in registry.units():
        if other.name == unit.name:
            continue
        for p in other.paths:
            resolved = p.resolve()
            if resolved not in own and any(resolved.is_relative_to(o) for o in own):
                claimed.add(resolved)
    return sorted(claimed)


def _containers(home: Path, directory: str) -> list[Path]:
    """Every directory under `home` that could hold this kind's documents.

    A kind's `find` names a container (`plans`) and a file pattern (`*.md`).
    `Path.rglob("plans/*.md")` only reaches one level below a directory
    literally named `plans` — it does not see `plans/archive/*.md`. So the
    container is matched by name at any depth, and each match is then
    searched for the file pattern at any depth in turn, which is what lets
    an archived plan still be found. When a kind has no container of its
    own — `doc`, whose pattern is a bare `*.md` — the home itself is the
    only container, which is also what keeps `doc` a catch-all rather than
    one more directory-bound kind.
    """
    if not directory:
        return [home]
    return [d for d in _dirs_under(home) if d.name == directory]


#: Build output and dependency folders: never documents, and the bulk of a
#: code home's directory count.
_SKIP = {"node_modules", "__pycache__", "venv", "dist", "build", "target", "site-packages"}


@lru_cache(maxsize=None)
def _dirs_under(home: Path) -> tuple[Path, ...]:
    """Every directory under a home, walked once per process and filtered
    per kind. `find` runs once per unit per kind, and a walk per call was
    92 walks over the same directories for 23 units."""
    found: list[Path] = []
    stack = [home]
    while stack:
        try:
            entries = sorted(stack.pop().iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.name.startswith(".") or entry.name in _SKIP:
                continue
            try:
                if entry.is_dir():
                    found.append(entry)
                    stack.append(entry)
            except OSError:
                continue
    return tuple(sorted(found))


def find(
    registry: Registry,
    kind: str,
    unit: Unit | str | None = None,
    within: str | None = None,
) -> list[Document]:
    """Documents of a kind, at any depth under a unit's homes.

    `unit` takes a `Unit` the caller already resolved, a bare name for
    genuine user input (`orglens find plan <name>`), or nothing for every
    unit. A caller iterating `registry.units()` and calling back in with
    `unit.name` was re-resolving a name that was never ambiguous in the
    first place — and two markers declaring the same unit name (a `cp -R`,
    a worktree, a Dropbox conflicted copy) turned that into `Registry.resolve`
    raising out of the loop, taking every *other* unit's row down with it.
    Accepting the `Unit` itself skips resolution altogether; only a plain
    string still asks `resolve` to adjudicate, which is the right place for
    that question to be asked and answered.

    A container nested inside a same-named container — an archived
    experiment's own `plans/` preserved under the parent's `plans/archive/`
    — matches `_containers` twice, so the file under it would otherwise be
    yielded once per container that reaches it. Deduplicated on the
    resolved path, but *per unit*, not across the whole call: within one
    unit a file is counted once however many containers enclose it, while
    two units that share a home each see the file, because that is what a
    shared home is for — the spec is explicit that the same repository can
    be a home of two different units, and a shared library genuinely
    belongs to both. A global dedup would hand the file to whichever unit
    happened to sort first and silently drop it for the other, which is a
    unit losing its own documents, not a duplicate being removed. Order is
    the first occurrence within each unit, so it stays the stable, sorted
    order below.
    """
    artifact = registry.grammar.artifact_types[kind]
    pattern = artifact.pattern
    # `within` is the tree's word where the grammar has none: any directory
    # of that name, at any depth, scopes the search instead of the kind's
    # own container. The kind still says what is matched inside it.
    container_names = (within,) if within is not None else artifact.directories
    if unit is None:
        units = registry.units()
    elif isinstance(unit, Unit):
        units = [unit]
    else:
        units = [registry.resolve(unit)]

    found: list[Document] = []
    for one in units:
        # Once per unit per command, not once per kind: `find` runs for
        # every kind on every unit, and this resolves every unit's paths.
        cache = registry.__dict__.setdefault("_claimed", {})
        if one.name not in cache:
            cache[one.name] = _claimed_by(registry, one)
        excluded = cache[one.name]
        seen: set[Path] = set()
        for home in one.paths:
            for container in [c for n in container_names for c in _containers(home, n)]:
                # A directory kind is the container's children themselves;
                # a file kind is every matching file at any depth beneath.
                if artifact.is_directory:
                    matches = [p for p in sorted(container.glob(pattern)) if p.is_dir()]
                else:
                    matches = [p for p in sorted(container.rglob(pattern)) if p.is_file()]
                for path in matches:
                    resolved = path.resolve()
                    if resolved in seen:
                        continue
                    if any(
                        e == resolved or e in resolved.parents for e in excluded
                    ):
                        continue
                    if any(part.startswith(".") for part in path.relative_to(home).parts):
                        continue
                    seen.add(resolved)
                    found.append(Document(path.name, kind, path, one.name))
    return found


def loose(unit: Unit) -> list[Path]:
    """Top-level documents in each home — backlogs, handoffs, dated notes."""
    return sorted(
        p
        for home in unit.paths
        for p in home.glob("*.md")
        if p.is_file() and not p.name.startswith(".")
    )


def subdirectories(unit: Unit) -> list[Path]:
    """What each home actually holds, declared or not.

    The grammar says what a part is *for*; only the tree knows what is there —
    `archive/`, `infrastructure/` and `presentation/` are real and were never
    declared anywhere.
    """
    return sorted(
        d
        for home in unit.paths
        for d in _entries(home)
        if d.is_dir() and not d.name.startswith(".")
    )


def _entries(home: Path) -> list[Path]:
    """What a home holds, or nothing if it has gone. Never raises.

    `glob` and `rglob` already return empty for a missing directory; only
    `iterdir` raises, and a listing that raises on the one home someone
    deleted would take the whole view down with it.
    """
    try:
        return list(home.iterdir())
    except OSError:
        return []



# ── matchers ─────────────────────────────────────────────────────────────
#
# `find` scopes: which paths, from the grammar and the declarations. A
# matcher narrows the scoped list and says why each survivor did. Text is
# the first; anything that takes documents and returns documents — a date,
# a gate, an index of embeddings, a link graph — is the same shape and
# composes the same way.


def _files_of(found: Document) -> list[Path]:
    """What a matcher reads: the file, or every markdown file in the
    directory when the artifact is one."""
    if found.path.is_dir():
        return sorted(p for p in found.path.rglob("*.md")
                      if p.is_file() and not any(part.startswith(".") for part in p.relative_to(found.path).parts))
    return [found.path]


def grep(found: list[Document], pattern: str) -> list[Document]:
    """The documents whose text contains `pattern`, case-insensitively, with
    the matching lines attached. A regular expression when it is one."""
    import re
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error:
        rx = re.compile(re.escape(pattern), re.IGNORECASE)
    out: list[Document] = []
    for item in found:
        hits: list[dict] = []
        for file in _files_of(item):
            try:
                lines = file.read_text(errors="replace").splitlines()
            except OSError:
                continue
            for number, text in enumerate(lines, start=1):
                if rx.search(text):
                    hits.append({"file": str(file), "line": number, "text": text.strip()})
        if hits:
            out.append(Document(item.name, item.kind, item.path, item.unit, tuple(hits)))
    return out


def parse_window(text: str) -> int:
    """`2w`, `90d`, `6h` as seconds. Raises ValueError on anything else."""
    units = {"h": 3600, "d": 86400, "w": 7 * 86400, "m": 30 * 86400}
    body, suffix = text[:-1], text[-1:]
    if not body.isdigit() or suffix not in units:
        raise ValueError(f"cannot read '{text}' as a window; use a number and h, d, w or m")
    return int(body) * units[suffix]


def _touched(found: Document) -> float:
    """When the document was last edited: its mtime, or the newest file's
    inside a directory artifact. A file, not git: an edit in flight counts."""
    files = _files_of(found)
    newest = 0.0
    for file in files:
        try:
            newest = max(newest, file.stat().st_mtime)
        except OSError:
            continue
    return newest


def since(found: list[Document], seconds: int, now: float | None = None) -> list[Document]:
    """The documents touched within the last `seconds`."""
    import time
    cutoff = (now if now is not None else time.time()) - seconds
    return [d for d in found if _touched(d) >= cutoff]


def waiting(found: list[Document]) -> list[Document]:
    """The directory artifacts that are packets with a gate open — a node
    finished and asked, and nobody has answered. The question is attached
    as the match."""
    from orglens.workflow import session
    from orglens.workflow.definition import WorkflowError, load_workflow
    out: list[Document] = []
    for item in found:
        if not item.path.is_dir():
            continue
        facts = session.read(item.path)
        if not facts:
            continue
        bound = session.workflow_path(facts)
        workflow = None
        if bound is not None:
            try:
                workflow = load_workflow(bound)
            except WorkflowError:
                workflow = None
        if not session.gated(facts, workflow):
            continue
        question = None
        if workflow is not None:
            question = session.next_node(workflow, facts).question
        else:
            last = [f for f in facts if f["type"] in session.ROUTING][-1]
            question = last.get("question")
        hit = {"file": str(item.path / session.SESSION_FILE), "line": len(facts),
               "text": question or "review"}
        out.append(Document(item.name, item.kind, item.path, item.unit, (hit,)))
    return out
