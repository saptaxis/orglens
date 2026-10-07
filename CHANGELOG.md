# Changelog

## [Unreleased]

### Sessions

- `sessions`, `resume` and `status` say when scad's index is more than an
  hour old, or was never built, from `scad index status` (scad 0.9.0). An
  older scad is no warning.
- scad's notes are memos (scad 0.9.0): `orglens notes` is now `orglens memos`,
  with no alias, and reads `scad memos ls`. When scad refuses, as it does
  until a machine's memo store is moved, its message is shown instead of an
  empty list.
- `resume UNIT NAME` resumes the unit's session of that name; TAB after the
  unit offers its attributed sessions' names, newest first.
- `resume UNIT` takes the unit's newest session, a running or just-launched
  one first (scad attaches to its pane), whatever its outcome, and names the
  others in one line.
- `start --split` lands the session in a pane beside this one.

### Status lines

- A status is its first sentence as plain text: org and markdown markup
  (code marks, emphasis, links) is dropped, and the line is no longer cut at
  the first comma or a trailing parenthesis, nor ever inside brackets.
  Shown so in `list`, `tree`, `view` and TAB hints.

### check

- A unit inside an ancestor of its stated parent is not misplaced.

### list

- Grouped by organisation: a block per top of the tree, units in it by the
  kind of their branch as `tree` groups them, flat and newest first, each
  with its path. Units alone at the top are grouped by kind as before.

### view

- Two tabs: *Recent* and *Explore*.
- Recent: every unit is its own card at any depth, banded by its own time,
  with its path; a name in the path scopes the page. Fixes 0.6.0 drawing
  every unit inside its organisation's card.
- Units are placed by session or by edit, toggled on the page; each card
  shows both times.
- Placed by session, a unit never worked on with an agent goes to a folded
  *no sessions* band rather than being placed by its edits.
- A *last week* band (7 to 14 days); bands through last week start open.
- Explore: the cards nested as `orglens tree` nests them, siblings by recency.
- A scope filter: every unit with units under it.
- `file://` links are percent-encoded.
- `view` runs scad's incremental reindex first (about a second), so running
  sessions show their turns; `--no-reindex` skips it.

## [0.6.0] — 2026-10-02

### Finding units

- Markers are found at any depth; roots are best listed one per repository.
- `skip:` in config: folders no walk enters (default: `node_modules`,
  `__pycache__`, `*.egg-info`, `site-packages`, `venv`, `env`, `build`, `dist`,
  `target`, `site`). No walk follows a link to a directory.
- `check` and `where` report a home that resolves nowhere.
- Paths are shown from the root's name (`traitful-chat/docs`).

### The unit tree

- `part_of` builds a tree of units; no kind is special.
- `orglens tree [UNIT]`: the tree with lines, units grouped by kind, each with
  its status. `--json` for data.
- `--under UNIT` on `list`, `status` and `find`; `snapshot --unit` takes the
  whole subtree.
- `view` draws every level and keeps units in a `part_of` cycle.
- `check` reports a `part_of` naming no unit, a cycle, a folder disagreeing
  with its marker, and an undeclared folder inside another unit's home.
- A session belongs to the deepest home containing it. Container sessions are
  matched by `/workspace/<home name>`.

### Declaring and creating units

- `new` and `declare` ask before writing a parent (`Part of X? [y/N]`), and
  never write one unasked. `declare` gains `--part-of`.
- A kind can be declared under `structure:` alone, found by its markers.
- `new` seeds every file the kind's `structure:` declares.

### Fixes

- `orglens config` renders a repository's root as its path, not a home inside
  it, which scad's clone refused.
- A unit's status comes from its driver in any home before other documents.
- `orglens start <TAB>` completes unit names.

### Not yet

- Status lines are shown with their org markup, and cut at the first comma
  even inside brackets.
- `list` does not group by organisation.
- `resume UNIT` can pick a running session or skip a just-launched one;
  fixing one by the obvious rule breaks the other, so the rule is not decided.

## [0.5.0] — 2026-09-28

orglens reads org beside markdown, mixed in one tree, and markdown stays
supported. A grammar says which format `new` writes; everything else reads both.
Measured on a 769-document tree converted from markdown to org: the same units,
the same documents per kind and a status wherever there was one, before and
after.

### Formats

- A format registry, `orglens/formats/`: one module per format (its suffix, how
  to read the status line, the driver `new` writes), and every glob and status
  read in the engine goes through it. A contract test runs once per format.
- The grammar declares `format: md` or `format: org`, and it decides only what
  `new` writes. Absent, it is `md`, so an existing grammar behaves as before.
- Patterns and the driver name no extension: `driver: overview`, `plans/*`.
  `*` matches `.md` and `.org` files and never an image, a `.nav.yml` or a
  `session.jsonl`. A grammar that still writes `plans/*.md` reads both formats
  the same way; a pattern ending in an extension no format registers
  (`*.txt`) is left as written.
- In org the status line is a `#+STATUS:` keyword; in markdown it is still
  `> **Status:**`.
- `new` writes the driver in the grammar's format: `#+TITLE:` and `#+STATUS:`
  in org.

