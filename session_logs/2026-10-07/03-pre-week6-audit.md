# Session: Pre-Week-6 data/code audit and CI unblock

## TL;DR
- **Worked On:** Review of changes since 2026-10-04, diagnosis of the stalled PR #2 CI, live-path code fixes, and read-only Preview/Production data verification (plan tracks A–D).
- **Outcome:** CI "hang" diagnosed and fixed locally (not yet pushed). Four live-path code defects fixed. Preview and Production serving state, Week 5 grades, registrations, grants and migration ledger verified read-only and consistent with the recorded state. Two discrepancies and one provenance gap remain open (below). B1-B7 are done apart from re-running the 6A/6B stage verify operations (see finding 5).
- **Plan Contract:** `/Users/connorkitchings/.claude/plans/use-agent-skills-start-session-to-get-functional-sifakis.md` (session plan; user-approved; not a `docs/plans/` contract). Fast path for localized fixes.
- **Approval / Status:** User approved the plan in Plan Mode and chose to skip Week 6 until pre-Week-6 data and code are confirmed. No writes to any database, R2 or Git.
- **Blockers:** Exact-SHA CI is unproven until the user pushes. B6/B7 outstanding.
- **Next:** User commits and pushes; confirm all CI jobs green and under 20 minutes. `docs/status.md` updated this session (see Files Modified).

## Context and Decisions
- Week 6's first kickoff (Troy vs Southern Miss, 2026-10-07T00:00Z) passed with no run. The freeze code and migration 0023 reject a run whose earliest game has started, so Week 6 cannot be prospective. User decision: skip Week 6 publishing.
- CI "Python tests" was not deadlocked. Three causes (verified from logs of runs 37626495969, 37628301690, 37633960136):
  1. All 12 tests in `tests/test_v5_legacy_freeze_attestation.py` errored: they run `git rev-parse 446c880` / `git show`, and `actions/checkout` is a depth-1 clone.
  2. `tests/test_rebuild_6b_flow.py` takes about 12 minutes on one xdist worker (`--dist loadfile`), so the other workers sat idle at 96%.
  3. The repeated `apply_partition 2018 W3` heartbeats came from a progress thread that outlived its (already passed, ~8s) test. `faulthandler_timeout=120` stack dumps added to the look of a hang.
- The earlier theory of a deadlock in the 8-thread `PartitionedDatasetWriter` was wrong. It did not reproduce on macOS or in the CI logs' timing; retained here as a retraction.
- Local coverage without the 6B file, the DB-reset files and the rating-runner file is 65% (gate 60%), so the 6B flow became its own parallel job with no coverage merge.

## Work Completed
- `.github/workflows/ci.yml`: `fetch-depth: 0` for the pytest job; `--ignore=tests/test_rebuild_6b_flow.py` in the xdist step; new job "Python 6B rebuild flow" (25 min timeout, own checkout); `faulthandler_timeout` 120→300 (600 in the 6B job).
- `tests/test_data_first_possession_rating_runner.py`: autouse fixture closes each `_Progress` heartbeat at test end.
- C1 `Makefile`: `freeze-week` forwards `DECISION_REF` to `--decision-ref`.
- C2 `scripts/pipeline/freeze_week.py`: the decision-ref requirement now runs after the missed-deadline branches, so a past-deadline pending run is recorded as `missed` instead of raising. New `tests/test_freeze_week_deadline.py` (2 tests; the missed-deadline one fails on the old code).
- C3 `web/src/app/performance/page.tsx` + new `web/src/lib/performance-sections.ts` (+ test, registered in `test:publication`): replay and prospective sections load independently; a prospective failure shows its own "temporarily unavailable" card and no longer blanks the replay record. `v5.ts` still throws (fail closed) on an unknown receipt or incomplete coverage.
- C4 `scripts/pipeline/select_v5_intended_update_batch.py`: error text no longer says "v2" in the v1 path.
- Read-only audit scripts and results saved in `docs/plans/2026-10-07/pre-week6-audit-evidence/` (checksums in `checksums.txt`; no connection strings stored).

