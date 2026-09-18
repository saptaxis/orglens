# capabilities

A tree of **capabilities**, each a self-contained bundle of programs and skills for
one purpose.

| Tool | Owns |
|---|---|
| [`scad`](https://github.com/saptaxis/scoped-agent-dispatch) | where and how an agent runs, and what happened |
| [`orglens`](https://github.com/saptaxis/orglens) | what exists, how it is filed, what state it is in |
| `capabilities/` (here) | what you *do* with those — method, glued to the tools |

**The dependency arrow points one way: capabilities → the tools, never the reverse.**
The orglens engine has no reference to `capabilities/` at all, so a capability is
invoked *through* the tools and stays independently discardable.

This tree is **orglens-governed content** — the same relationship a documents
tree has with orglens. The engine reads this tree's grammar
(`.orglens-grammar.yml`) and content. A **grammar** describes an entire tree; a
**declaration** (`.orglens.yml`) describes one unit within it.

## The model: capability → program

- **Capability** — a self-contained bundle for one purpose: programs, skills,
  what they read, and a workflow if the programs run in order.
- **Program** — what one node of a workflow runs. One file, one pass, one
  file written, performed by whoever is at the packet.
- **Skill** — a `SKILL.md` a harness loads on its own triggers. A capability can be
  skills alone, with no workflow.

New capabilities accrete over time. A capability is just a directory — port one in or out
freely. See [`CONVENTIONS.md`](CONVENTIONS.md) for the anatomy.

The capabilities that carry personal method live in `orglens-extras` — see *Private
capabilities* below. What ships here is `tutorial`, and it is not a stand-in: it is
the check that the engine is generic.

## Layout

```
orglens/
  bootstrap                # install the tool, route every capability's skills
  capabilities/
    .orglens-grammar.yml   # grammar: capability as the unit; program, skill, reference as artifacts
    CONVENTIONS.md         # what a capability is — the anatomy to copy when adding one
    tutorial/              # a three-node workflow, run in five minutes
      README.md
      WORKFLOW.yaml
      programs/            reproduce / fix / verify
    <next capability>/     # the tree grows here
```

`tutorial` is the only capability this repo ships. It is a bug-triage workflow and shares no vocabulary with any writing capability, so it tests that the engine carries none of its own. The engine is `orglens workflow`: a workflow is an ordered list of nodes in `WORKFLOW.yaml`, each naming a program and the one file it writes; a packet is a directory; its `session.jsonl` is an append-only record of what finished, what was asked, and what was answered. Capabilities about work that cannot be published live in `orglens-extras`.

`bootstrap` routes each capability's skills out with `npx skills add`, which walks a repo and owns the harness path table — a wrong skills path fails silently, so the tool decides it rather than a list here. Skills install as **copies**, not symlinks, so re-run `bootstrap` after editing one.

## Install

From the repo root — installs orglens into its own venv and routes the skills it ships:

```bash
./bootstrap                                    # editable, for co-developing
./bootstrap --pinned                           # a clean machine
./bootstrap --extras ~/code/orglens-extras     # include the private capabilities
```

A repo without a `pyproject.toml` is a capability repo: its skills are routed and nothing is pip-installed. scad installs itself from its own repo — the dependency runs one way, and `bootstrap` says so rather than reaching across.

To undo it:

```bash
./bootstrap --uninstall                        # shows the plan, then asks
./bootstrap --uninstall --extras ~/code/orglens-extras
```

It prints what it would remove and confirms once before doing any of it. `~/.agents/skills` is shared between repos and the skills tool records only where a skill is *installed*, never which repo put it there — so the match is by name, and you get to look at the list first.

**It never deletes `~/.orglens/events/`.** An attribution exists because a person said so and cannot be recomputed, which makes it the one thing here that is not a cache. Removing it is a deliberate act, not a flag on an installer.

## Status

Structure defined; capabilities harvested as they prove themselves on real problems,
not designed up front. The first working capability was built before the pattern was
named and moved to `orglens-extras` when this repo went public.

## Private capabilities

Capabilities about work that cannot be published live in a second repo, `orglens-extras`, with the same `capabilities/` shape. Which repo a capability sits in *is* the public/private line — there is no list here, no flag in the engine, and nothing for orglens to read: the engine has no reference to `capabilities/` at all.

Installing a second capability repo needs no extra machinery, because skills install by walking a repo:

```bash
./bootstrap --extras ~/code/orglens-extras
```

which is the same `npx skills add . -g -a '*' -y --full-depth`, run once per repo.