### check

- A document written in both formats side by side (`overview.md` beside
  `overview.org`) is reported; the grammar's format is the one read.
- A declared document counts as present in either format, and one that is
  missing is named as `new` would write it.
- Folders of undescribed documents count org files too.

### view, completion, workflows

- `view_link: file` in config links the view's documents to the files, for a
  tree read in an editor. The default is unchanged: the served site at
  `docs_base_url`.
- `.org` documents get the same served URL as markdown ones.
- Completion reads `snapshot.json`, written beside the markdown snapshot,
  rather than parsing the snapshot's headings. `snapshot --check` reports it
  stale when it lags.
- Completion and the workflow engine honour `ORGLENS_CONFIG`, as the CLI did.
  Before, they always read `~/.orglens/config.yaml`.
- A workflow node's `writes:` may name a stem (`writes: draft`): the file that
  exists in either format, else a new one in the grammar's format. A name with
  a suffix is used as written.

### The skills

- The operator card and the generated vocabulary reference say which format
  to write and what the org status line is; `orglens-adapt` gives the driver's
  shape in org. Re-run `bootstrap` to pick them up.

### Not yet

- A name the grammar writes with a suffix (`driver: overview.md`) is tried
  before the grammar's format, so under `format: org` a pair is read from the
  markdown one while `check` says the org one is read.
- Completion shows a status's org markup as it is written.
- `new` still offers to add the unit to a parent `.nav.yml`, a MkDocs habit.
- `view_link` has `served` and `file`; a GitHub link and a URL template are
  not built.

## [0.4.0] — 2026-09-27

Everything a session or a note needs is reachable from orglens: a turn into an
open pane, a name for the window it runs in, a decision per directory over the
unclaimed pile, and the notes a unit actually owns.

### Notes

- Notes are joined to units by **the session that wrote them** — attribution,
  else containment, the rule `sessions` already decides — rather than by the
  unit's name appearing in the note. The old name match survives as a weaker,
  labelled reason: every row says `written here`, `filed here` or
  `mentions this`, and `view` prints it. One read of `scad notes ls` for the
  whole tree replaces one `--about` subprocess per unit: **0.25s against
  8.47s on a 31-unit tree**. Measured on that tree: 42 exact links, 13 filed,
  62 mentions, and none the name match had missed — the correctness this
  fixes had not yet gone wrong, and the join no longer depends on tagging.
- `orglens notes [UNIT]`, with `--no-mentions` for the exact rows only.

### The unclaimed pile

- `sessions --triage` decides the unclaimed sessions **by directory**, one
  answer per group: 201 unclaimed on 2026-09-25 and six directories held ~95
  of them. `e` takes a group one session at a time, `--one-by-one` skips the
  grouping, `--groups` just counts. Nothing proposes a unit: a session at a
  shared root could be any of the units under it.
- `dismiss SESSION` records that a session belongs to no unit and never will,
  so the pile can empty; a later `attribute` takes it back. `dismiss --under
  PATH` clears a tree, the unclaimed part of it only. `sessions --dismissed`
  lists them, so a mistaken dismissal is visible.
- `attribute` and `dismiss` take `--why`, and it is shown wherever the session
  is listed, outranking the last turn.
- `sessions --none --json` emits rows with an empty `unit` and `why` to fill
  in; `sessions --from FILE` applies them.
- The view's unattributed rows carry the commands that act on them: resume,
  `attribute` (unfinished, ending in a space — no unit is proposed), `dismiss`,
  and `dismiss --under` for the row's directory.

### Sessions

- `resume --prompt TEXT` sends a turn to an open session through `scad session
  send` instead of attaching.
- `resume` names the other live processes on a session id before opening it,
  and `check` reports every doubly held session: two writers on one transcript
  is how a session forks. Five were doubly held when this landed.
- `start --window` lands the session as a window in the tmux you are already
  in, and the session is named `unit[-context]-sepDD` — the shape these names
  already had by hand, where the day anchors and `--about WORDS` distinguishes
  two sessions on one unit on one day. A name already in the index gets a
  `-2`. `--name TEXT` overrides, `--no-name` suppresses, `--dry-run` says what
  both would be. Both flags need scad's `session launch --window/--name`.

### The skill, and installing

- The operator card (`skills/orglens/SKILL.md`) learns the new verbs: `notes`,
  `--why`, `resume --prompt`, `start --window` and `--about`, `snapshot --json`,
  and that clearing the unclaimed pile is the person's to run, not an agent's.
  Re-run `bootstrap` to pick it up; the installed copy is a file, not a link.
- `bootstrap --uninstall` removes the completion script it wrote. The line
  sourcing it from a shell rc is the person's own and is left alone.

### Snapshot and completion

- `snapshot --json` emits the same facts as data, narrowed by the same
  `--type`/`--unit` selection as the document.
- Shell completion for unit names (with each one's status as the hint),
  document kinds, session ids, workflow nodes and packet paths, written by
  `bootstrap`. The completers read a cache, never the tree, so a tab is not a
  two-second pause; node names survive a workflow that does not validate.

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
