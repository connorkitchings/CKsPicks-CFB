# Session: R1 Cross-Lineage Audit Scope Remediation

## TL;DR

- **Worked On:** Continued Task 3 of the derived-schema contract: executed the
  full-corpus Preview R1 pipeline through three fresh code-bound runs,
  diagnosed and remediated two further latent defects in never-executed
  certification-path code, and aligned the certification gate with its
  contract-defined metric.
- **Outcome:** Runs `r1-full-corpus-20260828-2cb4d5a` and
  `r1-full-corpus-20260829-aaac30d` each completed captures, Silver, derived
  refs, and (for the latter) foundation + certification, exposing: (1)
  `DatasetRef(**entry)` crashes on derived-ref-set `season` scope fields in
  the foundation and certification scripts; (2) a certification metric that
  re-derived score reconciliation as observed-PPSO game coverage instead of
  the contract's finals-exact rate. Both fixed and tested; run
  `r1-full-corpus-20260829-e9edee5` (code `e9edee5`) is in flight.
- **Plan Contract:**
  `docs/plans/2026-08-28/r1-cross-lineage-audit-scope-remediation.md`
- **Approval / Status:** User directed continuous execution on 2026-08-28
  ("keep rolling"); the contract is `Approved` with Amendments 1–2.
- **Blockers:** None currently; R2 stays blocked until
  `tournaments_permitted: true`.
- **Next:** Monitor `r1-full-corpus-20260829-e9edee5` through certification;
  verify `tournaments_permitted: true`; run the identical invocation once more
  for deterministic-recovery verification.

## Context and Decisions

- A prior same-day attempt (17:00 UTC) had already bound run ID
  `r1-full-corpus-20260828-962f85d`. It completed all captures, Silver, and
  derived refs — validating the schema remediation — then failed at
  `audit_successor_cross_lineage` on two check mis-specifications (games ≡
  outcomes membership is impossible by Silver scope design; legacy evidence
  itself carries a canceled 2024 game with null scores). Fixed with
  per-dataset legacy parity plus canceled-game set equality; verified
  read-only against the real evidence; committed as `2cb4d5a`.
- The one-run-one-identity rule (`_successor_r1_identity()` binds
  `git rev-parse HEAD`) means every code fix requires a fresh full-corpus run;
  recapture is ~35–50 minutes and cheap relative to correctness.
- Runs resume same-ID only with an identical definition (same as_of); two
  sanctioned resumes occurred on `…-2cb4d5a` (Neon connection timeout; CFBD
  502 outage) and reused completed checksummed captures exactly as designed.
- Amendment 1: `build_successor_r1_foundation` and
  `certify_successor_history` crashed parsing derived-ref-set entries
  (`TypeError … 'season'`). Added shared scope-aware parser
  `derived_history_dataset_refs()`; committed as `aaac30d`.
- Amendment 2: run `aaac30d` completed all 127 steps but reported
  `tournaments_permitted: false` because 2021–2025 failed
  `score_stream_reconciliation` at 0.816–0.896 observed-PPSO game coverage.
  Root cause: isolated CFBD cumulative-score-field glitches (verified
  byte-identical in the Aug-9 bootstrap corpus and the passing Aug-26 v3
  byplay) quarantine PPSO at offense granularity per the deliberate 2026-08-26
  policy, and the new certification code misread the 0.94 gate as this
  coverage instead of the finals-exact reconciliation rate the contract's
  Task 4 and Phase-1 v3 precedent define (which passes 0.949–0.997 for every
  season, immutable in the measurement report). The gate now reads
  finals-exact counts from the measurement report; observed-PPSO coverage is
  a reported diagnostic. Thresholds and quarantine policy unchanged;
  committed as `e9edee5`.
- Preview launches must use `zsh scripts/ops/with_preview_env.sh`
  (Keychain-injected `PREVIEW_DATABASE_URL`).

## Work Completed

- Diagnosed all three failures with read-only probes against immutable
  artifacts (cross-lineage semantics, ref-set parsing, score-stream
  quarantine vs finals reconciliation).
- Implemented and tested: scope-correct `compare_season`; shared
  `derived_history_dataset_refs()`; finals-exact certification gate with
  observed-PPSO diagnostics.
- Recorded the remediation contract with Amendments 1–2 and the plan-index
  entry; commits `69e1fcf`, `2cb4d5a`, `aaac30d`, `e9edee5`.
- Launched `r1-full-corpus-20260829-e9edee5` (as_of `2026-08-29T01:23:11Z`).

## Files Modified

- `src/cks_picks_cfb/ratings/cross_lineage.py` — scope-correct comparisons.
- `src/cks_picks_cfb/ratings/successor_history.py` — shared ref-set parser;
  finals-exact evidence fields and gate.
- `scripts/pipeline/build_successor_r1_foundation.py` — uses shared parser.
- `scripts/pipeline/certify_successor_history.py` — shared parser;
  finals-exact evidence extraction.
- `tests/ratings/test_cross_lineage.py`, `tests/ratings/test_successor_history.py`
  — regression coverage (7 + 2 new tests).
- `docs/plans/2026-08-28/r1-cross-lineage-audit-scope-remediation.md`,
  `docs/plans/2026-08-28/r1-derived-schema-registration-and-atomicity.md`,
  `docs/plans/index.md` — contract record.

## Validation

- [x] Full Python suite at each fix: 584 → 585 → 586 passed, 2 skipped.
- [x] Scoped Ruff format + check; `make contracts-check`; strict MkDocs;
  `git diff --check`.
- [x] Read-only pre-verification of each fix against real immutable evidence.
- [x] Cross-lineage audit passed live on runs `2cb4d5a`, `aaac30d`
  (`all_checks_passed: true`).
- [ ] Run `e9edee5` through certification with `tournaments_permitted: true`.
- [ ] Identical-invocation deterministic recovery rerun.

## Amendments and Blockers

- Governing contract Amendment 1 (discovered 17:00 UTC run); remediation
  contract Amendments 1–2 (ref-set parser; finals-exact gate).

## Handoff Notes

- **Resume at:** Poll the ops ledger / run log for
  `r1-full-corpus-20260829-e9edee5`; on success verify coverage.json, then
  rerun the identical invocation (same run ID + as_of
  `2026-08-29T01:23:11Z`) to prove deterministic recovery.
- **Watch out for:** Failed runs are immutable diagnostics; never reuse a
  failed source set as parent; do not weaken the finals-exact threshold or
  quarantine policy without a new Sol review; R2 begins only after
  `tournaments_permitted: true`.

**tags:** ["r1", "cross-lineage", "certification", "ratings", "preview",
"historical-data"]
