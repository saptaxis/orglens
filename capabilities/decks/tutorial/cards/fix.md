# Card: fix

Make the smallest change that addresses what `repro.md` establishes.

Read `report.md` for what was asked and `repro.md` for what is actually true.
Where they disagree, `repro.md` wins — it was measured.

Write `fix.md`:

- **Change** — what you altered, concretely.
- **Why this and not more** — the smallest-change argument.
- **Risk** — what this could break.

**This pass ends at a gate.** The stage carries `review: true`, so finishing it
stops the chain until someone answers:

    orglens chain note <packet> "..."

That is deliberate. A fix nobody agreed to is not a fix.

When done:

    orglens chain done <packet> --stage fix --agent <you>
