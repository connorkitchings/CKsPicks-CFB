# Session: V5 Possession Certification Apply Handoff

## TL;DR

- **Worked On:** Executed the committed-code V5-02 Preview preflight and began
  the approved apply sequence under the user-selected 30-minute per-invocation
  limit.
- **Outcome:** The no-write preflight passed in 1,513 seconds and reproduced
  every producer row count and digest from the preserved diagnostic artifact.
  The initial apply was stopped before writes because its mandatory two-pass
  implementation cannot complete within the 30-minute ceiling. The target
  prefix remains empty. A bounded write-only apply handoff is implemented
  locally and requires a user-controlled code commit before certification can
  resume.
- **Plan Contract:** `docs/plans/2026-09-13/02-v5-possession-measurement-certification.md`
  (Amendment 2).
- **Approval / Status:** User explicitly authorized execution with “go” on
  2026-09-15. Contract remains **In Progress**.
- **Blockers:** The amended runner must be committed, producing a new SHA-bound
  run identity. No possession measurement artifact is eligible for V5-03 yet.
- **Next:** Commit the local amendment, then run a new dry run and a single-pass
  `--apply --preflight-evidence` attempt with a 30-minute limit, followed by
  independent verification and idempotency.

## Context and Decisions

- Baseline: clean `main` at
  `ac1fd6b24190d72122a4b2d1c663952d56bb5af3`; `CFB_STORAGE_BACKEND=r2`; both
  source and Preview R2 credential sets were present without printing secrets.
- Frozen first-attempt identity:
  `possession-v1-measurements-20260915-ac1fd6b-r3`, as-of
  `2026-09-15T13:22:37Z`, with the exact verified Repair v2 manifest
  `artifacts/research/data-first-football-v1/repair/v2/runs/repair-v2-20260909T1417Z/repair-manifest.json`.
- The target prefix was empty before preflight, after preflight, and after the
  stopped apply. No R2 object was written by this session.
- The no-write preflight completed in 1,513.107 seconds. It produced 8,936
  population rows (8,935 forecast-eligible), excluded 2020, retained the fixed
  PPP/EPA settings, and bounded history partitions at 6,516 rows.
- The signed preflight certification SHA was
  `be4fcb6ec1e50356f1230b5831bb775e5383507f2c51cc736476a15badd15fa1`.
  Its eight output row counts and record digests exactly matched the preserved
  `f7b6fe4` diagnostic producer artifact; that artifact remains ineligible only
  because its verifier was not independent.
- The established pinned-source reconciliation remains 98.06%–99.53% by
  season, above the 94% gate. Exact PPP/EPA coverage and quarantine reasons were
  re-read from the matching immutable coverage artifact before attempting apply.
- The legacy apply first computes a no-write preflight then computes a second
  write-time preflight. Given the measured first-pass runtime, it cannot meet the
  fixed 30-minute invocation limit. It was interrupted before any output write
  rather than knowingly create an ineligible partial prefix.
- Amendment 2 adds an evidence-validated single-pass apply path. It serializes
  the full partition plan on dry run and compares the write-time replay's rows,
  digests, and certification SHA against that reviewed evidence.

## Work Completed

1. Ran the full R2 Preview dry run and inspected its identity, source checksums,
   output counts/digests, scale diagnostics, coverage, and replay progress.
2. Confirmed exact producer determinism against the preserved Preview diagnostic
   output and retained its ineligible status.
3. Started then safely stopped the legacy apply before any write, confirming the
   target prefix remains empty.
4. Added `--preflight-evidence` support, strict identity/part-plan validation,
   and write-time replay comparison to the possession runner.
5. Added runner tests for complete plan reconstruction and tampered summary
   rejection.

## Files Modified

- `scripts/research/run_data_first_possession_measurements.py` — serialized
  dry-run part plans and a reviewed-evidence, write-only apply path.
- `tests/test_data_first_possession_runner.py` — plan-reconstruction and
  summary-integrity coverage.
- `docs/plans/2026-09-13/02-v5-possession-measurement-certification.md` —
  Amendment 2 and this log link.
- `session_logs/2026-09-15/01-v5-possession-certification-apply-handoff.md` —
  this log.

## Validation

- [x] `tests/test_data_first_possession_runner.py` — 7 passed with warnings as errors.
- [x] Focused V5-02 regression set — 72 passed with warnings as errors.
- [x] Scoped Ruff format and lint.
- [x] Runner CLI help exposes `--preflight-evidence`.
- [x] R2 prefix empty before/after the stopped apply.
- [x] Full warning-as-error coverage suite — 888 passed, 2 skipped, 67.44%.
- [x] `make contracts-check`.
- [x] Strict MkDocs build to `/private/tmp/ckspicks-v5-possession-apply-handoff`.
- [x] `git diff --check` before the final added identity-mismatch regression;
  rerun after the user-controlled commit and successful certification sequence.

## Amendments and Blockers

- Amendment 2 is mechanical: it preserves the exact original dry-run/write-time
  comparison while avoiding an unfinishable duplicate first pass under the fixed
  time limit.
- Do not reuse the `ac1fd6b-r3` identity after the code commit. Do not use any
  `f7b6fe4` output as a V5-03 parent.

## Handoff Notes

- **Resume at:** User commits the local runner/test/documentation checkpoint,
  capture the new full SHA, and choose
  `possession-v1-measurements-20260915-<new-sha7>-r4`. Run its dry preflight;
  preserve the resulting stdout JSON; then run apply with the exact same flags
  plus `--preflight-evidence <that-json>`.
- **Watch out for:** The apply evidence JSON must carry the new code SHA and
  exact identity; the old `/private/tmp` JSON is diagnostic-only and cannot be
  reused. Maintain the 30-minute cap separately for dry run, write-only apply,
  and verifier.

**tags:** ["v5", "ratings", "possession", "certification", "r2", "preview"]
