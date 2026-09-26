# Session: V5 best-quote production release — Steps 1–8 complete, released

## TL;DR
- **Worked On:** Executed the Approved Phase 3 contract end to end: production migration 0016, release driver, candidate preparation, five validated packets, the Step 4 release decision (all five weeks), authorization inserts, publish/score/select, production readback, and close-out.
- **Outcome:** The public site now serves best-quote replacement runs for all 2026 Weeks 0–4 (W0–3 scored with 281 grades; W4 published 58/58, unscored). V4 and original replay runs untouched. Parent plan Implemented.
- **Plan Contract:** `docs/plans/2026-09-26/01-v5-bestquote-production-release.md` (Implemented)
- **Approval / Status:** User release decision "proceed with all" recorded; execution complete.
- **Blockers:** None. W4 replacement scoring waits at its own finals gate (0 certified finals).
- **Next:** Commit; W4 scoring at finals gate; production debut of future-week best-quote runs at their own gates; Week 5 live lane continues separately.

## Context and Decisions

- Admin role for production migration/inserts is the `neondb_owner` URL (`DATABASE_URL_UNPOOLED`); pipeline mutations use `cks_prod_pipeline` via the production wrapper. No admin keychain item exists; no secret was written to the repo.
- Manifest namespace precedent confirmed from the prior cutover: production replays keep `predictions.csv`/features byte-identical and rewrite only the manifest's `artifact_uri`/`feature_snapshot_uri` to `artifacts/production/…`.
- Release run IDs match the verified Preview `-r2` batch in both namespaces (prior lane precedent).

## Work Completed

- Applied migration 0016 on production (checksum-enforced); readback: latest migration, table, `market_quote_id` column, `cks_prod_pipeline` SELECT+INSERT, `cks_prod_web` SELECT-only.
- Built `scripts/pipeline/release_v5_bestquote_replacement_production.py` (`prepare`/`packet`/`score`/`verify` + production guards + market-tick check) reusing the rehearsed verification suite; 5 unit tests in `tests/test_v5_bestquote_production_release.py`.
- Prepared 5 production candidates (byte-identical to the reviewed Preview builds — SHA-verified per week); built 5 packet JSONs (`/tmp/bestquote-packets/bestquote-2026w{0..4}-….json`); all five validate; precondition readback: 0016 latest, V4 frozen/scored intact, selections on originals, 0 existing bestquote auth rows, 0 W4 certified finals.

## Files Modified

- `docs/plans/2026-09-26/01-v5-bestquote-production-release.md` — new Approved contract
- `scripts/pipeline/release_v5_bestquote_replacement_production.py` — new release driver
- `tests/test_v5_bestquote_production_release.py` — new unit tests
- Production R2 only: candidate artifacts under `artifacts/production/predictions/year=2026/week={0..4}/run_id=2026w*-v5replay-bestquote-20260926-r2/`
- Production Neon: migration 0016 + privilege grants only; zero prediction/grade/selection/authorization writes

## Validation

- [x] Migration checksum pass + privilege readback (Step 1)
- [x] Scoped pytest (5 new) + full suite: 1,448 passed, 2 skipped
- [x] `ruff check .`, `ruff format`, `make contracts-check` unaffected (`git diff --check` clean)
- [x] `mkdocs build --strict --quiet`
- [x] `{"valid": true}` × 5 replay packets; precondition readback; byte-identity proof

## Amendments and Blockers

Release decision recorded (all five weeks). No code, R2, or Neon mutation beyond the contract's Steps 1–7. One operational note for the log: the first production publish attempt failed closed before any write because the direct `publish_to_db.py` invocation lacked `PYTHONPATH=.:src` (the `scripts` package import); retried with the documented path and succeeded. The rehearsal driver's `_publish` already sets this correctly.

## Execution record (Steps 4–8)

- **Step 4:** "proceed with all" (decision ref recorded on all five rows).
- **Step 5:** 5 authorization rows inserted under `neondb_owner` (IDs `v5-bestquote-2026w{0..4}-{c48bf913,bc021cfb,05bba834,9074cec0,ce9c7bc0}`); pipeline-role SELECT proven (5/5).
- **Step 6:** W0–3 published → scored → selected (15/80/87/99 = 281 grades; 157 spread + 124 total); W4 published → selected 58/58, unscored. Per-week `verify` passed on production (forecast equality, selections, grades, market ticks).
- **Step 7:** All five weeks select the replacements (W0–3 `scored`, W4 `published`); health `ok` with the W4 replacement active at 58/58/58 lined; V4 runs (frozen/scored, original grade counts) and original V5 replay runs (states + 15/78/86/99 grades) verified untouched. Rollback = single recorded selection per week; no live drill per the locked decision.
- **Step 8:** Parent plan Amendment 4 + Task 6 DoD Implemented; `v5_status.md` item 5 refreshed; this log; commit proposal below.

## Handoff Notes

- **Resume at:** User Step 4 decision. On approval, Step 5 (admin inserts of exactly the validated rows) → Step 6 (publish/score/select W0–3 then W4; expect 281 grades) → Step 7 (readback/health/rollback proof) → Step 8 (Amendment 4, DoD, docs, commit proposal).
- **Watch out for:** Never insert rows for unapproved weeks; never reuse these packets across runs/weeks/environments; W4 stays published+selected-unscored; Week 5 live lane keeps precedence at atomic checkpoints.

**tags:** ["v5", "best-quote", "production", "release", "packet"]
