"""`orglens chain <verb> <packet>`: next, done, note, goto.

The packet is a directory. The deck comes from the log's `deck` line;
`--deck` overrides it and, on a packet with no log yet, writes that line.

Exit codes: 0 for `next` on a runnable stage, complete, or waiting; 1 for a
log naming a stage the deck no longer has; 2 for a bad deck or a refused
write. Cards and dispatchers read `--json`; humans read the text.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from orglens.chain import session
from orglens.chain.deck import Deck, DeckError, load_deck
from orglens.chain.session import Position, State


def _fail(message: str, code: int = 2) -> None:
    click.echo(message, err=True)
    sys.exit(code)


def _load(packet: Path, deck_opt: str | None) -> tuple[Deck, list[dict]]:
    """The deck and the log. Binds the packet when `--deck` names a deck it
    has none of; refuses a second, different binding."""
    facts = session.read(packet)
    bound = session.deck_path(facts)
    if deck_opt is not None:
        given = Path(deck_opt).expanduser().resolve()
        if bound is None:
            session.bind(packet, given)
            facts = session.read(packet)
        elif bound.resolve() != given:
            _fail(f"{packet} is bound to {bound}; --deck names {given}")
        path = given
    elif bound is not None:
        path = bound
    else:
        _fail("no deck bound: pass --deck once to bind this packet")
    try:
        return load_deck(path), facts
    except DeckError as exc:
        _fail(str(exc))
    raise AssertionError("unreachable")


def _describe(packet: Path, pos: Position) -> dict:
    return {
        "state": pos.state.value,
        "stage": pos.stage.name if pos.stage else None,
        "card": str(pos.stage.card) if pos.stage else None,
        "write": str(packet / pos.stage.writes) if pos.stage else None,
        "note": pos.note,
    }


@click.group()
def chain():
    """A linear chain of passes over one packet, with a human between."""


@chain.command(name="next")
@click.argument("packet", type=click.Path(file_okay=False, path_type=Path))
@click.option("--deck", "deck_opt", default=None, help="Bind or override the deck.")
@click.option("--json", "as_json", is_flag=True)
def next_cmd(packet: Path, deck_opt: str | None, as_json: bool):
    """What to run next, or why nothing can run."""
    deck, facts = _load(packet, deck_opt)
    pos = session.next_stage(deck, facts)

    if as_json:
        out = _describe(packet, pos)
        if pos.state == State.WAITING:
            out["question"] = pos.question
        click.echo(json.dumps(out))
        sys.exit(1 if pos.state == State.UNKNOWN else 0)

    if pos.state == State.RUNNABLE:
        click.echo(f"stage: {pos.stage.name}")
        click.echo(f"card:  {pos.stage.card}")
        click.echo(f"write: {packet / pos.stage.writes}")
        if pos.note:
            click.echo(f"note:  {json.dumps(pos.note)}")
    elif pos.state == State.WAITING:
        click.echo(f"waiting on: {pos.question}            (after stage {pos.after})")
    elif pos.state == State.COMPLETE:
        click.echo("complete")
    else:
        _fail(f"unknown stage in log: {pos.after}", code=1)


@chain.command()
@click.argument("packet", type=click.Path(file_okay=False, path_type=Path))
@click.option("--stage", required=True)
@click.option("--agent", required=True, help="Who performed the card: claude, codex, ...")
@click.option("--question", default=None, help="Ask the human before the next stage.")
@click.option("--deck", "deck_opt", default=None)
@click.option("--force", is_flag=True, help="Finish a stage the chain is not on.")
def done(packet: Path, stage: str, agent: str, question: str | None,
         deck_opt: str | None, force: bool):
    """Record that a stage finished. Refuses a stage the chain is not on."""
    deck, facts = _load(packet, deck_opt)
    target = deck.stage(stage)
    if target is None:
        _fail(f"'{stage}' is not a stage of {deck.name}: "
              + ", ".join(s.name for s in deck.stages))
    pos = session.next_stage(deck, facts)
    if not force:
        if pos.state == State.WAITING:
            _fail(f"waiting on: {pos.question} (after stage {pos.after}); "
                  "answer it with `note`, or move with `goto`")
        if pos.state == State.COMPLETE:
            _fail(f"{deck.name} is complete; `goto` a stage to run it again")
        if pos.stage is None or pos.stage.name != stage:
            on = pos.stage.name if pos.stage else pos.after
            _fail(f"the chain is on {on}, not {stage}; --force records it anyway")

    fact = {"type": "done", "stage": stage, "agent": agent,
            "wrote": [target.writes] if (packet / target.writes).exists() else []}
    if question:
        fact["question"] = question
    if force:
        fact["forced"] = True
    session.append(packet, fact)
    click.echo(f"done: {stage}" + (f" (asks: {question})" if question else ""))


@chain.command()
@click.argument("packet", type=click.Path(file_okay=False, path_type=Path))
@click.argument("text")
def note(packet: Path, text: str):
    """Answer the open gate. The text is handed to the next card verbatim."""
    deck, facts = _load(packet, None)
    pos = session.next_stage(deck, facts)
    if pos.state != State.WAITING:
        _fail("no gate is open")
    last = [f for f in facts if f["type"] in session.ROUTING][-1]
    session.append(packet, {"type": "note", "resolves": last["id"], "text": text})
    click.echo(f"noted; next: {pos.stage.name if pos.stage else 'complete'}")


@chain.command()
@click.argument("packet", type=click.Path(file_okay=False, path_type=Path))
@click.option("--stage", required=True, help="The stage to run next.")
@click.option("--why", required=True)
@click.option("--deck", "deck_opt", default=None)
def goto(packet: Path, stage: str, why: str, deck_opt: str | None):
    """Point the chain at a stage. Clears any open gate; `why` is the note."""
    deck, _ = _load(packet, deck_opt)
    if deck.stage(stage) is None:
        _fail(f"'{stage}' is not a stage of {deck.name}: "
              + ", ".join(s.name for s in deck.stages))
    session.append(packet, {"type": "goto", "stage": stage, "why": why})
    click.echo(f"next: {stage}")

