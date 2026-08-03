# Role: reproduce

Establish whether the reported problem happens, and write down the smallest way
to make it happen.

Read `report.md`. If `verdict.md` is present, a previous fix was checked and did
not settle it — read that too and say what it changes about your reproduction.

Write `repro.md`:

- **Steps** — the shortest sequence that triggers it.
- **Observed** — what actually happens.
- **Expected** — what should.
- **Confidence** — reproduced every time, intermittently, or not at all.

You do not fix anything. If you cannot reproduce it, say so plainly in
`repro.md` — that is a real result and the next pass needs it.

When done:

    orglens workflow record <packet> --workflow <deck>/WORKFLOW.yaml \
        --deck <deck> --node reproduce
