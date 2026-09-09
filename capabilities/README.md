# capabilities — the deck bank

The method layer of the scad + orglens ecosystem: a bank of **decks**, each a
self-contained bundle of operators and skills for one purpose.

| Tool | Owns |
|---|---|
| [`scad`](https://github.com/saptaxis/scoped-agent-dispatch) | where and how an agent runs, and what happened |
| [`orglens`](https://github.com/saptaxis/orglens) | what exists, how it is filed, what state it is in |
| `capabilities/` (here) | what you *do* with those — method, glued to the tools |

**The dependency arrow points one way: decks → the tools, never the reverse.**
The orglens engine has no reference to `capabilities/` at all, so a deck is
invoked *through* the tools and stays independently discardable.

This tree is **orglens-governed content** — the same relationship a documents
tree has with orglens. The engine reads this tree's grammar
(`.orglens-grammar.yml`) and content. A **grammar** describes an entire tree; a
**declaration** (`.orglens.yml`) describes one unit within it.

## The model: bank → deck → card

- **Bank** — this directory. All decks under one roof, one grammar.
- **Deck** — a themed, self-contained bundle: operators and/or skills for a
  purpose, plus the packs and state they need. Two kinds:
  - **Method decks** (general, cross-domain) — inception / verification /
    communication operators. Domain-agnostic; the packs carry the taste.
  - **Domain decks** (one recurring real task) — a full workflow with its own
    vocabulary and state.
- **Card** — a single operator or skill you deal out: a `SKILL.md`, an operator
  prompt, a named agent.

New decks accrete over time. A deck is just a directory — port one in or out
freely. See [`CONVENTIONS.md`](CONVENTIONS.md) for the anatomy, and the caveat
that it was reverse-engineered from one deck rather than designed.

**Both kinds are only illustrated here, not shipped.** The decks that carried
personal method moved to `orglens-extras` — see *Private decks* below. What
remains is `tutorial`, and it is not a stand-in: it is the check that the
engine is generic.

## Layout

```
orglens/
  bootstrap                # install the tool, route every deck's skills
  capabilities/
    .orglens-grammar.yml   # grammar: deck, operator, pack, agent as artifact types
    CONVENTIONS.md         # what a deck is — the anatomy to copy when adding one
    decks/
      tutorial/            # a three-node loop, run in five minutes
        DECK.md
        roles/             reproduce / fix / verify
        WORKFLOW.yaml
      <next deck>/         # the bank grows here
```

`tutorial` is the only deck this repo ships, and it earns the slot: it is a bug-triage loop that shares no vocabulary with any writing deck, which is what makes it evidence that the engine knows no nouns. Decks about work that cannot be published live in `orglens-extras`.

Canonical prompts live here once. `bootstrap` routes each deck's cards out with `npx skills add`, which walks a repo and owns the harness path table — a wrong skills path fails silently, so the tool decides it rather than a list here. Cards install as **copies**, not symlinks, so re-run `bootstrap` after editing one.

## Install

From the repo root — installs orglens into its own venv and routes the skills it ships:

```bash
./bootstrap                                    # editable, for co-developing
./bootstrap --pinned                           # a clean machine
./bootstrap --extras ~/code/orglens-extras     # include the private decks
```

A repo without a `pyproject.toml` is a deck repo: its skills are routed and nothing is pip-installed. scad installs itself from its own repo — the dependency runs one way, and `bootstrap` says so rather than reaching across.

To undo it:

```bash
./bootstrap --uninstall                        # shows the plan, then asks
./bootstrap --uninstall --extras ~/code/orglens-extras
```

It prints what it would remove and confirms once before doing any of it. `~/.agents/skills` is shared between repos and the skills tool records only where a skill is *installed*, never which repo put it there — so the match is by name, and you get to look at the list first.

**It never deletes `~/.orglens/events/`.** An attribution exists because a person said so and cannot be recomputed, which makes it the one thing here that is not a cache. Removing it is a deliberate act, not a flag on an installer.

## Status

Scaffold. Structure defined; **decks and operators harvested as they prove themselves on real problems — not designed up front.** The first domain deck was built before the pattern was named, and moved to `orglens-extras` when this repo went public — the anatomy it demonstrated is what stayed.

## Private decks

Decks about work that cannot be published live in a second repo, `orglens-extras`, with the same `capabilities/decks/` shape. Which repo a deck sits in *is* the public/private line — there is no list here, no flag in the engine, and nothing for orglens to read: the engine has no reference to `capabilities/` at all.

Installing a second deck repo needs no extra machinery, because skills install by walking a repo:

```bash
./bootstrap --extras ~/code/orglens-extras
```

which is the same `npx skills add . -g -a '*' -y --full-depth`, run once per repo. Whether you pass `--extras` is the whole of the choice — there is nothing to configure and nothing that remembers your answer.
