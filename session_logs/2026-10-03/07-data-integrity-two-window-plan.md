# Session: Data-integrity two-window implementation contract

## TL;DR

- **Worked On:** Converted the completed data-integrity investigation and user decisions into a durable implementation contract.
- **Outcome:** [04-data-integrity-two-window-implementation.md](../../docs/plans/2026-10-03/04-data-integrity-two-window-implementation.md) is Approved. Window 1 is independently releasable; Window 2 is held behind full-R1 scoring-attribution certification.
- **Plan Contract:** `docs/plans/2026-10-03/04-data-integrity-two-window-implementation.md`
- **Approval / Status:** User resolved the decision packet and requested documentation first on 2026-10-03. Approved; implementation has not started.
- **Blockers:** Window 2 needs independent attribution evidence beyond quarter totals. This is an intentional release gate.
- **Next:** Start a fresh Terra task with the prompt below after the plan commit is reviewed.

## Context and Decisions

- Full R1 is the candidate, but no V1 fallback, partial release, or neutral-only release is authorized if certification fails.
- Never impute missing EPA. Withhold affected EPA with provenance while retaining valid PPP.
- Existing canonical spread/total fields remain; corrected snapshots use new versioned identities and separately retain selected points.
- Exact ties are away/under. Corrected public history is reconstructed retrospective; original frozen records remain audit evidence.
- Public Performance is accuracy-only. Stored financial values remain auditable with actual/default price provenance.

## Work Completed

- Saved the approved contract and aligned the decision packet, plan index, known-issues register, decision log, status page, operator/runbook wording, and dependent team-stat/matchup plans.
- Marked the original unified single-batch rollout as historical and superseded without deleting its investigation evidence.

## Files Modified

- `docs/plans/2026-10-03/04-data-integrity-two-window-implementation.md` — approved execution contract.
- `docs/plans/2026-10-03/01-unified-data-fix-and-matchup-rollout.md` — historical/superseded authority marker.
- `docs/plans/2026-10-03/02-week5-data-issue-investigation.md` and `03-data-decision-packet.md` — evidence and recorded decisions aligned to the contract.
- `docs/data/known_issues.md`, `docs/decisions/decision_log.md`, `docs/status.md`, `docs/plans/index.md`, and operations/dependent plans — current authority and release wording.

## Validation

- [x] `git diff --check`
- [x] `uv run mkdocs build --quiet`

## Amendments and Blockers

- None. Any change to R1 scope, EPA policy, replay cutoff, neutral refit, snapshot identity, or release atomicity is material and requires an amendment.

## Handoff Notes

**Resume at:** Review the documentation diff, then open a fresh Terra task only when implementation is desired.

**Copy-ready Terra prompt:**

```text
Use the repository-local implement-plan skill and implement the approved contract at:

docs/plans/2026-10-03/04-data-integrity-two-window-implementation.md

Treat it as authoritative. Preserve its architectural decisions, run its validation,
and stop for any material conflict. This request explicitly authorizes implementation.
```

**tags:** ["planning", "data-integrity", "v5", "operations"]
