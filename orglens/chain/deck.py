"""Load and validate a `CHAIN.yaml`.

Validation is all of it: stages non-empty, names unique, every card a file
that exists, every stage naming what it writes. Nothing else is declared —
no guards, no reads, no roots. A card says in its own prose what it loads.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


class DeckError(ValueError):
    """A deck file the engine will not run. Raised at load, never later."""


@dataclass(frozen=True)
class Stage:
    name: str
    #: Resolved against the deck directory at load; exists, or the load failed.
    card: Path
    #: The one file this stage produces, relative to the packet.
    writes: str
    #: Finishing this stage opens a gate.
    review: bool = False


@dataclass(frozen=True)
class Deck:
    name: str
    path: Path
    stages: tuple[Stage, ...]

    def stage(self, name: str) -> Stage | None:
        return next((s for s in self.stages if s.name == name), None)

    def after(self, name: str) -> Stage | None:
        """The stage following `name`, or None if it is the last."""
        names = [s.name for s in self.stages]
        i = names.index(name)
        return self.stages[i + 1] if i + 1 < len(self.stages) else None


def load_deck(path: Path) -> Deck:
    path = Path(path).expanduser()
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except OSError as exc:
        raise DeckError(f"cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise DeckError(f"{path} is not valid YAML: {exc}") from exc

    stages_raw = raw.get("stages") or []
    if not stages_raw:
        raise DeckError(f"{path}: no stages")

    here = path.parent
    stages: list[Stage] = []
    seen: set[str] = set()
    for i, item in enumerate(stages_raw):
        if not isinstance(item, dict) or not item.get("name"):
            raise DeckError(f"{path}: stage {i + 1} has no name")
        name = str(item["name"])
        if name in seen:
            raise DeckError(f"{path}: stage name '{name}' appears twice")
        seen.add(name)
        if not item.get("card"):
            raise DeckError(f"{path}: stage '{name}' has no card")
        card = (here / str(item["card"])).resolve()
        if not card.is_file():
            raise DeckError(f"{path}: stage '{name}' names a card that does not exist: {item['card']}")
        if not item.get("writes"):
            raise DeckError(f"{path}: stage '{name}' does not say what it writes")
        stages.append(Stage(
            name=name, card=card, writes=str(item["writes"]),
            review=bool(item.get("review", False)),
        ))
    return Deck(name=str(raw.get("deck") or path.parent.name), path=path, stages=tuple(stages))
