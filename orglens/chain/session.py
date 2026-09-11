"""The packet's log, and the two things derived from it.

`session.jsonl` is append-only. Each line is a fact about the past: a stage
finished, a human answered, a human pointed somewhere. Nothing is rewritten,
so nothing here can go stale.

Where the chain stands is read off the last routing fact (`done` or `goto`);
whether it is waiting is read off that same fact and whether a `note` answers
it. Neither is stored.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from orglens.chain.deck import Deck, Stage

LOG = "session.jsonl"

#: What each fact type must carry, beyond `type`, `at` and `id`.
REQUIRED: dict[str, tuple[str, ...]] = {
    "deck": ("path",),
    "done": ("stage", "agent"),
    "note": ("resolves", "text"),
    "goto": ("stage", "why"),
}

ROUTING = frozenset({"done", "goto"})


class SessionError(ValueError):
    """A fact the log will not take, or a binding that is already made."""


class State(str, Enum):
    RUNNABLE = "runnable"
    WAITING = "waiting"
    COMPLETE = "complete"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Position:
    state: State
    #: The stage to run next. None when complete or unknown.
    stage: Stage | None = None
    #: The stage the last routing fact named; what a gate or an unknown is after.
    after: str | None = None
    #: What the human said: the note answering the last gate, or a goto's why.
    note: str | None = None
    #: While waiting, what is being waited on.
    question: str | None = None


def read(packet: Path) -> list[dict]:
    """Every fact, in order. A broken line is skipped: a log that refuses to
    be read because one line is bad loses everything for the sake of one."""
    path = Path(packet) / LOG
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text().splitlines():
        try:
            fact = json.loads(line)
        except ValueError:
            continue
        if isinstance(fact, dict) and fact.get("type") in REQUIRED:
            out.append(fact)
    return out


def _validate(fact: dict) -> None:
    kind = fact.get("type")
    if kind not in REQUIRED:
        raise SessionError(f"unknown fact type: {kind!r}")
    for key in REQUIRED[kind]:
        if not fact.get(key):
            raise SessionError(f"a {kind} fact needs {key!r}")


def append(packet: Path, fact: dict) -> dict:
    """Stamp, validate, write. The fact on disk is valid by construction."""
    stamped = {**fact, "at": datetime.now().astimezone().isoformat(timespec="seconds"),
               "id": secrets.token_hex(6)}
    _validate(stamped)
    path = Path(packet) / LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(stamped, sort_keys=True) + "\n")
    return stamped


def deck_path(facts: list[dict]) -> Path | None:
    """The deck this packet is bound to, from its `deck` line."""
    for fact in facts:
        if fact["type"] == "deck":
            return Path(fact["path"]).expanduser()
    return None


def bind(packet: Path, deck: Path) -> dict:
    """Write the `deck` line. Once: a packet runs one deck."""
    if deck_path(read(packet)) is not None:
        raise SessionError(f"{packet} is already bound to a deck")
    return append(packet, {"type": "deck", "path": str(deck)})


def next_stage(deck: Deck, facts: list[dict]) -> Position:
    """The whole of the engine's reasoning, from the last routing fact."""
    routing = [f for f in facts if f["type"] in ROUTING]
    if not routing:
        return Position(State.RUNNABLE, stage=deck.stages[0])

    last = routing[-1]
    named = deck.stage(last["stage"])
    if named is None:
        return Position(State.UNKNOWN, after=last["stage"])

    if last["type"] == "goto":
        return Position(State.RUNNABLE, stage=named, after=named.name, note=last["why"])

    following = deck.after(named.name)
    answer = next(
        (f["text"] for f in facts if f["type"] == "note" and f.get("resolves") == last["id"]),
        None,
    )
    asked = last.get("question")
    if (asked or named.review) and answer is None:
        question = asked or f"review before {following.name if following else 'complete'}"
        return Position(State.WAITING, stage=following, after=named.name, question=question)
    if following is None:
        return Position(State.COMPLETE, after=named.name, note=answer)
    return Position(State.RUNNABLE, stage=following, after=named.name, note=answer)
