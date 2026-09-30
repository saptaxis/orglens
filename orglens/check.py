"""Where the tree has drifted from what the grammar describes, and what has
not declared itself at all.

An audit, never a gate. Nothing calls it, nothing is hidden or blocked by what
it finds, and it always exits 0. It exists so drift can be cleaned up when you
feel like tidying — which is the opposite of the previous design, where the
same information was expressed by making four real entities invisible.

It reports declared units only for drift. Once filenames stopped being
parsed, the 88 documents that do not match a template stopped being defects:
they are the other two naming conventions actually in use, and listing them
would be noise. What has not declared itself at all is a different question,
answered by `undeclared` — the migration worklist, and the reason nothing
goes dark while the tree is half declared.

A glob that matches nothing anywhere is a different silent failure again —
not an undeclared directory, but a mistyped or misplaced pattern that quietly
stops finding documents it should. A capabilities glob once pointed one
directory too high and found nothing, and nothing said so. `unmatched` is
what says so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import get_close_matches
from pathlib import Path

from orglens import activity, documents, formats
from orglens.state import unit_status
from orglens.homes import Candidate, candidates_for
from orglens.units import Registry


@dataclass(frozen=True)
class Missing:
    name: str
    #: A file already present whose name is close. Two of four real cases are
    #: a near-miss rather than an absence, and saying so is what makes this
    #: worth running instead of a scold.
    resembles: str | None = None


@dataclass(frozen=True)
class Drift:
    #: The unit, not one of its homes. A declared file belongs to whichever
    #: home the grammar's structure actually implies — a code repository
    #: should never carry `overview.md` — so naming a home here would point
    #: the fix at the wrong place as often as the right one.
    entity: str
    missing: list[Missing] = field(default_factory=list)


@dataclass(frozen=True)
class Duplicate:
    """A unit name declared by more than one marker — a `cp -R`, a git
    worktree, a Dropbox conflicted copy, a template folder. Left unreported,
    every consumer that resolves this name by exact match raises, which used
    to take `status`, `view`, `snapshot` and `find` down for every unit, not
    only this one.
    """
    name: str
    paths: list[Path] = field(default_factory=list)


@dataclass(frozen=True)
class Collision:
    """A home name that more than one candidate directory could have
    answered for — the ladder still picks one, by scan order, but the tie
    is real. `weak` says a resolution is fragile; this says it was actually
    contested.
    """
    unit: str
    home: str
    paths: list[Path] = field(default_factory=list)


@dataclass(frozen=True)
class Shared:
    """A home declared on more than one unit. Sharing is intended — one
    repository can be a home of two units when both work in it — but `where`
    inside that directory answers one of them, and which one is a fact worth
    seeing: `Registry.at` takes the first by unit name, and `units` is in
    that order.
    """
    home: str
    units: list[str] = field(default_factory=list)


#: How many documents make a directory a folder of documents rather than a
#: package with a README in it. On the real tree, 116 of 158 undescribed
#: directories held one file and nine held two; the 42 at three or more
#: were the ones worth a word.
UNDESCRIBED_FLOOR = 3


@dataclass(frozen=True)
class Twin:
    """One document written twice, in two formats, side by side — an
    `overview.md` beside an `overview.org`. Only one is read: the grammar's
    format wins (R11). The other is either a leftover of a conversion or a
    fork nobody meant, and a person decides which."""
    unit: str
    #: The shared stem, without a suffix.
    path: Path


@dataclass(frozen=True)
class Undescribed:
    """A directory holding documents that no kind's container and no
    entity's structure names. Everything in it is still found by the
    catch-all kind, so nothing is lost; what is missing is a word. The grammar can grow one,
    or the folder can knowingly stay `doc`. Either way, somebody decides.
    """
    unit: str
    path: Path
    count: int


@dataclass(frozen=True)
class Unlisted:
    """A unit whose parent directory carries a `.nav.yml` listing children
    by name, without this one. mkdocs-awesome-nav renders only what an
    explicit list names, so the unit exists and the site does not show it.
    One sibling file orglens knows about; a nav with a glob needs nothing.
    """
    unit: str
    nav: Path


@dataclass(frozen=True)
class Stale:
    """The unit's status line is older than its newest edit by more than a
    week: the tree moved and the person's sentence did not. The line is the
    one authored fact `status` and `view` show, so a stale one misleads
    every reader until it is rewritten."""
    unit: str
    days: int


@dataclass(frozen=True)
class Held:
    """One session id with more than one live process on it. Two writers on
    one transcript is how a session forks: of the six doubly held on this
    machine three stayed clean, two forked outright and one needed seven
    interrupted-turn repairs. Reported, never gated — which pane to keep is
    the person's call."""
    session: str
    label: str | None
    panes: tuple


