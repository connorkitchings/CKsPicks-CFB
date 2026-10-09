# Session: Week 6 release resume — notice suppression + rollback rehearsal prep (Terra)

## TL;DR
- **Worked On:** Contract `02` resume: user decisions (mixed lineage accept, notice hidden, week-7 reunification), Amendment 4 web change, Task 2 rollback script + dry run.
- **Outcome:** Notice hidden behind `CFB_DISPLAY_ONLY_NOTICE=0` (both modes verified locally; web suite green). Rollback script written; Preview dry run scopes exactly 7,879 rows with all guards passing. Rehearsal `--apply` blocked on one privilege: `prediction_market_selections` is owned by `neondb_owner` with no DELETE grant. User chose one-time GRANT (user-run as owner); rehearsal proceeds after.
- **Plan Contracts:** `02-week6-display-production-release.md` (Amendment 4 appended; Task 2 in progress), `03-matchup-6a-bridge.md` (Implemented, committed as `3e20f2ce` by user mid-session alongside unrelated work)
- **Approval / Status:** implement-plan on `03` (done); release resume per user "proceed" + question answers.
- **Blockers:** Owner-run GRANT (statement below), then rehearsal `--apply` (user-run), then Production path (Tasks 3–6).
- **Next:** User runs the GRANT → rehearsal `--apply` (user-run) → verify hold screen locally → re-apply forward → verify open state → Tasks 3–6.

## Context and Decisions
- User accepted mixed lineage for Week 6 ("different host"), no labels, reunification at Week 7 (already the cutover plan — no change).
- "Don't label anything" disambiguated: the only label in the design is the timing notice. Dropping it reverses the Oct-8 disclosure decision but touches no evidence machinery: DB flag, freeze guard, unconstrained grading and prospective exclusion all unchanged. Implemented as `CFB_DISPLAY_ONLY_NOTICE=0` opt-out (default shows; mirrors the `CFB_MATCHUP_ENABLED=0` pattern). Verified hidden on Picks + Results with games intact, and shown when unset.
- W0–5 Production matchup degradation on selection documented in `02` Amendment 3 as requiring explicit accept (accepted via the mixed-lineage decision).
- Rollback script `scripts/pipeline/rollback_week6_display.py` (new): fail-closed guards (published/pending/display_only, selection + pointer must reference the run), dependency-ordered deletes with NOT EXISTS guards for shared market rows, sibling guard for the shared bundle approval, history-week-rows deletion documented as required by RESTRICT FKs, post-delete verification in-transaction with rollback on any remainder, R2 artifacts deliberately left in place.
- Ownership survey (Preview): 20/21 tables owned by `cks_preview_migrator`; only `prediction_market_selections` owned by `neondb_owner` with zero DELETE grants. Rehearsal `--apply` fails closed as migrator (proven: permission denied). User chose GRANT DELETE over run-as-owner or skipping.

## Work Completed
- Web: `display-only.ts` (`isDisplayOnlyNoticeEnabled`), both page call sites gated, unit test added (4/4 pass), README env docs; lint, typecheck, publication suite (fail 0), production build green; local Preview verification both modes.
- Rollback script written, ruff clean, `--help` + dry run green (7,879 rows; scopes match the release writes exactly: 110 selections, 55 predictions, 220 link rows, 58 venues/games, 508 components, 1,656 stats, 549 adjusted, 1 registry, 1,624 snapshots, 3,036 team stats, 1 run, 1 auth; 0 log rows correct).
- Contract `02`: Amendment 4 appended. Session mid-flight work (bridge commit `3e20f2ce`) verified present and intact in HEAD.

## Files Modified
- `web/src/lib/display-only.ts`, `web/src/app/page.tsx`, `web/src/app/results/page.tsx`, `web/src/lib/display-only.test.ts`, `web/README.md` - notice opt-out (uncommitted)
- `scripts/pipeline/rollback_week6_display.py` - new rollback script (uncommitted)
- `docs/plans/2026-10-09/02-week6-display-production-release.md` - Amendment 4 (uncommitted)
- `session_logs/2026-10-09/06-week6-release-resume.md` - this log (uncommitted)

## Validation
- [x] Web lint, typecheck, display-only unit (4/4), publication suite (fail 0), `next build` green
- [x] Local site both notice modes verified (shown unset / hidden with flag)
- [x] Rollback `--help`, ruff clean, dry run counts reconcile with release writes
- [x] `git diff --check` clean; unrelated worktree files untouched
- [ ] GRANT (user-run as owner)
- [ ] Rehearsal `--apply` + hold-screen verify + re-apply forward (user-run / authorized)
- [ ] Contract `02` Task 2 gate: user review of script + rehearsal

## Amendments and Blockers
- `02` Amendment 4 (notice opt-out; user-directed, disclosure implications stated).
- Blocker: owner-run GRANT below, then rehearsal `--apply`.

## Evening session: rehearsal proof + re-apply blocked on clean tree

- Rehearsal `--apply` executed (migrator, after both GRANTs): first attempt failed closed on game-scoped market rows (unselected capture rows), second on `current_week` FK order — both rolled back atomically with Preview byte-intact, proving the transaction design. Fixed by game-scoping market deletes + clearing the pointer first + adding `ops.activation_history`/`ops.waivers` run-scoped deletes (found via schema FK survey).
- Third `--apply`: **"Rollback applied and verified: hold-screen state restored"** (7,879 rows). Verified: `current_week` (2026,6)/NULL, 0 W6 games, d2/snapshots gone, weeks 0–5 selections intact; local site shows "Dropping Soon". **Task 2's hard gate is met.**
- Re-apply forward blocked: `authorize_v5_intended_update_preview --apply` demands a clean tree + reviewed shas. Worktree is dirty (this session's uncommitted files + the other workstream's byplay files). Original Oct-8 decision-ref recovered from the surviving approval row: `preview-rehearsal-display-only-week6` (reproduces record `951bd71c…`).
- `docs/status.md` Week 6 row updated truthfully (Preview also on hold until re-apply). No code changed after the green suite run except the rollback script fixes (ruff clean) + docs.
- Next: user commits (or stashes) to a clean tree → re-auth with original ref → seed → venues → publish → select → matchup → verify → open-state check (all Preview, all previously proven commands).

## Handoff Notes (updated)
- **Resume at:** user confirms GRANT → run rehearsal `--apply` → local hold-screen check → re-apply forward (ratings, stats as-of 6, matchup, publish_to_db, select) → local open-state check → Tasks 3–6.
- **Watch out for:** same ownership pattern likely exists in Production (`prediction_market_selections` there too) — check before the Production rollback would ever be needed; the grant decision for Production is separate. Never freeze/close Week 6.
- **Pending user-run statements:**
  ```sql
  -- Preview, as neondb_owner (one time):
  GRANT DELETE ON public.prediction_market_selections TO cks_preview_migrator;
  ```

**tags:** ["implementation", "week6", "rollback", "web", "preview"]
