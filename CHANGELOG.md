# Changelog

## Unreleased

A session belongs to a set of units: the one an attribution names, or every
unit with a home containing where it ran. `orglens/sessions.py` is the one
place that decides this; `list`, `status` and `view` read from it.

The workflow engine is replaced. `orglens workflow` runs a workflow as an ordered
list of nodes: `next` says which program to perform and which file it writes,
`done` records a finished node, `note` answers the open gate, `goto` points
the workflow at a node. A packet's `session.jsonl` is the only record; position
and gate are derived from its last routing fact. The guard-based engine
(guards, roles, reads, terminal predicates, `runs.jsonl`) is removed in commit
`76858fd`; the new package reuses its path, so recover the old one with
`git show 76858fd^:orglens/workflow/<file>` or a checkout of `76858fd^` into a
worktree. The tutorial is ported to `WORKFLOW.yaml`.

"Deck" is retired. A bundle of programs, skills and references is a
**capability**, and lives directly under `capabilities/<name>/` with a
`README.md` as its descriptor; `capabilities/decks/` and `DECK.md` are gone.
In the engine, what `--deck` named was always the `WORKFLOW.yaml`, so the flag
is `--workflow`, the session's binding fact is `{"type": "workflow", ...}`, and
the loader is `orglens.workflow.definition.load_workflow`. No packet had been
bound under the old names.

- Sessions and notes come from `scad session ls --json` and `scad notes ls
  --about`, never from scad's index file. The `sqlite3` dependency, the index
  path and the reading of Claude's process registry are gone; scad 0.5 or
  later is needed for the sessions face, and an older scad or none means no
  sessions. A session started by hand in a terminal is not listed until
  scad's next reindex.
- `orglens sessions [UNIT]` lists a unit's sessions, or every unit's grouped,
  with how each is the unit's. `--none` lists the sessions belonging to no unit.
- `orglens resume UNIT|SESSION-ID` hands a session, or a unit's newest open
  one, to `scad session resume`.
- `orglens attribute SESSION-ID UNIT` records an attribution after the fact.
- `view` shows how each recent session is the unit's, and ends with the
  unattributed sessions, each with its resume command.
- Session counts are main sessions only. Subagents and workflow agents used to
  be counted too, which is why a unit's number can be lower than before.
- A home reached through a symlinked root matches sessions that recorded
  either spelling of the path.
- A root listed inside another root is swept to its own depth, so a marker
  deeper than three directories below the outer root is found by listing its
  parent as a root.
- `orglens check` reports a home declared on more than one unit, and which of
  them `where` answers inside it.
- `status` runs in 5s and `view` in 4.4s on a 23-unit tree, from 12.4s and
  10.6s: git is asked once per repository instead of three times per home,
  a checkout's remote is read from `.git/config`, and each home is walked
  once for every document kind.
- A grammar `find` ending in `/` names directories, one artifact each; the
  default grammar gains `article: articles/*/`. A `find` may be a list when
  one kind lives in several containers.
- `orglens find` takes `--grep TEXT` (keeps documents whose text matches, with
  the lines), `--in DIR` (scopes to a directory the grammar has no name for),
  `--since 2w`, `--waiting` (packets with a gate open) and `--json`. An
  unknown unit is refused in one line.
- `orglens check` reports folders holding three or more documents that no
  kind's container and no entity's structure names.
- `orglens snapshot --check` says whether the written snapshot is older than
  any declaration or driver document, and exits 1 if it is.
- Everything orglens keeps on a machine is under `~/.orglens/`: `config.yaml`,
  `cache/snapshot.md`, `events/`. Move `~/.config/orglens/config.yaml` there;
  nothing reads the old path.

## [0.2.0] — 2026-09-10

`orglens start UNIT` picks one of the unit's homes, launches through scad, and
records the unit before the session's first turn. Unless `--prompt` is given,
that first turn names the unit, lists its homes, and points at where its status
is written.

Containment attributes a session when its working directory sits inside exactly
one home. Where it does not, the session stays unattributed.

- `orglens declare PATH` proposes a declaration from a directory's position,
  shows the reason for each guess, and asks before writing.
- `orglens config UNIT` renders a unit's homes into the `repos:` block a
  container launcher reads.
- `orglens new` takes `--home`, repeatable.
- Attribution events are stored in `~/.orglens/events/`, one file per session.
- The deck bank keeps `tutorial`. The other decks moved to a private repo.

## [0.1.0] — 2026-08-14

A unit of work declares itself in a `.orglens.yml` and names the places it
lives. Its documents, sessions and state are derived from those. A home is a
name that resolves to a path on the machine you are on.