@dataclass(frozen=True)
class Report:
    drifted: list[Drift] = field(default_factory=list)
    #: Directories that look like work and have not declared themselves. The
    #: migration worklist, and the reason nothing goes dark while the tree is
    #: half declared.
    undeclared: list[Path] = field(default_factory=list)
    #: (unit, home, how) rows where identity came only from the directory
    #: name, or from a git remote's repository-name tail while some other
    #: scanned candidate shares that same tail. Both discard information a
    #: marker would have kept, but they are not equally dangerous: a bare
    #: name is fragile the moment that one directory is renamed, whether or
    #: not anything collides today, so it is always reported. A remote tail
    #: is only a hazard when an owner collision is actually live among the
    #: candidates on disk — on a real tree every home resolves through the
    #: remote rung, so reporting it unconditionally drowned the rows that
    #: are an actual worklist in noise that fires whether or not the risk is
    #: real. `how` is carried so the printer can say which of the two
    #: actually happened, rather than always naming the first.
    weak: list[tuple[str, str, str]] = field(default_factory=list)
    #: (unit, home name) for every home that resolved nowhere: its repository
    #: is under no root, or it is not cloned on this machine.
    absent: list[tuple[str, str]] = field(default_factory=list)
    #: Document kinds whose glob matches nothing anywhere. A mistyped glob
    #: finds no documents and raises nothing, so without this it fails
    #: silently — the one way this design can still go wrong quietly.
    unmatched: list[str] = field(default_factory=list)
    #: Unit names declared by more than one marker.
    duplicates: list[Duplicate] = field(default_factory=list)
    #: Home names more than one candidate directory could have satisfied.
    collisions: list[Collision] = field(default_factory=list)
    #: Home names declared on more than one unit.
    shared: list[Shared] = field(default_factory=list)
    #: Folders of documents the grammar has no word for.
    undescribed: list[Undescribed] = field(default_factory=list)
    #: Documents written in two formats side by side (R11).
    twins: list[Twin] = field(default_factory=list)
    #: Units an explicit parent nav does not list.
    unlisted: list[Unlisted] = field(default_factory=list)
    #: Status lines older than the unit's newest edit by more than a week.
    stale: list[Stale] = field(default_factory=list)
    #: Sessions with two live processes on one id.
    held: list[Held] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(
            self.drifted
            or self.undeclared
            or self.weak
            or self.absent
            or self.unmatched
            or self.duplicates
            or self.collisions
            or self.shared
            or self.undescribed
            or self.twins
            or self.unlisted
            or self.stale
            or self.held
        )


