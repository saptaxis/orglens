# Role: fix

Make the smallest change that addresses what `repro.md` establishes.

Read `report.md` for what was asked and `repro.md` for what is actually true.
Where they disagree, `repro.md` wins — it was measured.

Write `fix.md`:

- **Change** — what you altered, concretely.
- **Why this and not more** — the smallest-change argument.
- **Risk** — what this could break.

**This pass ends at a gate.** The declaration carries `human_review: true`, so
recording it raises a question and the loop stops until someone answers:

    orglens workflow resolve <packet> --note "..."

That is deliberate. A fix nobody agreed to is not a fix.

When done:

    orglens workflow record <packet> --workflow <deck>/WORKFLOW.yaml \
        --deck <deck> --node fix
