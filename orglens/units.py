"""What units exist, and which one you are standing in.

Two operations with different requirements, and conflating them is what made
this hard. Resolution walks *up* from a directory until a marker turns up: no
roots, no index, no config, so a fresh clone answers immediately. Enumeration
sweeps the roots, and is the only thing that needs to know where to look.

A directory matching one of the grammar's old positional patterns but carrying
no declaration is a *candidate*, not a unit. That is the whole migration
worklist, and it is why nothing goes dark while the tree is half declared.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from orglens.declaration import MARKER, read_marker
from orglens.grammar import Grammar
from orglens.homes import Candidate, Home, resolve_home, scan_roots


@dataclass(frozen=True)
class Unit:
    name: str
    kind: str
    homes: tuple[Home, ...]
    part_of: str | None
    #: The directory whose marker declared it. One per unit; `check` says so
    #: when that stops being true.
    declared_at: Path
    #: scad's own words for a container, passed through verbatim by
    #: `scadconfig.render`. `None` when the declaration carries none.
    runtime: dict | None = None

    @property
    def paths(self) -> list[Path]:
        """Every home present on this machine. Absent homes are ordinary."""
        return [h.path for h in self.homes if h.path is not None]


class Registry:
    def __init__(self, roots: list[Path], grammar: Grammar):
        self.roots = [Path(r).expanduser() for r in roots]
        self.grammar = grammar
        self._candidates: list[Candidate] | None = None
        self._units: list[Unit] | None = None

    # ── the sweep ────────────────────────────────────────────────────────

    def _scan(self) -> list[Candidate]:
        if self._candidates is None:
            self._candidates = scan_roots(self.roots)
        return self._candidates

    def scan(self) -> list[Candidate]:
        """The raw sweep, for callers that need to reason about candidates
        directly rather than through a resolved `Unit` — `check`, checking
        whether a home name could have resolved to more than one directory.
        """
        return self._scan()

    def _homes_of(self, marker) -> tuple[Home, ...]:
        """Resolve a marker's declared homes, plus the directory it was
        found in — a home whether or not it named itself via `home:`.

        The spec documents a subfolder declaration that omits `home:`
        entirely, so `marker.home` can be absent while the directory is
        still, unambiguously, one of the unit's homes: it is where the
        declaration was read from. Checked by resolved path rather than by
        name, so a directory that *did* name itself and already resolved
        into `homes` below is not counted twice.

        Marked `how="declaring"` rather than `"marker"` — it is stronger
        evidence than any ladder rung (the marker was read from this exact
        directory, nothing was matched at all) but it is not a ladder
        answer, and `check`'s collision report walks the ladder again for
        every home name it sees. A directory named after its own code
        repository with no `home:` key is the ordinary case for a subfolder
        declaration, and re-running the ladder on its bare basename would
        "find" every unrelated directory sharing that name as a contested
        match that never actually occurred.
        """
        homes = tuple(resolve_home(name, self._scan()) for name in marker.homes)
        declaring = marker.path.resolve()
        if any(h.path is not None and h.path.resolve() == declaring for h in homes):
            return homes
        own = Home(
            name=marker.home or marker.path.name, path=marker.path, how="declaring"
        )
        return (own,) + homes

    def units(self) -> list[Unit]:
        """Every declared unit under the roots."""
        if self._units is not None:
            return self._units

        found: list[Unit] = []
        for candidate in self._scan():
            marker = read_marker(candidate.path)
            if marker is None or not marker.declares:
                continue
            found.append(
                Unit(
                    name=marker.unit,
                    kind=marker.kind or "",
                    homes=self._homes_of(marker),
                    part_of=marker.part_of,
                    declared_at=candidate.path,
                    runtime=marker.runtime,
                )
            )
        self._units = sorted(found, key=lambda u: u.name)
        return self._units

    # ── resolution ───────────────────────────────────────────────────────

    def at(self, path: Path) -> Unit | None:
        """The unit whose home contains this path, found by walking up.

        Deliberately independent of the sweep: it reads markers on the way up,
        so it answers in a container or a fresh clone where no index exists.
        Where several homes contain the path, the deepest wins.
        """
        here = Path(path).expanduser().resolve()
        for directory in [here, *here.parents]:
            marker = read_marker(directory)
            if marker is None:
                continue
            if marker.declares:
                return self._unit_from(marker, directory)
            if marker.home:
                for unit in self.units():
                    if any(h.name == marker.home for h in unit.homes):
                        return unit
        # No marker anywhere above. Fall back to the sweep, which knows homes
        # that carry no marker of their own because they resolved by remote or
        # by directory name.
        for unit in self.units():
            for home in unit.homes:
                resolved = home.path.resolve() if home.path else None
                if resolved and (resolved == here or resolved in here.parents):
                    return unit
        return None

    def _unit_from(self, marker, directory: Path) -> Unit:
        return Unit(
            name=marker.unit,
            kind=marker.kind or "",
            homes=self._homes_of(marker),
            part_of=marker.part_of,
            declared_at=directory,
            runtime=marker.runtime,
        )

    def resolve(self, name: str) -> Unit:
        """Resolve a partial name to a single unit."""
        units = self.units()
        for group in (
            [u for u in units if u.name == name],
            [u for u in units if u.name.startswith(name)],
            [u for u in units if name in u.name],
        ):
            if len(group) == 1:
                return group[0]
            if len(group) > 1:
                raise ValueError(
                    f"'{name}' matches multiple units: "
                    + ", ".join(u.name for u in group)
                )
        raise ValueError(
            f"No unit '{name}' found. Available: {', '.join(u.name for u in units)}"
        )

    def parts_of(self, unit: Unit) -> list[Unit]:
        """Units that declared themselves part of this one.

        Stated, never derived from folder depth — which is what lets a unit be
        regrouped without anything being renamed.
        """
        return [u for u in self.units() if u.part_of == unit.name]

    # ── what has not declared itself ─────────────────────────────────────

    def candidates(self) -> list[Path]:
        """Directories that look like work and carry no declaration.

        The grammar's positional patterns, demoted: they no longer say what
        exists, only what is worth asking about. A report, never a gate.

        Matched against the sweep rather than by `rglob` per pattern. The
        sweep is depth-bounded and already done; an unbounded `rglob` over a
        code root walks build output and dependency folders, which is the
        expense the whole index exists to avoid.

        Matched with `Path.match`, not `fnmatch`: `fnmatch`'s `*` crosses `/`,
        so `projects/*` would match `projects/orglens/specs` as readily as
        `projects/orglens` — every `specs/` and `plans/` in the tree offered
        up as a migration candidate, which is the same as reporting nothing.
        `Path.match` is right-anchored and stops at the separator.

        A directory nested *inside* a declared unit's home is owned by that
        unit, not undeclared — excluded whether or not it happens to be the
        home path exactly, which is why the test is "under a home" rather
        than "equal to a home".
        """
        owned = {u.declared_at.resolve() for u in self.units()} | {
            p.resolve() for u in self.units() for p in u.paths
        }
        found: list[Path] = []
        for candidate in self._scan():
            resolved = candidate.path.resolve()
            if any(resolved.is_relative_to(o) for o in owned):
                continue
            if any(
                candidate.path.match(et.pattern)
                for et in self.grammar.entity_types.values()
            ):
                found.append(candidate.path)
        return sorted(found)