def run(registry: Registry, sessions: list | None = None) -> Report:
    units = registry.units()
    drifted = []

    for unit in units:
        # `kind` is a free-ish label and need not be a key in the grammar's
        # entity types — an unknown kind means no declared files to check,
        # not a crash.
        declared = (
            registry.grammar.entity_types[unit.kind].files
            if unit.kind in registry.grammar.entity_types
            else {}
        )
        if not declared:
            continue

        # What each home actually holds, gathered once so a declared file
        # can be checked against every home before it is called missing —
        # a documents home carrying `overview.md` clears the code homes
        # that a unit also lives in, which should never carry that file.
        present_by_home: list[list[str]] = []
        for home in unit.paths:
            try:
                present_by_home.append([p.name for p in home.iterdir()])
            except OSError:
                # A home can vanish between the sweep and the read. An audit
                # that raises on the thing it is auditing is worse than one
                # that reports nothing about it.
                continue

        missing = []
        suffix = formats.get(registry.grammar.format).suffix
        for name in declared:
            # A declared document is present in any registered format (R2);
            # when absent it is named as `new` would write it.
            written = {name} | {formats.stem(name) + s for s in formats.SUFFIXES}
            if any(written & set(present) for present in present_by_home):
                continue
            shown = name if Path(name).suffix in formats.SUFFIXES else name + suffix
            # The file that resembles this one may live in a home that was
            # not the first checked, so the hint has to search all of them.
            close = None
            for present in present_by_home:
                match = get_close_matches(shown, present, n=1, cutoff=0.55)
                if match:
                    close = match[0]
                    break
            missing.append(Missing(name=shown, resembles=close))
        if missing:
            drifted.append(Drift(entity=unit.name, missing=missing))

    # The same scan and the same `candidates_for` the collision report below
    # uses — reused, not re-run, and cached per home name since several units
    # can share one. A rung a home actually resolved through is guaranteed to
    # be the rung `candidates_for` reports rivals at, since both walk the same
    # `_rungs` over the same candidates.
    scan = registry.scan()
    rivals_by_home: dict[str, list[Candidate]] = {}

    def rivals_for(home_name: str) -> list[Candidate]:
        if home_name not in rivals_by_home:
            rivals_by_home[home_name] = candidates_for(home_name, scan)
        return rivals_by_home[home_name]

    # `name` discards everything but a directory's basename, and is fragile
    # regardless of what else is on disk today — renaming that one directory
    # detaches it whether or not anything currently collides, so it is always
    # weak. `remote` discards the host and owner, keeping only the
    # repository-name tail, but that looseness is only a live hazard when
    # some other scanned candidate actually shares the tail — on the real
    # tree every home resolves through this rung, so flagging it
    # unconditionally reported a risk that was present nowhere and drowned
    # the rows that matter.
    weak = [
        (unit.name, home.name, home.how)
        for unit in units
        for home in unit.homes
        if home.how == "name"
        or (home.how == "remote" and len(rivals_for(home.name)) > 1)
    ]

    # `documents.find` matches a kind's container by name at any depth
    # rather than taking the glob text literally, so a document one level
    # below where the pattern's text reaches — `plans/archive/x.md` for
    # `plans/*.md` — still counts as a match rather than a false unmatched.
    unmatched = [
        name
        for name in registry.grammar.artifact_types
        if not documents.find(registry, name)
    ]

    by_name: dict[str, list[Path]] = {}
    for unit in units:
        by_name.setdefault(unit.name, []).append(unit.declared_at)
    duplicates = [
        Duplicate(name=name, paths=sorted(paths))
        for name, paths in sorted(by_name.items())
        if len(paths) > 1
    ]

    seen: set[tuple[str, str]] = set()
    collisions = []
    for unit in units:
        for home in unit.homes:
            # `declaring` and `absent` never walked the ladder in the first
            # place — `declaring` is the directory a marker was read from,
            # pinned directly rather than resolved by name, and re-running
            # the ladder on its bare basename (the ordinary case for a
            # subfolder declaration with no `home:` key) would "find" every
            # unrelated directory sharing that name as a contest that never
            # happened. Only a name the ladder actually walked can have been
            # actually contested.
            if home.how not in ("marker", "remote", "name"):
                continue
            key = (unit.name, home.name)
            if key in seen:
                continue
            seen.add(key)
            rivals = rivals_for(home.name)
            if len(rivals) > 1:
                collisions.append(
                    Collision(
                        unit=unit.name,
                        home=home.name,
                        paths=sorted(c.path for c in rivals),
                    )
                )

    # `units` is sorted by name, so the first unit listed under a home is
    # the one `at` answers with inside it.
    units_by_home: dict[str, list[str]] = {}
    for unit in units:
        for home in unit.homes:
            if home.how == "declaring":
                continue
            if unit.name not in units_by_home.setdefault(home.name, []):
                units_by_home[home.name].append(unit.name)
    shared = [
        Shared(home=name, units=names)
        for name, names in sorted(units_by_home.items())
        if len(names) > 1
    ]

    # A directory is described when a kind's container or an entity's
    # structure names it, or an ancestor of it — `plans/archive/` is inside
    # `plans/`. The unit's own root is `doc`'s container and is left out;
    # so is any directory a nested unit's home claims.
    grammar = registry.grammar
    named = {
        name
        for at in grammar.artifact_types.values()
        for name in at.directories if name
    } | {
        key.rstrip("/")
        for et in grammar.entity_types.values()
        for key in et.directories
    }
    undescribed: list[Undescribed] = []
    for unit in units:
        claimed = documents._claimed_by(registry, unit)
        for home in unit.paths:
            for directory in documents._dirs_under(home):
                rel = directory.relative_to(home)
                if any(part in named for part in rel.parts):
                    continue
                if any(directory == c or c in directory.parents for c in claimed):
                    continue
                count = sum(1 for p in documents._entries(directory)
                            if p.is_file() and formats.is_document(p))
                if count >= UNDESCRIBED_FLOOR:
                    undescribed.append(Undescribed(unit=unit.name, path=directory, count=count))

    twins: list[Twin] = []
    for unit in units:
        for home in unit.paths:
            for directory in (home, *documents._dirs_under(home)):
                stems: dict[str, int] = {}
                for p in documents._entries(directory):
                    if p.is_file() and formats.is_document(p):
                        key = formats.stem(p.name)
                        stems[key] = stems.get(key, 0) + 1
                twins += [Twin(unit=unit.name, path=directory / s)
                          for s, n in sorted(stems.items()) if n > 1]

    unlisted = [
        Unlisted(unit=unit.name, nav=unit.declared_at.parent / ".nav.yml")
        for unit in units
        if _nav_omits(unit.declared_at.parent / ".nav.yml", unit.declared_at.name)
    ]

    stale: list[Stale] = []
    for unit in units:
        status = unit_status(unit.paths, grammar.documents_for(unit.kind), grammar.format)
        if status is None or not status.edited:
            continue
        newest = max((activity._newest_mtime(p) or 0) for p in unit.paths)
        if newest - status.edited > 7 * 86400:
            stale.append(Stale(unit=unit.name, days=int((newest - status.edited) // 86400)))

    held = [
        Held(session=s.id, label=s.label,
             panes=tuple(h.get("pane") or f"pid {h.get('pid')}"
                         for h in s.also_held_by))
        for s in (sessions or []) if getattr(s, "also_held_by", ())
    ]

    return Report(
        drifted=drifted,
        undeclared=registry.candidates(),
        weak=weak,
        absent=[(u.name, h.name) for u in units for h in u.homes if h.how == "absent"],
        unmatched=unmatched,
        duplicates=duplicates,
        collisions=collisions,
        shared=shared,
        undescribed=sorted(undescribed, key=lambda u: (u.unit, u.path)),
        twins=twins,
        unlisted=unlisted,
        stale=stale,
        held=held,
    )


def _nav_omits(nav: Path, name: str) -> bool:
    """Whether `nav` is an explicit list that leaves `name` out."""
    if not nav.is_file():
        return False
    try:
        items = [l.strip()[2:] for l in nav.read_text().splitlines() if l.startswith("  - ")]
    except OSError:
        return False
    if not items or any("*" in item for item in items):
        return False
    listed = {item.split(":")[-1].strip().strip("'\"") for item in items} | {item.strip("'\"") for item in items}
    return name not in listed
