# Tutorial deck — a three-node workflow you can run in five minutes

This deck exists to be run, not read. It is a bug-triage workflow — *reproduce,
fix, verify* — chosen because it is obviously **not** about writing. The engine
that runs it is the same engine that runs a writing deck, and it knows nothing
about bugs, articles, or anything else. `reproduce`, `report.md`, `verdict.md`
are strings this deck invents.

By the end you will have used every mechanic the engine has: `next`, `done`, a
gate, `note`, and `goto`.

## Set up

```bash
# Run this from the root of your orglens clone. $WF must be absolute,
# because the next step moves you elsewhere.
export WF="$PWD/capabilities/decks/tutorial/WORKFLOW.yaml"

mkdir -p ~/vsr-tmp/triage/bug-417 && cd ~/vsr-tmp/triage
export PKT=$PWD/bug-417
echo 'Login fails with a space in the password.' > $PKT/report.md
```

A **packet** is just that directory. There is no database and no registry.

## 1. What runs next?

```bash
$ orglens workflow next $PKT --deck $WF
node: reproduce
program: .../tutorial/programs/reproduce.md
write: .../bug-417/repro.md
```

The packet has no session yet, so the first node runs. `--deck` bound the
packet to this deck; you will not pass it again. The program is the instructions
for the pass; `write` is the one file the pass produces.

## 2. Do the pass, then say so

The engine runs nothing. You, or an agent handed the program, do the work.

```bash
$ cat > $PKT/repro.md <<'EOF'
Steps: log in with "a b".
Observed: 500.
Expected: success.
Confidence: every time.
EOF

$ orglens workflow done $PKT --node reproduce --agent you
done: reproduce

$ orglens workflow next $PKT
node: fix
program: .../tutorial/programs/fix.md
write: .../bug-417/fix.md
```

`done` is the only thing that moves the workflow forward. It refuses a node the
workflow is not on: try `--node verify` here and it says so.

## 3. A gate

`fix` carries `review: true`.

```bash
$ cat > $PKT/fix.md <<'EOF'
Change: stop trimming the password field.
Why: the trim was cosmetic.
Risk: none known.
EOF

$ orglens workflow done $PKT --node fix --agent you
done: fix

$ orglens workflow next $PKT
waiting on: review before verify            (after node fix)
```

Nothing runs until a human answers. The answer is a note, and it is the only
channel from you to the next pass:

```bash
$ orglens workflow note $PKT "agreed, ship it"
noted; next: verify

$ orglens workflow next $PKT
node: verify
program: .../tutorial/programs/verify.md
write: .../bug-417/verdict.md
note:  "agreed, ship it"
```

A pass can also raise a gate of its own: `done --question "..."` waits the same
way, with your question printed instead of `review before`.

## 4. The end of the list

```bash
$ echo 'FAILS: still 500 on a trailing space.' > $PKT/verdict.md
$ orglens workflow done $PKT --node verify --agent someone-else
done: verify

$ orglens workflow next $PKT
complete
```

`verify` is the last node, so the workflow is complete. The engine did not read
`verdict.md`; it does not know the fix failed.

## 5. Round again is a human act

```bash
$ orglens workflow goto $PKT --node reproduce --why "verdict FAILS on a trailing space"
next: reproduce

$ orglens workflow next $PKT
node: reproduce
program: .../tutorial/programs/reproduce.md
write: .../bug-417/repro.md
note:  "verdict FAILS on a trailing space"
```

`goto` names the node to run next. Forward, backward, the same node again:
any node, any time. It appends a fact with your reason rather than setting a
field, so six months later the packet says who moved what and why. It also
clears an open gate, because a human moving the workflow is the human acting.

## What you just used

| mechanic | where |
|---|---|
| `next` derives the position from the session file | every step |
| `done` moves the workflow, and refuses the wrong node | §2 |
| `review: true` on a node opens a gate | §3 |
| `note` answers it, and reaches the next program | §3 |
| the end of the list is the end | §4 |
| `goto` moves the workflow by hand | §5 |

Everything the engine knows is in `$PKT/session.jsonl`, one fact per line,
never rewritten. Delete it and you are back at `reproduce`; git is the backup.

## Try changing it

- Add `review: true` to `verify` and run the workflow again: it waits before
  `complete` now, and a `note` finishes it.
- Rename every node and file to something from your own domain. Nothing in
  `orglens/workflow/` needs to change, because nothing in it knows these words.