## Verification Results (read-only, restricted roles, `default_transaction_read_only=on`, captured 2026-10-07T14:34Z)
- **B1 serving state (both envs):** `current_week = (2026, 6, active_run NULL)`; 6 selections (Weeks 0–4 `v5repair-…-p1`, Week 5 `v5repair-20260929-p2`), identical selection hashes in Preview and Production. All six rollback runs present.
- **B2 Week 5 grades (both envs):** 56 predictions, 112 grade rows, spread 28-27-1, total 25-30-1 (matches `docs/status.md`). Grade-row and prediction hashes are identical between Preview and Production. 56 results scored; all 56 games have spread and total lines.
- **B3 registrations:** one `prospective_week_records` row per environment for Week 5 `2026w5-v5repair-20260929-p2`. The receipt filename embeds the same SHA-256 the row stores (Preview `9b3d04f3…`, Production `9f022418…`); `decision_ref` is `contract-04-amendment-4-5-w5-legacy-freeze` in both. I did not re-read the R2 objects in this session (earlier sessions did).
- **B4 schema and grants:** `schema_migrations` has the same 23 entries through 0024 in both. `cks_prod_web` can SELECT `prospective_week_records` and `market_quotes`; `cks_prod_pipeline` can SELECT `ops.v5_release_revocations` and INSERT/SELECT `prospective_week_records`; only `cks_release_authorizer` can INSERT revocations. Both append-only triggers exist. **C5 (new grants migration) is not needed.**
- **B5:** `game_venues` 271/271 with city in both. Production `team_season_stats` weeks 1–5 = 10,460 rows.

