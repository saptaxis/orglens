# Card: verify

Check the fix against the reproduction. Nothing else.

Read `repro.md` for the steps and `fix.md` for what changed. Run the steps.

Write `verdict.md` with one of two outcomes, stated in the first line:

- **PASSES** — the steps no longer produce the observed behaviour.
- **FAILS** — they still do, or they now produce something else. Say which.

`verify` is the last stage, so after it the chain reports `complete` whatever
your verdict says — the engine does not read prose. Going round again is a
human act:

    orglens chain goto <packet> --stage reproduce --why "FAILS: ..."

Your verdict is that next reproduction's input. Write it so the next round is
better than the last one.

**You should not be the same session that wrote `fix.md`.** A session checking
its own work reads its own reasoning as obvious and misses what it assumed.
Nothing enforces this — it is on whoever dispatches the pass to hand it to a
fresh session.

When done:

    orglens chain done <packet> --stage verify --agent <you>
