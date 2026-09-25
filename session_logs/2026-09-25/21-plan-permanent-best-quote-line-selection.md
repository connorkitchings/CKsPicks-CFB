# Session: Plan permanent best-quote line selection

## TL;DR

- **Worked On:** Investigated the permanent replacement of consensus/median market lines with the best stored executable quote after each model prediction.
- **Outcome:** Drafted a decision-complete implementation contract. No product, database, artifact, serving, or production changes were made.
- **Plan Contract:** `docs/plans/2026-09-25/03-permanent-best-quote-line-selection.md`
- **Approval / Status:** The user chose permanent all-season/all-week policy and requested planning only. Contract remains Draft pending approval of the exact path for implementation.
- **Blockers:** None for planning. Historical release work remains conditional on the planned quote-eligibility audit and separate production release decisions.
- **Next:** Review and approve or amend the Draft; then hand it to a fresh implementation task.

## Context and Decisions

- The canonical consensus/median snapshot will establish a model's side; the selected raw quote then maximizes the edge for that already-fixed side. This avoids a quote changing the model's direction while still choosing the most favorable executable point.
- The permanent policy applies wherever immutable eligible quotes are stored. A missing, mismatched, unpriced, or post-kickoff quote produces an unlined/ungraded target rather than a synthetic fallback.
- Current selected V5 Weeks 0–4 cannot be modified. They require replacement replay artifacts and the existing exact replay authorization path. V4 remains untouched.

## Work Completed

- Inspected frozen quote/snapshot persistence, existing selection and settlement helpers, prediction/grade schema, publish/score transactions, V5 replay authorization boundary, web serving fallback, and weekly operating documentation.
- Documented an append-only target-level `prediction_market_selections` design, exact grade quote linkage, all-year coverage audit, future pre-freeze selection, historical replacement releases, and validation gates.

## Files Modified

- `docs/plans/2026-09-25/03-permanent-best-quote-line-selection.md` — Draft implementation contract only.
- `session_logs/2026-09-25/21-plan-permanent-best-quote-line-selection.md` — this planning record.

## Validation

- [x] `uv run mkdocs build --strict --quiet`
- [x] `git diff --check`

## Amendments and Blockers

None.

## Handoff Notes

- **Resume at:** Review the Draft's fixed-side selection rule and historical replacement procedure; upon approval, update the contract approval source and use the repository-local `implement-plan` skill in a fresh task.
- **Watch out for:** No existing frozen/scored run or grade can be rewritten. Quote eligibility must be derived from immutable game, target, snapshot, quote, and kickoff identity.

## Approved-Plan Handoff

After approval, start a fresh implementation task with:

```text
Use the repository-local implement-plan skill and implement the approved contract at:

docs/plans/2026-09-25/03-permanent-best-quote-line-selection.md

Treat it as authoritative. Preserve its architectural decisions, run its validation,
and stop for any material conflict. This request explicitly authorizes implementation.
```

**tags:** ["planning", "market-lines", "quote-selection", "v5", "schema", "operations"]
