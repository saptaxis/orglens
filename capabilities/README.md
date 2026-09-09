# orgdeck

> Private. The personal layer of the scad + orglens ecosystem — your **bank of decks**.

`orgdeck` is the third pillar of a three-part agent workflow. The other two are public tools; this one is private, because it holds personal taste and method, not general mechanism.

| Pillar | Repo | Owns |
|---|---|---|
| Execution / isolation / companion | [`scad`](https://github.com/saptaxis/scoped-agent-dispatch) (public) | where & how an agent runs, and what happened |
| Taxonomy / semantic grammar | [`orglens`](https://github.com/saptaxis/orglens) (public) | what exists, how it's filed, what state it's in |
| **Decks — operators, skills, packs, config** | **`orgdeck`** (private) | what *I* do with these — my method, glued to the tools |

**The dependency arrow points one way: `orgdeck` → the public tools, never the reverse.** scad and orglens never know orgdeck exists; orgdeck is invoked *through* them and stays independently discardable. Nothing personal ever leaks into the public repos.

orgdeck is an **orglens-governed content tree** — the same relationship [`traitful-docs`](../../traitful-code/traitful-docs) has with orglens. orglens (public engine) reads orgdeck's private grammar (`.orglens-grammar.yml`) and content. The lens stays public; what it looks into is private. A **grammar** describes an entire tree; a **declaration** (`.orglens.yml`) describes one unit within it.

## The model: bank → deck → card

- **Bank** — this repo. Holds all your decks under one roof, one install, one grammar.
- **Deck** — a themed, self-contained bundle: operators and/or skills for a purpose, plus the packs and state they need. Two kinds:
  - **Method decks** (general, cross-domain) — e.g. `method`: the inception / verification / communication operators. Domain-agnostic; the packs carry the taste.
  - **Domain decks** (one recurring real task) — e.g. `interior-design`: a full workflow with its own vocabulary and state.
- **Card** — a single operator or skill you deal out (a `SKILL.md`, an operator prompt, a named agent).

New decks accrete over time. A deck is just a directory — port one in or out freely. See [`CONVENTIONS.md`](CONVENTIONS.md) for the deck anatomy.

## The method deck (first deck)

Three operator families ([design notes](../../traitful-code/traitful-docs/docs/projects/traitful-workflow-ecosystem/logs/02-orchestration-and-planning-Jul222026-log.md) Part D):

- **Inception** (diverge) — `breadth-framer`, `data-profiler`, `scaffolder` + triangulation. Generate options; *you* converge.
- **Verification** (prune) — `leakage-hunter`, `metric-auditor`, `baseline-skeptic`, `assumption-checker`. Decorrelated critics; adversarial.
- **Communication** (cross-cutting) — `labnotebook-logger`, `essay-drafter`, `deliverable-writer` + `humanizer`. Reads *from* the capture layer; different polish for different audiences.

Parameterized by **bias-packs** (breadth-framer's anti-default lenses, per domain) and **voice-packs** (personal register). The operators are the skeleton; the packs are where taste lives and accretes.

## Layout

```
orgdeck/
  bootstrap              # install everything on a new macOS/Linux machine
  .orglens-grammar.yml   # grammar: deck, operator, pack, agent as artifact types
  CONVENTIONS.md         # what a deck is — the anatomy to copy when adding one
  configs/               # ecosystem-wide (not per-deck)
    scad/                *.yml project configs
    orglens/             config.yaml
    claude/              CLAUDE__global.md  settings.json
  decks/
    method/              # the general cross-domain deck
      DECK.md
      operators/         inception/  verification/  communication/
      packs/             bias/  voice/
      skills/            /inception, /remember, ...
      agents/            harness-format named agents
    <domain deck>/       # private ones live in orglens-extras, not here
      DECK.md
    <next deck>/         # the bank grows here
```

Canonical prompts live here once; `bootstrap` symlinks each deck's cards out to harness locations (`~/.claude/`, `~/.scad/`, `~/.config/orglens/`, later `~/.pi/agent/`) so editing in-repo is live everywhere.

## Install

One command, cross-platform (macOS + Linux) — installs the public tools and symlinks this config:

```bash
./bootstrap        # or: chezmoi init --apply <this repo>
```

## Status

Scaffold. Structure defined; **decks and operators harvested as they prove themselves on real problems — not designed up front.** The first domain deck was built before the pattern was named, and moved to `orglens-extras` when this repo went public — the anatomy it demonstrated is what stayed.

## Private decks

Decks about work that cannot be published live in a second repo, `orglens-extras`, with the same `capabilities/decks/` shape. Which repo a deck sits in *is* the public/private line — there is no list here, no flag in the engine, and nothing for orglens to read: the engine has no reference to `capabilities/` at all.

Installing a second deck repo needs no extra machinery, because skills install by walking a repo:

```bash
cd ../orglens-extras && npx skills add . -g -a '*' -y --full-depth
```

Same command, different repo. Whether you run it is the whole of the choice.
