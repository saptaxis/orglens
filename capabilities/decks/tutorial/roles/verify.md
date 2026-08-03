# Role: verify

Check the fix against the reproduction. Nothing else.

Read `repro.md` for the steps and `fix.md` for what changed. Run the steps.

Write `verdict.md` with one of two outcomes, stated in the first line:

- **PASSES** — the steps no longer produce the observed behaviour.
- **FAILS** — they still do, or they now produce something else. Say which.

If it FAILS, the loop returns to `reproduce` and your verdict is that pass's
input. Write it so the next reproduction is better than the last one.

If it PASSES, the loop still returns to `reproduce` — the engine does not know
what your prose says. Ending the loop is a human act:

    touch <packet>/CLOSED

`exists:CLOSED` is the workflow's only terminal condition.

**You should not be the same session that wrote `fix.md`.** A session checking
its own work reads its own reasoning as obvious and misses what it assumed.
Nothing enforces this — it is on whoever dispatches the pass to hand it to a
fresh session.

When done:

    orglens workflow record <packet> --workflow <deck>/WORKFLOW.yaml \
        --deck <deck> --node verify
