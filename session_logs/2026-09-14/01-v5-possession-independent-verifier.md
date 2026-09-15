# Session: V5 Possession Independent Verifier Correction

## TL;DR

- **Worked On:** Corrected Contract 02 verifier independence, bounded comparison,
  long-run observability, and apply idempotency before strict recertification.
- **Outcome:** The corrective code checkpoint is complete and locally validated.
  The prior `f7b6fe4` artifact is preserved as a Preview-only failed certification
  attempt and cannot be used by Contract 03.
- **Plan Contract:** `docs/plans/2026-09-13/02-v5-possession-measurement-certification.md`
  Amendment 1.
- **Approval / Status:** User explicitly approved the strict recertification plan
  and directed implementation. Contract status remains **In Progress** pending a
  new committed-code Preview run and independent verification.
- **Blockers:** User-controlled corrective code commit is required before selecting
  the new SHA-bound `r3` run identity.
- **Next:** Commit this checkpoint, then run the exact dry-run/apply/verifier/
  idempotency sequence under the new committed SHA.

## Context and Decisions

- The initial verifier imported producer `build_measurements` and replay logic.
  Its internally matching result did not satisfy the independent-reconstruction
  requirement.
- The immutable run
  `possession-v1-measurements-20260914-f7b6fe4-r2` remains intact for diagnosis;
  no object was deleted, overwritten, promoted, or made a rating parent.
- Strict failure policy requires a new code SHA and unused run identity. No gate,
  methodology, constant, parent, or possession definition was changed.

## Work Completed

- Added verifier-owned population, canonical team attribution, possession/scoring
  ledgers, paired measurements, coverage, final-score reconciliation, four-pass
  adjustment, prior-only snapshots, adjusted history, and terminal reconstruction.
- Removed imports of producer measurement/replay functions from the verifier and
  added an AST import-boundary regression test plus a producer-only perturbation
  test.
- Changed stored adjusted-history verification from full concatenation to
  season/week partition reads and per-part row/key/canonical-digest comparisons.
- Removed pandas' deprecated all-null concatenation inference from cross-season
  source loading and verified all focused paths with warnings treated as errors.
- Added structured stderr JSONL phase events and a true 30-second background
  heartbeat. Final machine-readable results remain stdout-only; secret-like fields
  are excluded from progress payloads.
- Added early matching-manifest/certification validation so repeated apply returns
  `already_applied` before expensive preflight; incompatible identities still fail.
- Tightened apply to require a fully clean committed worktree, including untracked
  files, and added the new verifier/progress files to committed-path enforcement.

## Files Modified

- `src/cks_picks_cfb/ratings/possession_verification.py` — independent
  reconstruction implementation.
- `scripts/research/verify_data_first_possession_measurements.py` — streaming
  independent verifier, source-contract checks, progress, and final evidence.
- `src/cks_picks_cfb/data/research_progress.py` — producer progress and heartbeat.
- `src/cks_picks_cfb/ratings/possession_measurements.py` — bounded producer progress
  callbacks only; measurement semantics are unchanged.
- `scripts/research/run_data_first_possession_measurements.py` — progress,
  warning-safe source loading, strict clean-worktree enforcement, and fast
  idempotency.
- `tests/ratings/test_possession_verification.py` and
  `tests/test_data_first_possession_runner.py` — independence, perturbation,
  chronology, progress, warning, idempotency, and collision tests.
- `docs/plans/2026-09-13/02-v5-possession-measurement-certification.md` — Amendment
  1 and corrective log link.

## Validation

- [x] Focused possession/schema/runner/verifier suite: 21 passed with `-W error`.
- [x] Full coverage suite: 884 passed, 2 skipped, 67.40% coverage with `-W error`.
- [x] Scoped Ruff format and lint.
- [x] `make contracts-check`.
- [x] Strict MkDocs build to
  `/private/tmp/ckspicks-v5-possession-verifier-20260914`.
- [x] Producer and verifier CLI `--help` smoke checks.
- [x] `git diff --check`.

## Amendments and Blockers

- Amendment 1 records the verifier-independence defect and strict full-rerun
  decision. This is a mechanical certification correction, not a semantic or
  methodological amendment.
- No R2 apply, catalog, provider, database, production, activation, or V4 change
  occurred in this checkpoint.
- Contract 02 cannot be marked Implemented and Contract 03 remains blocked until
  the new artifact passes independent verification and idempotency.

## Handoff Notes

- **Resume at:** User commits with
  `fix(research): independently verify possession measurements`. Then derive
  `possession-v1-measurements-20260914-<new-sha7>-r3`, reconfirm Preview R2
  credentials and empty identity, and run the committed-code dry run.
- **Watch out for:** Use the exact Repair manifest, sealed config, and as-of value.
  Do not reuse the `f7b6fe4` output as a rating parent or fold Contract 03 into
  this certification checkpoint.

**tags:** ["v5", "ratings", "possession", "verification", "research", "preview"]
