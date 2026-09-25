# Changelog

## [Unreleased]

Everything a session or a note needs is reachable from orglens: a turn into an
open pane, a name for the window it runs in, a loop over the unclaimed pile,
and the notes a unit actually owns.

- Notes are joined to units by the session that wrote them — the same rule
  `sessions` uses — rather than by the unit's name appearing in the note. The
  older name match survives as a weaker, labelled reason: each row says
  `written here`, `filed here` or `mentions this`, and `view` shows it. One
  read of `scad notes ls` for the whole tree replaces one `--about`
  subprocess per unit: 0.25s against 8.47s on a 31-unit tree.
- `orglens notes [UNIT]` prints what was written down about a unit, with
  `--no-mentions` for the exact rows only.
- `sessions --triage` decides the unclaimed sessions **by directory**, one
  answer per group: 201 unclaimed on 2026-09-25 and six directories held ~95
  of them. `e` takes a group one session at a time, `--one-by-one` skips the
  grouping entirely, and `--groups` just counts. `dismiss --under PATH` clears
  a whole tree, the unclaimed part of it only. Nothing proposes a unit: a
  session at a shared root could be any of the units under it.
- `--why` is shown wherever a session is listed, and outranks the last turn on
  an unclaimed row — it was written about the session, the turn merely
  happened in it. `sessions --dismissed` lists what someone said belongs to no
  unit, so a mistaken dismissal is visible rather than buried in the log.
- The view's unattributed rows carry the commands that act on them: resume,
  `attribute` (unfinished, ending in a space — no unit is proposed), `dismiss`,
  and `dismiss --under` for the row's directory.
- `snapshot --json` emits the same facts as data, narrowed by the same
  `--type`/`--unit` selection as the document.
- Completion reaches workflow nodes and packet paths. Node names survive a
  workflow that does not validate, since a half-written one is when you most
  need them.
- `dismiss SESSION` records that a session belongs to no unit and never will,
  so the pile can empty. A later `attribute` takes it back. `attribute` and
  `dismiss` both accept `--why`.
- `sessions --none --json` emits rows with an empty `unit` and `why` to fill
  in; `sessions --from FILE` applies them.
- `resume --prompt TEXT` sends a turn to the open session through
  `scad session send` instead of attaching. `resume` also names the other
  live processes on a session id before opening it, and `check` reports every
  doubly held session: two writers on one transcript is how a session forks.
- `start --window` lands the session as a window in the tmux you are already
  in, named for the unit, and `--name` (on by default) names the session
  itself at launch. Both need scad's `session launch --window/--name`.
- Shell completion for unit names, document kinds and session ids, written by
  `bootstrap`. The completers read the snapshot cache, never the tree, so a
  tab is not a two-second pause.

## [0.3.0] — 2026-09-18

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
- Session ids are shown as the shortest prefix that is unique across the
  list, at least eight characters. codex thread ids are UUIDv7, so two threads
  started in one minute share their first eight; they read as duplicates and
  `resume` could not tell them apart.
- Unattributed sessions, in `sessions --none` and at the end of `view`, show
  where they ran and the last thing said.
- `view` is banded by when a unit last moved — waiting, today, yesterday,
  this week, this month, earlier — with the clock that placed it first on
  the card: a live session, then a session, an edit, a commit to its own
  paths. Every card folds; a unit that is part of another is a card inside
  its parent's. Kind is a chip and a filter, not a section. The status line
  is shown as the person's last word with its age, marked stale when the
  tree moved more than a week after it; a unit talked about without an edit,
  or edited without a session, says so. Filters: band, kind, agent, text.
  The unattributed sessions fold at the end.
- Session counts are main sessions only. Subagents and workflow agents used to
  be counted too, which is why a unit's number can be lower than before.
- A home reached through a symlinked root matches sessions that recorded
  either spelling of the path.
- A root that is itself a repository, or declares itself, is a home
  candidate in its own right, so a checkout whose parent holds everything
  can be listed as a root on its own.
- A root listed inside another root is swept to its own depth, so a marker
  deeper than three directories below the outer root is found by listing its
  parent as a root.
- `orglens check` reports a home declared on more than one unit, and which of
  them `where` answers inside it.
- `status` runs in 3s and `view` in 3s on a 25-unit tree, from 12.4s and
  10.6s: git is asked once per repository instead of three times per home,
  a checkout's remote is read from `.git/config`, each home is walked once
  for every document kind, and everything that waits on a subprocess or a
  file walk — git per home and driver document, the newest mtime, the notes
  per unit — is fetched in one pool before the per-unit loop.
- A grammar `find` ending in `/` names directories, one artifact each; the
  default grammar gains `article: articles/*/`. A `find` may be a list when
  one kind lives in several containers.
- `orglens find` takes `--grep TEXT` (keeps documents whose text matches, with
  the lines), `--in DIR` (scopes to a directory the grammar has no name for),
  `--since 2w`, `--waiting` (packets with a gate open) and `--json`. An
  unknown unit is refused in one line.
- `orglens check` reports a status line older than the unit's newest edit
  by more than a week.
- `orglens check` reports folders holding three or more documents that no
  kind's container and no entity's structure names.
- `orglens new` writes a stub driver document and adds the unit to a parent
  `.nav.yml` that lists children by name, and prints the next steps. `start`
  says the session is running detached and how to get back to it; `--dry-run`
  says so too and shows the first turn. `snapshot` takes `--type` and
  `--unit`. `check` reports a unit its parent nav omits. From a first-time
  operator's account: ~8k tokens and one human round-trip to do new, overview
  and start, half of it recovering the fact that the launch is detached.
- The `orglens` skill is an operator card: every command an agent runs, once,
  with its one non-obvious fact, so the common path needs no `--help`.
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
