# V5-01: Close the Independent V4 Feature-v5 Diagnostic

- **Status:** Implemented
- **Created:** 2026-09-13
- **Planner:** Codex planning task
- **Approval source:** User explicitly selected separate diagnostic closure and approved the full package on 2026-09-13 with “Implement the proposed plan.” Execution authorized 2026-09-22 ("Use the repository-local implement-plan skill and implement the approved contract…").
- **Implementation log:** `session_logs/2026-09-22/02-v4-feature-v5-diagnostic-closure.md`
- **Commit policy:** Separate diagnostic evidence/documentation checkpoint; user executes Git.

## Goal and current state

Close Task 5 of the [existing diagnostic](../2026-09-10/2026-v5-shadow-rebuild-diagnostic.md)
using its existing shadow artifacts and the now-recorded Week 2 finals. The
September 13 operations log records Week 2 closure; reverify the exact outcomes
and frozen refs before scoring. Week 0/1 scoring and prior parity gates are
completed work, not instructions to rebuild those artifacts.

The [common V5 contract](v5-ratings-successor-roadmap-and-contracts.md) governs
isolation and evidence interpretation. This task concerns V4 inference with
feature schema v5, not possession ratings or V5 prospective evidence.

## Approach, scope, and interfaces

Resume the original contract's Task 5 with all existing Amendments 1–3 and
cutoffs preserved. This contract authorizes only artifact-level scoring, paired
analysis, and closure documentation. The original diagnostic's permitted Preview
artifact paths remain valid; do not migrate existing output into the new
possession namespace. No new provider requests, production writes, serving-table
writes, catalog registration, model code changes, or new shadow predictions.

### Approved interpretation amendment

Preserve and report the original preregistered threshold: pooled Week 1+2 shadow
spread win rate >=50%, <45%, or otherwise inconclusive. Report its historical
label and threshold outcome separately from the causal interpretation.

An absolute win rate alone does not establish that feature mismatch caused V4
underperformance. The causal assessment must describe the paired prediction and
error differences under identical bundle, inputs apart from the intended feature
change, cutoffs, game population, and market refs. Value-identical predictions
cannot explain different forecast performance. Do not invent a replacement
significance threshold, tune the diagnostic, or label hypotheses as established.

## Implementation tasks

### Task 1 — Reconcile refs and recover grading inputs

**Files/evidence:** Existing diagnostic and its latest implementation log;
September 13 Week 2 close record; immutable shadow predictions and production
final-outcome refs.

**Changes:** Verify Preview R2 configuration without exposing credentials. Read
exact refs from the completed diagnostic records, validate hashes and forecast
cutoffs, and recover the final outcomes ref from Week 2 close pipeline run
`cb75ca881f3a49d5bd115c4fdeaa7dcb`. Confirm full 49-game Week 2 outcome coverage;
do not guess an object path or use mutable latest data instead of a pinned ref.
Recheck unchanged official run identities and serving pointers with read-only
queries if required by the original contract.

**Acceptance:** Shadow Week 2 prediction identity and final outcomes are exact,
recoverable, and grading-safe. Missing, mismatched, or unavailable refs block
scoring; they do not authorize regeneration with newer inputs.

### Task 2 — Score and independently compare

**Tools:** Existing `scripts/pipeline/score_weekly_bets.py` artifact-only path.

**Changes:** Score `shadow-2026-v5-w2` using the verified outcomes URI and original
artifact, retaining idempotency and immutable-collision behavior. Reuse existing
Week 0/1 scored artifacts. Never invoke `score_to_db.py`, `publish_to_db.py`, a
freeze operation, or serving upserts.

Produce a paired table for Week 0, Week 1, Week 2, and pooled Week 1+2 (92 unique
games). Report Week 0's eight games separately and exclude them from the pooled
threshold. Show prediction differences, MAE/bias changes by target, win/loss/push
counts, ungraded/No-Bet counts, and actual win-rate denominators. Do not assume 92
graded observations for each target. Freeze the original threshold denominator
convention from the existing scorer; a discovered discrepancy requires an
explicit amendment rather than silent denominator replacement.

**Acceptance:** An independent computation from exact prediction/outcome/market
artifacts reproduces all counts, metrics, and threshold labels. Preserve original
official and shadow artifacts; zero serving-state changes.

### Task 3 — Close the diagnostic record

**Files:** Existing diagnostic contract, `docs/plans/index.md`, this contract,
new session log, and a linked diagnostic results document under `docs/research/`.

**Changes:** Record refs, hashes, paired results, the interpretation amendment,
and justified next hypotheses. Remove the obsolete finals blocker only after
the scoring/verification succeeds. Link the final verdict from the existing
contract and mark both execution records Implemented when all gates pass.

## Testing strategy and risks

No product-code changes or new unit tests are required. Validate input hashes,
population, outcome coverage, paired metric recomputation, idempotency, and
read-only before/after serving-state evidence. Run strict MkDocs and
`git diff --check`. Source score corrections, inconsistent denominators, or old
artifact/code differences must be explained rather than treated as feature gains.

## Definition of done and amendments

- [x] Final Week 2 scored artifact and independently recomputed pooled report exist. (`…/scored/year=2026/week=2/run_id=shadow-2026-v5-w2/scored.csv`; `docs/research/2026-09-22-v4-feature-v5-diagnostic-closure.md`)
- [x] Original threshold calculation and causal limitations are both explicit. (38.46% < 45% → cause not confirmed; value-identical predictions across 100/100 games refute the mismatch as cause.)
- [x] No production, catalog, or Preview serving writes occurred. (Counts/current_week identical before/after in both databases; idempotent rerun.)
- [x] Contracts/index/session log reflect completion with exact refs and validation.

**Closure record (2026-09-22):** Verdict — pooled W1+W2 shadow spread 35-56-1
on 91 graded (38.46%) < 45% → **cause not confirmed**; shadow ≡ official on all
100 games (drift 0.0), refuting the feature mismatch as the cause of the 2026
spread underperformance. Full record, tables, and reproduction:
[`docs/research/2026-09-22-v4-feature-v5-diagnostic-closure.md`](../../../research/2026-09-22-v4-feature-v5-diagnostic-closure.md).

Use the common amendment process. Production repair or activation is a separate
future contract regardless of this diagnostic's result. This task never selects
the V5 ratings model or counts toward its six-slate evidence window.
