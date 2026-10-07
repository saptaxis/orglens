"""Units kept off what is drawn on screen.

For showing the setup to someone: `interview-prep` should not be on the page
during a screen share. Only what draws for a person hides them --- `view`,
`tree`, `list`, `status`, `sessions`. What agents and scripts read
(`snapshot`, `--json`, `find`, `where`) never does, and naming a hidden unit
explicitly still shows it. Every display that hid something says how many,
so a hide nobody remembers is noticed.
"""

from __future__ import annotations

import re
from pathlib import Path

from orglens import tree as tree_mod


def expand(shape: tree_mod.Tree, names, named: str | None = None) -> set[str]:
    """Every unit hidden: each name and its subtree. `named` is the unit a
    command was asked about by name; when it is hidden, it and its subtree
    are shown, since asking for it is the point."""
    out: set[str] = set()
    for name in names:
        out.update(tree_mod.below(shape, name))
    if named is not None and named in out:
        out -= set(tree_mod.below(shape, named))
    return out


#: A top-level `hide:` key and the list under it.
_BLOCK = re.compile(r"^hide:.*\n(?:[ \t]+.*\n|[ \t]*\n(?=[ \t]))*", re.MULTILINE)


def write(path: Path, names: list[str]) -> None:
    """Set the config's `hide:` list, leaving every other line --- comments
    included --- as it was. Nothing hidden is `hide: []`, so the key and its
    comment stay together for the next `hide`."""
    text = path.read_text()
    if text and not text.endswith("\n"):
        text += "\n"
    block = ("hide:\n" + "".join(f"  - {n}\n" for n in names)) if names else "hide: []\n"
    if _BLOCK.search(text):
        text = _BLOCK.sub(lambda _: block, text, count=1)
    elif names:
        text += "\n# Units kept off the screen, each with what is under it (orglens hide).\n" + block
    path.write_text(text)
