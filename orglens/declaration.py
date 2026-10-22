"""The marker file: what a directory is, and sometimes what unit it declares.

One filename for both, because a back-pointer is a declaration with fewer
keys. Every marker says which home its directory is; some also declare a unit
and list its homes. Exactly one marker per unit carries `homes` — `check`
reports it when that stops being true.

Nothing here raises. A malformed marker is reported as absent, because a
missing declaration must never make a directory invisible; `check` is what
tells you it is broken.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

MARKER = ".orglens.yml"


@dataclass(frozen=True)
class Marker:
    path: Path
    home: str | None = None
    unit: str | None = None
    kind: str | None = None
    part_of: str | None = None
    homes: tuple[str, ...] = ()
    #: scad's own words for a container — `python:`, `claude:`, and the
    #: like — passed through verbatim. orglens has no vocabulary for a
    #: runtime; inventing one for a single consumer would be a translation
    #: layer nobody asked for.
    runtime: dict | None = None
    #: Other names the person calls the unit by (`aliases: [scad]`). A name
    #: resolves to the unit by any of them; the unit's own name is still
    #: `unit:`, and every listing shows that one.
    aliases: tuple[str, ...] = ()
    #: Homes written `- name: data`: the unit's, shown and mounted like any
    #: other, but holding data rather than documents, so never searched.
    data_homes: tuple[str, ...] = ()
    #: `homes:` entries that are neither a name nor `name: data`, as written.
    #: Left out of `homes`; `check` reports them.
    bad_homes: tuple[str, ...] = ()

    @property
    def declares(self) -> bool:
        """Whether this marker defines a unit, rather than only naming a home."""
        return self.unit is not None


def read_marker(directory: Path) -> Marker | None:
    """The marker in this directory, or None if there is not a readable one."""
    path = Path(directory) / MARKER
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, ValueError, yaml.YAMLError):
        # ValueError catches UnicodeDecodeError from read_text() on invalid
        # UTF-8: a corrupt file must not be louder than a missing one.
        return None
    if not isinstance(data, dict):
        return None

    home = data.get("home")
    homes, data_homes, bad_homes = _homes(data.get("homes"))
    # The declaring home is one of the unit's homes whether or not it was
    # listed: it is the directory the declaration was found in, which is a
    # fact about the filesystem rather than something a human should restate.
    if data.get("unit") and home and home not in homes:
        homes = (home,) + homes

    return Marker(
        path=Path(directory),
        home=home,
        unit=data.get("unit"),
        kind=data.get("kind"),
        part_of=data.get("part_of"),
        homes=homes,
        runtime=data.get("runtime"),
        aliases=_names(data.get("aliases")),
        data_homes=data_homes,
        bad_homes=bad_homes,
    )


def _homes(value) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """`homes:` as (every name, the ones marked data, entries not understood).

    An entry is a name, or a one-key mapping `name: data`. Every other
    reader of `homes` sees names only.
    """
    names, data, bad = [], [], []
    for entry in value if isinstance(value, list) else []:
        if isinstance(entry, str):
            names.append(entry)
        elif (isinstance(entry, dict) and len(entry) == 1
              and isinstance(name := next(iter(entry)), str)
              and entry[name] == "data"):
            names.append(name)
            data.append(name)
        else:
            bad.append(str(entry))
    return tuple(names), tuple(data), tuple(bad)


def _names(value) -> tuple[str, ...]:
    """`aliases:` as a list, or one name written bare. Anything else is no
    alias: a malformed key must not hide the unit."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return ()
    return tuple(str(v).strip() for v in value if str(v).strip())
