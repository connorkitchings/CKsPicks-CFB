# Session: JP+ site review and adoption contract

## TL;DR

- **Worked On:** Review of jpplusratings.com (design, functionality, content) against Stratum Production on Week 12; decision on which ideas to adopt.
- **Outcome:** Decision record written; one approved implementation contract written for the adopted display-only features. Documentation only.
- **Plan Contract:** [`docs/plans/2026-11-17/jpplus-review-adoptions.md`](../../docs/plans/2026-11-17/jpplus-review-adoptions.md)
- **Approval / Status:** Owner approval in this session; contract Approved, then deferred by the owner until after the offseason model and methods work. Not implemented.
- **Commit policy:** Commit on local `dev`; no push. Commits `dee21f98` (record and contract) and `89f55c68` (deferral).
- **Blockers:** None
- **Next:** None until the offseason model and methods work is done; then implement the contract (revisit tasks B and D first).

**tags:** ["planning", "web", "review"]

## Context and Decisions

- Decision record: [JP+ site review](../../docs/decisions/2026-11-17-jpplus-site-review.md). Adopt weekly movers, projected score, record by difference band, and two method-page sections; rating scale deferred to the methods discussion.
- Owner later deferred implementation: projected score and the method sections depend on the final totals behavior and rating scale.
- Storage not needed; branch `dev` at `1036c7e1`.

## Work Completed

- Wrote the decision record and the contract; linked them from the decision log, `mkdocs.yml` and `docs/plans/index.md`.

## Files Modified

- `docs/decisions/2026-11-17-jpplus-site-review.md` — review table and owner decisions
- `docs/plans/2026-11-17/jpplus-review-adoptions.md` — approved implementation contract
- `docs/decisions/decision_log.md`, `docs/plans/index.md`, `mkdocs.yml` — links

## Validation

- [x] `uv run mkdocs build --strict` (passes; existing INFO anchor notices only)
- [x] Contract saved under `docs/plans/2026-11-17/` with lifecycle metadata
- [x] `git status` clean after commit; `docs/status.md` unchanged (no week or release state change)
- [x] `git diff --check`

## Amendments and Blockers

- None

## Handoff Notes

- **Resume at:** After the offseason model and methods work; owner deferred implementation on 2026-11-17
- **Watch out for:** Mobile density and layout invariants in `mobile-slate.spec.ts` and `mobile-matchup.spec.ts`; betting-policy wording.

## Terra Handoff Prompt (use only after the deferral lifts)

> Implement the approved contract `docs/plans/2026-11-17/jpplus-review-adoptions.md` on a new worktree branched from local `dev`. Read `AGENTS.md` and `docs/status.md` first. Revisit tasks B and D against the final model first. Work through tasks A to D in order, commit each locally, add the 2.0.0 `CHANGELOG.md` entries, and run `make check`, `make web-e2e` and the visual checks listed in the contract. Do not change version files, the share card, or anything out of scope. Do not push or deploy.
