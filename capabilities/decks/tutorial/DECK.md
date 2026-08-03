# Tutorial deck — a three-node loop you can run in five minutes

This deck exists to be run, not read. It is a bug-triage loop — *reproduce, fix,
verify, round again* — chosen because it is obviously **not** about writing. The
engine that runs it is the same engine that runs the writing deck, and it knows
nothing about bugs, articles, or anything else. `reproduce`, `report.md`,
`CLOSED` are strings this deck invents.

By the end you will have used every mechanic the system has: the cursor, a gate,
a loop-back edge, a terminal condition, and moving the cursor by hand.

## Set up

```bash
export DECK=~/Dropbox/code/orglens/capabilities/decks/tutorial
export WF=$DECK/WORKFLOW.yaml

mkdir -p /tmp/triage/bug-417 && cd /tmp/triage
git init -q . && export PKT=/tmp/triage/bug-417
echo 'Login fails with a space in the password.' > $PKT/report.md
git add -A && git commit -qm "bug 417 reported"
```

A **packet** is just that directory. There is no database and no registry.

## 1. Where am I?

```bash
$ orglens workflow derive $PKT --workflow $WF
runnable: reproduce
  reproduce: guard matched
```

The log is empty, so the cursor is nothing, and `reproduce` is the only node
whose guard accepts that. Nothing was configured — the answer comes from the
directory and an absent log.

## 2. What exactly does that pass get?

```bash
$ orglens workflow job $PKT --workflow $WF --deck $DECK
node:   reproduce
role:   .../tutorial/roles/reproduce.md
read:   report.md  -> /tmp/triage/bug-417/report.md
read:   verdict.md (no match)
write:  /tmp/triage/bug-417/repro.md
```

Note `verdict.md (no match)`. `reproduce` declares it because on later rounds a
verdict exists — on the first round it does not, and that is reported rather
than treated as an error. **You see what a pass is being handed before it runs.**

## 3. Do the pass, then record it

The engine does not run anything. You (or an agent given `role`) do the work.

```bash
$ cat > $PKT/repro.md <<'EOF'
Steps: log in with "a b".
Observed: 500.
Expected: success.
Confidence: every time.
EOF

$ orglens workflow record $PKT --workflow $WF --deck $DECK --node reproduce
recorded reproduce

$ orglens workflow derive $PKT --workflow $WF
runnable: fix
  fix: guard matched
```

Recording moved the cursor. That is the only thing that moves it.

## 4. A gate

`fix` declares `human_review: true`.

```bash
$ cat > $PKT/fix.md <<'EOF'
Change: stop trimming the password field.
Why: the trim was cosmetic.
Risk: none known.
EOF

$ orglens workflow record $PKT --workflow $WF --deck $DECK --node fix
recorded fix
raised the declared review gate

$ orglens workflow derive $PKT --workflow $WF
runnable: verify
  verify: guard matched
  blocked on fix: fix is declared for human review before the next node runs
```

It tells you the next node *and* that you are blocked. Clear it with a reason:

```bash
$ orglens workflow resolve $PKT --note "agreed, ship it"
resolved f7b4f8226911
```

> **Watch out:** `derive` prints `blocked` but its exit code is still `0`. Fine
> when you are reading it; a trap if you script `derive && do_next`. Use
> `orglens workflow run` for automation — it checks blocking first.

## 5. The loop closes

```bash
$ echo 'FAILS — still 500 on a trailing space.' > $PKT/verdict.md
$ orglens workflow record $PKT --workflow $WF --deck $DECK --node verify
recorded verify

$ orglens workflow derive $PKT --workflow $WF
runnable: reproduce
  reproduce: guard matched
```

**Back to `reproduce`, in the same directory, with nothing cleared.** That is the
loop-back edge — `reproduce`'s guard is `any: ["after:nothing", "after:verify"]`,
so it is both the entry point and the return point. A second round is the same
pipeline over current data; `verdict.md` now exists, so this time it matches.

## 6. Ending it is a human act

The engine cannot read `verdict.md` and does not know your fix worked. Only one
thing ends the loop:

```bash
$ touch $PKT/CLOSED
$ orglens workflow derive $PKT --workflow $WF
terminal: -
  terminal: closed (exists:CLOSED=True)
```

## 7. Moving the cursor by hand

Suppose a report arrives with a reproduction already attached. Skip the node:

```bash
$ orglens workflow goto $PKT --workflow $WF --node reproduce \
      --note "reporter attached a clean repro"
cursor moved to reproduce: reporter attached a clean repro
```

Forward, backward, redo a stage — any node, any time. It appends a fact with
your reason rather than setting a field, so six months later the packet says
*who skipped what and why*. You cannot move silently, and that is the only
restriction.

## What you just used

| mechanic | where |
|---|---|
| the cursor is the run log | §1, §3 |
| `exists:<glob>` over the directory | §6 terminal, §2 `(no match)` |
| `after:<node>` over the cursor | every guard |
| entry and loop-back in one guard | §5 |
| a human gate | §4 |
| moving the cursor by hand | §7 |

## Try changing it

The fastest way to understand the engine is to break this deck.

- Give `verify` the guard `all: ["after:reproduce"]` and run
  `orglens workflow check` — two nodes now claim the same cursor, and it says so
  without running anything. Ambiguity is decidable here because exactly one
  `after:` is ever true.
- Delete `runs.jsonl` **and `CLOSED`**, then derive — you are back at
  `reproduce`. The log *is* the position; git is the backup, `goto` is the
  repair. (Leave `CLOSED` in place and you get `terminal` instead: terminal
  conditions are checked before any guard, so a closed packet stays closed no
  matter what the cursor says.)
- Rename every node and file to something from your own domain. Nothing in
  `orglens/workflow/` needs to change, because nothing in it knows these words.
