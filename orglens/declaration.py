# orglens/declaration.py
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

    @property
    def declares(self) -> bool:
        """Whether this marker defines a unit, rather than only naming a home."""
        return self.unit is not None


def read_marker(directory: Path) -> Marker | None:
    """The marker in this directory, or None if there is not a readable one."""
    path = Path(directory) / MARKER
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict):
        return None

    home = data.get("home")
    homes = tuple(data.get("homes") or ())
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
    )
