# Session: Full-Corpus Successor-v2 R1–R4 Planning

## TL;DR

- **Worked On:** Replanned the remaining rating-successor program after the
  user chose full recapture of every permitted historical season and a broad
  mixed methodology redesign.
- **Outcome:** Persisted four decision-complete, separately gated contracts for
  R1, R2, R3, and R4; amended the governing plan; superseded the narrower R1
  reliability contract while preserving its reusable implementation.
- **Plan Contracts:**
  `docs/plans/2026-08-27/r1-full-corpus-recapture-and-certification.md`,
  `r2-redesigned-offseason-prior-tournament.md`,
  `r3-mixed-state-update-tournament.md`, and
  `r4-structured-predictor-and-candidate-v2-freeze.md`.
- **Approval / Status:** User explicitly authorized implementation of the exact
  full-corpus plan on 2026-08-27. All four contracts are `Approved`; execution
  remains staged and begins with a fresh R1 Terra task after separate plan commit.
- **Blockers:** `PREVIEW_DATABASE_URL` is not present in the normal `.env`; it
  must be loaded through the isolated Preview workflow and verified distinct
  before migration or capture.
- **Next:** Commit the planning slice separately, then open a fresh Terra task
  for the R1 contract only.

## Context and Decisions

- Recapture 2015–2019 and 2021–2025 from CFBD; do not reuse old refs as
  authoritative successor parents.
- Use capture-only ingestion because standard ingesters call `ingest_data()`
  and could overwrite 2021–2025 legacy `raw/*` projections.
- Preserve the committed weekly request ledger/worker but supersede its
  compatibility-projection behavior and four-season scope.
- Redesign the tournament before new results are inspected. R2 uses pooled,
  EWMA, and Ridge priors; R3 compares Bayesian, recency, Glicko-style, and
  constrained ML updaters; R4 compares structured and residual predictors.
- Ranking plausibility remains diagnostic. Structural validity, uncertainty,
  chronology, calibration, and predictive gates remain hard requirements.
- Reserve 2025 for one end-to-end locked confirmation after the complete design
  freezes, rather than inspecting it separately at R2 and R3.

## Work Completed

- Added four approved implementation contracts with ordered tasks, interfaces,
  tests, stop conditions, and definitions of done.
- Added Amendment 2 to the governing historical-expansion plan.
- Marked the narrower R1 reliability plan Superseded and retained its reusable
  implementation lineage at `2c7018d`.
- Updated the contracts index and recorded the fresh-Terra execution order.

## Files Modified

- `docs/plans/2026-08-27/r1-full-corpus-recapture-and-certification.md`
- `docs/plans/2026-08-27/r2-redesigned-offseason-prior-tournament.md`
- `docs/plans/2026-08-27/r3-mixed-state-update-tournament.md`
- `docs/plans/2026-08-27/r4-structured-predictor-and-candidate-v2-freeze.md`
- `docs/plans/2026-08-26/historical-expansion-ratings-methodology-reset.md`
- `docs/plans/2026-08-27/r1-play-capture-reliability-hardening.md`
- `docs/plans/index.md`
- `session_logs/2026-08-27/12-full-corpus-successor-v2-planning.md`

## Validation

- [x] `git diff --check`
- [x] `uv run mkdocs build --quiet`
- [x] Confirmed documentation-only worktree diff.

## Amendments and Blockers

- The full-corpus choice is a material Amendment 2 to the governing plan and
  supersedes the earlier ref-reuse and tournament-roster decisions.
- No implementation file, migration, Preview catalog row, R2 object, model
  artifact, or production state was changed in this planning task.

## Handoff Notes

- **Resume at:** Fresh Terra task using the exact R1 contract path after the
  user-controlled planning commit.
- **Watch out for:** Do not run standard historical ingesters for 2021–2025;
  their compatibility writes violate the capture-only contract. Do not begin
  R2 before R1 says `tournaments_permitted: true`.

Copy-ready Terra handoff:

```text
Use the repository-local implement-plan skill and implement the approved contract at:

docs/plans/2026-08-27/r1-full-corpus-recapture-and-certification.md

Treat it as authoritative. Preserve its architectural decisions, run its validation,
and stop for any material conflict. This request explicitly authorizes implementation.
```

**tags:** ["ratings", "r1", "r2", "r3", "r4", "planning", "historical-data"]
