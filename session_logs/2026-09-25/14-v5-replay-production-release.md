# Session: V5 replay production release execution

## TL;DR

- **Worked On:** Executed the approved replay packet: production 0015, policy seed, 5 authorization inserts, publish/score/select for Weeks 0–4.
- **Outcome:** The public site now selects V5 replay for all 2026 weeks (W0–3 scored with frozen-quote grades: spread 72-82-3, total 67-54-0; W4 published 58/58 pending finals). V4 runs frozen/scored and re-selectable; health endpoint confirms the cutover.
- **Plan Contract:** `docs/plans/2026-09-25/02-v5-week4-replay-site-cutover.md` (Approved), Task 5.
- **Approval / Status:** User approved all five weeks + W0–W3 frozen-quote grading (Amendment 3). No step exceeded those approvals.
- **Blockers:** None. W4 scoring/selection-refresh awaits its 58 certified finals.
- **Next:** After W4 finals certify: score V5 W4 (outcomes + frozen-quote grades), refresh its selection receipt; continue the Week 5 live path at the finals gate.

## Context and Decisions

- Production execution exposed a latent blocker: `SELECT ... FOR SHARE` needs write privilege, so the SELECT-only pipeline role could not read either authorization table — every authorized production V5 write (including the previously approved live path) failed closed at the read. Removed the locking clause from both require functions (Amendment 2); integrity rests on append-only tables with no concurrent writer plus byte-exact R2 revalidation inside each transaction. Probe-verified on Preview first; regression-tested.
- W0–3 grading (Amendment 3) reuses the frozen V4 pre-kickoff quotes per game (all verified pre-kickoff), the pipeline frozen-line rule, and V4's grading basis (all spreads; totals at edge ≥ 1.5). Dry-run previewed before commit; results are retrospective, never superiority claims.
- Incidental finding: scoring V5 runs zeroed the derived `system_stats` table (recompute prefers newest scored per week). Nothing user-facing reads it (the site computes records live from selected runs' grades); V4 grades are intact; the next close-week recomputes it. Documented here instead of hand-forging rows.

## Work Completed

- Applied migration 0015 in production (checksum `5659a5b5…` matches the committed file); verified 0 rows and pipeline SELECT-only / web-blocked grants through the real role connection.
- Seeded `v5_release_policy` id=1 (model, pinned bundle, first-live 2026 Week 5, replay-cutover decision ref).
- Inserted the 5 approved replay authorization rows verbatim from the validated packet files.
- Published all 5 V5 runs to production via `cks_prod_pipeline` (8/43/49/57/58; current_week untouched by publish).
- Scored W0–3 outcomes + frozen-quote grades (278 grade rows); selected W0–4 with explicit retrospective reasons (`current_week` now points at the V5 W4 run; V4 W4 stays frozen).
- Verified: selections, grade counts, V4 runs untouched, public `/api/health` shows the V5 W4 active run at 58/58.

## Files Modified

- `src/cks_picks_cfb/ops/v5_release.py` - removed row-lock reads (Amendment 2).
- `tests/test_v5_release.py` - no-locking-clause regression test.
- `docs/plans/2026-09-25/02-v5-week4-replay-site-cutover.md` - Amendments 2 and 3.

## Validation

- [x] Focused V5 suites + ruff + contracts-check + strict MkDocs + `git diff --check`.
- [x] Real-role grant readbacks (replay table SELECT-only; web blocked).
- [x] Packet validator `valid: true` for all five weeks before any write.
- [x] Production readback of every mutation (rows, states, grades, selections, V4 intact).
- [x] Public health endpoint confirms serving state.

## Amendments and Blockers

Amendments 2 (row locks) and 3 (W0–3 grading) recorded in the plan. No code, R2, or Neon mutation beyond the approved release steps.

## Handoff Notes

- **Resume at:** When W4 finals certify: score `2026w4-v5replay-w4` (same frozen-quote mechanism; quotes already staged), re-verify selection/health, then continue the Week 5 live plan (01-v5-week4-finals-to-live-preview.md) at its gate.
- **Watch out for:** Rollback = select `2026w4-da5d98761831` (frozen, 58/58) with `--allow-v4-fallback`, exactly as rehearsed. Never insert authorizations for unapproved weeks; never reuse packets across runs. The `system_stats` table will be rewritten by the next close-week recompute.

**Suggested commit message:** `Release V5 replay history to production site`

**tags:** ["v5", "replay", "release", "production"]