## Open Findings
1. **Preview Week 4 rollback run is not scored: explained, document only.** `2026w4-v5replay-bestquote-20260926-r3` has the same artifact hash (`4f1e8436…`) and 58 predictions in both environments. Production scored and graded it on 2026-09-27 (29-27 spread, 18-23 total); Preview left it `published` with 0 grades although all 58 results are present. Neither environment selects it, so serving is unaffected. Bringing Preview in line needs a Preview grade write; not done. Evidence: `pre-week6-audit-evidence/w4-rollback-*.json`.
2. **Preview and Production team stats differ: explained, no defect.** Preview has the 2026-10-02 punt-return fix (extra `ppa_per_play` metric, lower play counts in `conv_rate_3rd_4th`, `explosive_rate`, `turnover_rate`; seven other metrics identical on every row); Production still serves the pre-fix stats published 15:25Z. Both are already documented (known issues #2, punt-fix plan). Production stats are therefore not "current" until the Window 1 production republish. Evidence: `pre-week6-audit-evidence/team-stats-divergence.md`.
3. **Production Week 5 registration provenance.** The row's `decision_ref` references Contract 04 Amendments 4/5, but no session log records who ran the Production registration or when. Needs a user statement to close.
4. `docs/status.md` updated this session with the verified facts above; the Production registration operator remains open.
5. **B6 and B7 completed (read-only).**
   - **B6, 6B root and objects (Preview R2):** root raw SHA-256 `6fb59797…`, signature verifies, internal `manifest_sha256` `32105bbe…`, build and publisher `eca6871`, verify checksum `e462ae05…`, 12 stages, all 112 listed objects re-hash to their listed SHA. Both hashes are correct: `6fb59797…` is the raw bytes (use it in packet refs) and `32105bbe…` is the internal checksum.
   - **B6, Preview catalog:** offsets 271, frames 271, predictions 542, selections 541, grades 541 (one version each), 54 dependency edges, 1,063 catalog versions in all; matches `docs/status.md`.
   - **B6, not done:** I did not re-run the stage `verify`/`publish` operations. `rebuild_6a.py` requires HEAD to equal the build SHA and a clean tree, and writes local staging; HEAD has moved past `eca6871` and the tree is dirty. The 6A (Preview) readback is also not re-done.
   - **B7, Known Issue 6:** exactly 5 selection-versus-grade side disagreements for Week 5 `p2` (spreads 401858245, 401862788, 401864513; totals 401858247, 401862788), identical in Preview and Production; 7 null spread leans and 8 null total leans. Matches the register.
   - **B7, Amendment 5:** the Preview attestation has a null `freeze_pipeline` and carries the required limitation sentence; the Production attestation has a non-null `freeze_pipeline` and no such sentence. Both raw hashes equal the registered ones.
   - **B7, 5A:** the post-hoc change to checks 1-2 is recorded as Amendment 1 in `5a-frozen-definitions.md`, labeled post-hoc, and the report tabulates the variants (strict equality: 0%; frozen-as-clarified: 44.4% against the 25% gate).
   - **Clarification:** local `CFB_R2_BUCKET` and `CFB_R2_PREVIEW_BUCKET` both resolve to `cks-picks-cfb-preview`. Environments are separated by key prefix (`artifacts/preview/…`, `artifacts/production/…`, `…/environment=production/…`), and objects exist under both. So my "Production" attestation read used that shared lake bucket; I did not verify any separate production bucket, and did not look for one.

## Provenance and Waivers
- **Issue-13 wording in `docs/status.md` is a restatement, not a new measurement.** The old "34 wrong-line Away spreads" was 32 (Weeks 0-4) plus 2 (Week 5: `401856819`, `401864513`) from the corrected-verifier sizing in `session_logs/2026-10-04/02-window1-completion.md` (lines 46-62, read-only on Preview R2, 2026-10-04). `docs/data/known_issues.md` #13 later reclassified `401864513` as a legacy null-lean record (edge 0.98 below the 1.0 threshold), leaving 1 genuine Week 5 selection (`401856819`, 0.5 point). The status text now mirrors #13. I did not recompute any of these counts.
- **B6 remainder: waived with reason, not left open.** Not re-run: the stage `verify`/`publish` operations and the 6A readback, because `scripts/pipeline/rebuild_6a.py` requires HEAD to equal the build commit and a clean worktree (neither holds). Changes to the rebuild path since build `eca6871` (17 commits in all; four rebuild-path files): `stages.py` is a line-wrap only (`66c71de8`); `orchestrator.py`, `catalog_publish.py` and `publish_6a.py` changed in `91829432` (parent-first catalog ordering and reuse of an already-written signed root), which is publish-path code, not stage build or verify logic. So the changes are not formatting-only. Substitute evidence: the published root's signature, all 112 object hashes and the catalog counts were re-read on 2026-10-07, and the root still records build and publisher `eca6871`. A full verifier rerun is deferred to a clean worktree at `eca6871` if it is ever required.
- **Push set:** the seven modified files plus `docs/status.md`, and the five new paths (`tests/test_freeze_week_deadline.py`, `web/src/lib/performance-sections.ts`, `web/src/lib/performance-sections.test.ts`, `docs/plans/2026-10-07/pre-week6-audit-evidence/`, this log). `docs/plans/2026-10-07/02-docker-python-ci-parity.md` is a separate Approved plan that I did not create or touch; keep it out of this push and commit by explicit path.

## CI Result on d100d15e (run 37641000610) and Correction
- **Python lint and contracts failed at "Check formatting" (14 seconds); Lint, contracts and registry steps were skipped.** Cause: the eight audit scripts I added under `docs/plans/2026-10-07/pre-week6-audit-evidence/` were not ruff-formatted, and `ruff format --check .` covers the whole repo. My earlier "Ruff clean" statement was made before I added those scripts and checked only changed files for format; that claim was wrong for the pushed tree.
- **Fix (uncommitted):** formatted the eight scripts, applied 14 auto-fixes (import order), and marked the five intentional late imports `# noqa: E402` (the `sys.path` setup must precede them, same pattern as `scripts/pipeline/rebuild_6a.py`). Evidence JSON is unchanged; `checksums.txt` regenerated and verified. No script behavior changed (the three that import project modules compile).
- **Verified locally after the fix:** `ruff format --check .` (669 files), `ruff check .`, `python contracts/validation.py`, `python -m cks_picks_cfb.quality --verify-registry` (29 checks, no problems).
- The Python tests, 6B rebuild flow and Web jobs of that run were still in progress when I checked and are unproven. The next push cancels this run (`cancel-in-progress`).
- **Proposed commit:** `style: format and lint audit evidence scripts`

## CI Result on 0cd0a3c0 (run 37641359773)
- **All four jobs succeeded (about 10m 21s end to end).** Lint and contracts 28s (format, lint, contracts, registry all green); Web 1m54s; Python tests 10m21s; Python 6B rebuild flow 9m52s.
- **Python tests steps:** parallel 1,987 passed, 2 skipped (6m42s); rating publication 7 passed (2m27s, no heartbeat lines in the log against 26 in the stalled run); PostgreSQL integration 23 passed (22s); coverage "Required test coverage of 60.0% reached. Total coverage: 65.96%". The 12 attestation tests that errored before now pass under `fetch-depth: 0` (no errors in the step).
- **6B rebuild flow:** 34 passed in its own job; slowest call 279s plus 170s fixture setup.
- **Vercel Preview:** the PR check for head `0cd0a3c0` is `SUCCESS` ([inspect URL](https://vercel.com/connorkitchings-projects/c-ks-picks-cfb/4QA4B4HxvHmUSDrhUCtvbMV6XJFd)). Not opened; `dpl_` ID not captured; no route verification done.
- The earlier `d100d15e` run (37641000610) failed at the formatting step as recorded above and is superseded. Release-packet update: `docs/plans/2026-10-07/track1-release-packet.md` ("Update after push"). The packet remains HOLD.

## Files Modified
- `.github/workflows/ci.yml`, `Makefile`, `scripts/pipeline/freeze_week.py`, `scripts/pipeline/select_v5_intended_update_batch.py`
- `tests/test_data_first_possession_rating_runner.py`; new `tests/test_freeze_week_deadline.py`
- `web/src/app/performance/page.tsx`, `web/package.json`; new `web/src/lib/performance-sections.ts`, `web/src/lib/performance-sections.test.ts`
- `docs/status.md` (Week 6 row, audit summary, 6B hash labels, issue 13 wording, Stage 7B foundations)
- New `docs/plans/2026-10-07/pre-week6-audit-evidence/*` (22 files incl. checksums), this log

## Validation
- [x] Attestation + rating-runner tests: 19 passed locally. Shallow clone cannot resolve `446c880`; after full fetch (770 commits) it resolves.
- [x] Python suite excluding the three DB-reset files: 2,028 passed, 2 skipped (165s). The DB-reset files and 6B flow were not re-run after these edits (they were not touched; the 6B flow passed in the last CI run's 2,007).
- [x] `ruff check .` clean; changed Python files format-clean.
- [x] Web: lint, typecheck, `test:publication` 139 tests (138 pass, 1 pre-existing skip); Performance Playwright spec 5 passed.
- [x] `git diff --check` clean. CI YAML parses (jobs: lint, pytest, rebuild-flow, web).
- [ ] Exact-SHA CI on PR #2 (needs push).
- [ ] `actionlint` (not installed).
- Confirmed: the 6B flow needs no database (it monkeypatches `psycopg.connect`). No test renders the prospective-error card (Playwright runs in fixture mode); the card shows only a fixed message.

## Handoff Notes
- **Resume at:** user push → watch the three Python jobs; then B6, B7, status.md update.
- **Watch out for:** `cancel-in-progress` cancels the running CI on every push, so push once. `make freeze-week` now needs `DECISION_REF=` for 2026 Week 5+.
- **Proposed commits (user-run):**
  - `ci: fetch full history for pytest and run the 6B rebuild flow as its own job`
  - `fix(ops): record a missed freeze deadline before requiring a decision ref`
  - `fix(web): keep the replay record visible when prospective performance fails`

**tags:** ["ci", "audit", "week6", "freeze", "web", "verification"]
