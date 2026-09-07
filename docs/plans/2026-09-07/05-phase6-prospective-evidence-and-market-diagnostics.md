# Phase 6: Prospective Evidence and Market Diagnostics

- **Status:** Approved
- **Created:** 2026-09-07
- **Planner:** Sol
- **Approval source:** User-approved 2026-09-06 resequencing contract, `docs/plans/2026-09-06/06-transformation-documentation-and-phase3-plus-resequence.md`.
- **Implementation log:** Pending Phase 5
- **Commit policy:** Separate plan and implementation/evidence commits; user executes Git operations.

## Goal

Collect valid future frozen evidence for the Phase 5 candidate against V4, then
compare authentic prediction-time and closing market quotes only after football
forecast evaluation. Phase 6 may recommend retaining V4, continuing shadow
evidence, or drafting a separate Phase 7 promotion plan; it cannot activate a
model.

## Current State

This phase requires the signed Phase 5 candidate through `--phase5-candidate-uri`.
Week 0 and every week before a valid candidate freeze are ineligible. Historical
reconstructed lines and outcomes are development/diagnostic evidence only and
never count as prospective evidence.

## Interfaces and Safeguards

- CLI input: `--phase5-candidate-uri`; freezes bind code/config, training
  cutoff, exact inputs/model-state identity, population, predictions, quote
  lineage, and freeze timestamp under version-1 freeze/evaluation schemas.
- Target T-2h before the first kickoff; require at least T-1h. Freeze candidate
  and V4 predictions on paired games before kickoff.
- Require six completed normal-coverage slates of at least 40 games. Any
  candidate change starts a new evidence window; freezes may never be backdated.
- Score finalized outcomes no earlier than 24 hours after completion. Apply
  behavior remains Preview-only; V4 production/publication/rollback are unchanged.

## Implementation Tasks

### Task 1 — Freeze and score eligible slates

- Validate timing, immutable identity, code/config/data lineage, paired game
  populations, and prediction completeness before declaring a freeze eligible.
- Score only finalized outcomes after the 24-hour minimum. Report paired V4 and
  candidate error, broader candidate coverage separately, and every exclusion.
- Permit only predefined updates using prior completed games. Late, incomplete,
  changed, or unverifiable freezes are permanently ineligible for the counter.

### Task 2 — Publish market diagnostics after football evaluation

- For eligible slates, compare authentic prediction-time and closing quotes
  separately, preserving quote IDs, timestamps, providers, and paired coverage.
- Report football forecast error, market-implied error, prediction-time
  disagreement, closing-line disagreement, and quote omissions. Do not call
  reconstructed evidence CLV or use markets in model fitting/selection.

### Task 3 — Issue the evidence recommendation

- After six eligible slates, publish an immutable recommendation: retain V4,
  continue shadow evidence, or draft a separate Phase 7 promotion/operational
  readiness contract. No recommendation activates or publishes the candidate.

## Validation

- Test cutoff timing, no-backdating, immutable collision, candidate-change
  resets, paired populations, final-outcome wait, quote authenticity/lineage,
  counting rules, deterministic scoring, and all exclusion paths.
- Run focused prospective/market/ops tests plus full warning-as-error Python,
  coverage, Ruff, contracts validation, strict MkDocs, V4/boundary checks, and
  `git diff --check`.

## Definition of Done

- [ ] Six qualifying slates are independently verifiable or the report explains
  why continued shadow evidence is required.
- [ ] Football evaluation precedes separate authentic-quote diagnostics.
- [ ] No freeze is backdated and no model is activated or published.
- [ ] Artifacts, validation, documentation, and a session log are complete.

## Amendments

Promotion, publication, evidence-window changes, betting decisions, thresholds,
or market-informed modeling requires a revised approved contract.
