# Tutorial deck — a three-stage chain you can run in five minutes

This deck exists to be run, not read. It is a bug-triage chain — *reproduce,
fix, verify* — chosen because it is obviously **not** about writing. The engine
that runs it is the same engine that runs a writing deck, and it knows nothing
about bugs, articles, or anything else. `reproduce`, `report.md`, `verdict.md`
are strings this deck invents.

By the end you will have used every mechanic the engine has: `next`, `done`, a
gate, `note`, and `goto`.

## Set up

```bash
# Run this from the root of your orglens clone. $CHAIN must be absolute,
# because the next step moves you elsewhere.
export CHAIN="$PWD/capabilities/decks/tutorial/CHAIN.yaml"

mkdir -p ~/vsr-tmp/triage/bug-417 && cd ~/vsr-tmp/triage
export PKT=$PWD/bug-417
echo 'Login fails with a space in the password.' > $PKT/report.md
```

A **packet** is just that directory. There is no database and no registry.

## 1. What runs next?

```bash
$ orglens chain next $PKT --deck $CHAIN
stage: reproduce
card:  .../tutorial/cards/reproduce.md
write: .../bug-417/repro.md
```

The packet has no session yet, so the first stage runs. `--deck` bound the
packet to this deck; you will not pass it again. The card is the instructions
for the pass; `write` is the one file the pass produces.

## 2. Do the pass, then say so

The engine runs nothing. You, or an agent handed the card, do the work.

```bash
$ cat > $PKT/repro.md <<'EOF'
Steps: log in with "a b".
Observed: 500.
Expected: success.
Confidence: every time.
EOF

$ orglens chain done $PKT --stage reproduce --agent you
done: reproduce

$ orglens chain next $PKT
stage: fix
card:  .../tutorial/cards/fix.md
write: .../bug-417/fix.md
```

`done` is the only thing that moves the chain forward. It refuses a stage the
chain is not on: try `--stage verify` here and it says so.

## 3. A gate

`fix` carries `review: true`.

```bash
$ cat > $PKT/fix.md <<'EOF'
Change: stop trimming the password field.
Why: the trim was cosmetic.
Risk: none known.
EOF

$ orglens chain done $PKT --stage fix --agent you
done: fix

$ orglens chain next $PKT
waiting on: review before verify            (after stage fix)
```

Nothing runs until a human answers. The answer is a note, and it is the only
channel from you to the next pass:

```bash
$ orglens chain note $PKT "agreed, ship it"
noted; next: verify

$ orglens chain next $PKT
stage: verify
card:  .../tutorial/cards/verify.md
write: .../bug-417/verdict.md
note:  "agreed, ship it"
```

A pass can also raise a gate of its own: `done --question "..."` waits the same
way, with your question printed instead of `review before`.

## 4. The end of the list

```bash
$ echo 'FAILS: still 500 on a trailing space.' > $PKT/verdict.md
$ orglens chain done $PKT --stage verify --agent someone-else
done: verify

$ orglens chain next $PKT
complete
```

`verify` is the last stage, so the chain is complete. The engine did not read
`verdict.md`; it does not know the fix failed.

## 5. Round again is a human act

```bash
$ orglens chain goto $PKT --stage reproduce --why "verdict FAILS on a trailing space"
next: reproduce

$ orglens chain next $PKT
stage: reproduce
card:  .../tutorial/cards/reproduce.md
write: .../bug-417/repro.md
note:  "verdict FAILS on a trailing space"
```

`goto` names the stage to run next. Forward, backward, the same stage again:
any stage, any time. It appends a fact with your reason rather than setting a
field, so six months later the packet says who moved what and why. It also
clears an open gate, because a human moving the chain is the human acting.

## What you just used

| mechanic | where |
|---|---|
| `next` derives the position from the session file | every step |
| `done` moves the chain, and refuses the wrong stage | §2 |
| `review: true` on a stage opens a gate | §3 |
| `note` answers it, and reaches the next card | §3 |
| the end of the list is the end | §4 |
| `goto` moves the chain by hand | §5 |

Everything the engine knows is in `$PKT/session.jsonl`, one fact per line,
never rewritten. Delete it and you are back at `reproduce`; git is the backup.

## Try changing it

- Add `review: true` to `verify` and run the chain again: it waits before
  `complete` now, and a `note` finishes it.
- Rename every stage and file to something from your own domain. Nothing in
  `orglens/chain/` needs to change, because nothing in it knows these words.
