# Status history

> Dated narrative moved out of `AGENTS.md` and `docs/status.md` on 2026-10-09 so those pages stay current. Text is verbatim except that link targets were rebased to this folder; nothing here is current operating authority. Live state: [`status.md`](status.md).

## Moved from AGENTS.md (2026 Season Execution Status, checkpoints through 2026-10-04)

The detailed checkpoints below are dated historical records. Use the status
above and the latest session log for current-week operations.

**Current focus (2026-10-04):** Step 5 is closed; the [pre-6A integrity and rebuild contract](plans/2026-10-04/02-pre-stage6-integrity-and-rebuild.md) is Approved. Shared-contract repairs and explicit corrected-lineage integration precede the Preview rebuild/refit. Stage 6B replay and Stages 7–8 release remain separately gated. Current serving/week state: [`docs/status.md`](status.md).

**Historical checkpoints (dated, not current):**
- ✅ Data platform modernization (immutable lake, CFBD hardening, resumable ops)
- ✅ Week 0 regime modeling (5 routes × 2 targets, temporal folds)
- ✅ Phase 1–5: Full bootstrap, Silver/Gold, OOF baselines, V4 tournament complete
  (bundle `week0-2026-v4-strict-20260818-r2`, config `conf/weekly_bets/v4_2026.yaml`)
- ✅ Phase 6: Production deployed 2026-08-18; predictions revealed 2026-08-21;
  Week 0 games played Aug 29–30.
- ✅ **Week 0 closed:** `2026w0-55de0317120d` frozen and `scored` (8/8/8).
- ✅ **Week 1 scored:** 43 games and 86 grade rows were verified on 2026-09-10.
- ✅ **Week 2 scored:** `2026w2-43b25511a100` froze on 2026-09-10 (49/49/49,
  no waiver) and closed 2026-09-13 after a 49/49 finals gate: 90 grade rows
  (49 spread + 41 total; 8 sub-threshold totals are No-Bet/ungraded by design);
  YTD spread 37-62-1, total 40-52-0. Follow the current weekly runbooks for
  later-week procedures.
- 🧭 **Week 3 prepared:** cumulative Gold `point_in_time_matchups`
  `d184186ddfbc7c40657f0714` (preview pipeline-run
  `285684cc44af4e5b95943d4c5f40d4b3`), readiness-green 2026-09-13 after a
  Preview-only catalog quarantine of 2025-replay market versions
  (`e4061aab…`, `32db239e…`, `dfc36725…`) plus phantom-row cleanup
  (`db61a68d…`); earliest kickoff Thu 2026-09-17 23:30Z. Week 3 published
  same day: run `2026w3-68fe6a815bd6` activated 57/57/56 (Houston @ Texas
  Tech total not yet posted); progressive republish Mon-Wed, then freeze
  before kickoff. The v4 feature
  chain is intentionally unchanged. The old rebuild is a superseded root-cause
  record; the independent feature-v5 diagnostic resumes under
  `docs/plans/2026-09-13/01-v4-feature-v5-diagnostic-closure.md`.
- 🧭 **Historical ratings evidence:** R1 is certified at
  `r1-full-corpus-20260831-5f2a384`; its immutable coverage report has
  `tournaments_permitted: true`. The fresh, code-bound Preview admission at
  `early-week-context-20260904-786580ec-r2` admits reconstructed returning
  production, recruiting, and coaching; transfers and talent remain rejected.
  The direct selection report and R2 between-season tournament remain historical
  reconstructed evidence. Corrected Phase 1 audit v3 classifies the R2 result as
  unsupported for the data-first program, so its prior winner cannot enter
  Phase 4 without renewed evidence. The pending R3/R4 sequence is superseded;
  **Corrective checkpoint 2026-09-08:** completed Phase 3/4 engineering does
  not establish current predictive eligibility. The review found 32 completed
  schedule games omitted from Phase 3, same-game context leakage in Phase 4B,
  constant coaching features, and incorrect roster continuity. The original
  Phase 4B retained manifest is prohibited as a new forecasting parent. Repair
  v2 is independently verified; Phase 3 v2 is certified in Preview under
  `docs/plans/2026-09-10/phase3-v2-compact-tournament-state.md` (run
  `phase3-v2-compact-state-20260910-r2`, selection `quality_core_epa_split`,
  independently verified and idempotently rerun on 2026-09-11).
  It is benchmark evidence. **V5 checkpoint (2026-09-22):** the historical lane
  is complete and accepted. All four 10B blockers are closed on the corrected
  lineage — Repair v2 (verifier v3), measurements
  `possession-v1-measurements-20260921-r9` (superseding the R6
  `possession-v1-measurements-20260915-18fb0aa-r6` historical evidence), ratings
  `possession-v1-ratings-20260921-11d59ee-r9cert` (no selection flip:
  `ppp__rho_0_60__exposure`), forecast bridge
  `forecast-v1-20260921-5afd577-11c` with through-2025 final fit (11D verifier
  `4cfe5ef8…`). Contract 12 issued
  `accepted_for_prospective_evaluation` (`readiness-v1-20260921-scorecard`)
  and the user explicitly accepted it on 2026-09-22. Contracts 07–09 are
  re-reviewed against the corrected parents with deferrals lifted under the
  archived September 22 acceptance and re-review record.
  Contract 08 was Implemented for Weeks 0–3 as independently verified replay
  `possession-v1-rating-replay-20260922-fcaa571`; the Week 4 07/08 refresh
  and Week 5 live forecast were verified on 2026-09-27.
  [V5 model development is complete and accepted](modeling/v5_status.md).
  The Week 5 candidate was authorized and published in production (`session_logs/2026-09-27/06.md`).
  Contract 06
  continues prospective monitoring; six slates are not a prelaunch condition.
  Conditional results remain `conditional_historical_results_only`.
  V4 feature-schema-v5 diagnostic (contract 01) closed 2026-09-22: cause not
  confirmed (pooled W1+W2 shadow spread 38.46% < 45%), predictions
  value-identical on all 100 games. V5 ratings successor is distinct from V4
  feature schema v5. September 8 Phase 4A–6
  contracts are Superseded by the V5 package; only explicitly inherited mathematics
  carry forward. The first release uses a rating-to-margin/total Ridge bridge;
  possession arithmetic is a later challenger. Polls/direct models and O2
  candidate-v1 at `ac1fba1` are diagnostic-only. See the canonical
  [data-first roadmap](planning/data-first-football-forecasting-roadmap.md).

## Moved from docs/status.md (2026-10-09)

Verbatim lines, with their former `status.md` line numbers. These items were closed, duplicated elsewhere in `status.md`, or superseded by its Open work list.

<!-- status.md line 3 -->
> **Repair-track verification update (2026-10-08):** The [completion matrix](plans/2026-10-08/02-repair-track-certification-and-closure.md) now records independent c2/B2 readback, baseline CI and deployed revision. These checks do not establish corrected Production activation or full track closure. Serving/week state below is unchanged.

<!-- status.md line 71 -->
- Week 5: **Closed and scored 2026-10-04** (certified finals verified in CFBD, scored via `score_to_db.py`, and graded via `backfill_v5_unconstrained_grades.py --week 5 --grades-only` on Preview and Production; 56 spread and 56 total grades, 112 total).

<!-- status.md line 73 -->
- Approved, in progress: [authentic team stats pipeline](plans/2026-10-01/10-authentic-team-stats-pipeline.md). **Code released to `main` (`53d346b`); data live on Preview and production** as of 2026-10-02 (Silver promoted, migrations 0019/0020 applied, team stats weeks 1-5 = 10,460 rows, venues = 271), run by the user and verified read-only; checked against CFBD (Amendment 1). Matchup pages are now default-on; the former enablement step is superseded. Reconcile remaining completion against contract 04 and re-run team stats through the approved weekly path.

<!-- status.md line 76 -->
- Done 2026-10-01: [dead-code prune](plans/2026-10-01/05-dead-code-prune.md) and [docs cleanup/archive](plans/2026-10-01/06-docs-cleanup-and-archive.md) (Implemented).

<!-- status.md line 77 -->
- Approved, in progress: [matchup data layer v2](plans/2026-10-02/01-matchup-data-layer-v2.md): everything the V5 ratings use per team per week (raw V5 metrics shown on matchups, separate adjusted values, per-game log, rating decomposition), bound to the served rating manifest. **Phase A (2026) is live on Preview and production** (user-run 2026-10-02): migration 0021, the four data tables published with Preview's payload hash `a4a1062d…71215` and verified read-only (0 rows differing, 11 gates ok), and the Silver stats republished with the V5 play filter. Web code reading the new tables is released to `main`; the former enablement step is superseded by default-on matchups. Remaining corrected repinning and Phase B (2025) belong to contract 04 Stage 8.

<!-- status.md line 78 -->
- **Window 1 progress (2026-10-04; code released to `main` at `0cd0a3c0` on 2026-10-07, see Release state):** selection/tie/null-lean/frozen-grading fixes, `ppa_missing` masking, the accuracy-only Performance page and the pinned venue publisher are committed (`850ca38`, `562b2b2`); Playwright 28/28 and the full Python suite pass. Preview `game_venues` is 271/271 with city (user-run, verified 2026-10-04). The Week 1 Preview serving rehearsal passed with public state unchanged, and the user closed Window 1 for implementation on 2026-10-04 (receipt: `session_logs/2026-10-04/02-window1-completion.md`); the code was later released to `main` (Track 1, 2026-10-07). The Production venue upsert was skipped by decision: Production already holds all 271 venues with cities and the business diff is empty. The corrected verifier shows wrong-line Away spreads in the served Weeks 0-5 artifacts (known issue 13: 32 diverging-book games in Weeks 0-4; Week 5 is 1 genuine selection plus 1 null-lean record); they are replayed in Window 2, and frozen Week 5 is unchanged. The data-quality gates contract ([plans/2026-10-04](plans/2026-10-04/01-pipeline-data-quality-gates.md)) has Tasks 1-6 delivered on `dev` (check library, ingest, Silver and publish-boundary checks, web row guards, CI registry check, [checks catalog](data/data_quality_checks.md)); it is Implemented (2026-10-04) with six follow-ups tracked in its Amendment 3 (ingest input wiring, unpinned-dataset review, Gold checks and build-script receipts, promotion of checks to `block`, R2 receipt copy, `utils/validation.py` decision). **Window 2 step 5A (2026-10-04):** full baseline reproduction done; historical sizing found 3,193 changed scoring-allocation groups in 2,324 of 8,936 games; the CFBD corroboration gate **passes at 44.4%** (25% needed), carried by attribution-only groups (points-recovery groups are 1.9% corroborated); report and caveats in [5a-sizing-report](plans/2026-10-03/window2/5a-sizing-report.md); closed by the user (not a signed release receipt). **Step 5B (2026-10-04):** shared data contracts built and tested locally (metric registry, four Gold dataset contracts, `team_game_metrics` builder, nullable PPA opt-in, null-aware ledger consumers, stream-score reconciliation resolving issue 7, served-PPP isolation tests); full suite 1814 passed; no dataset built or published; draft receipt [5b-receipt](plans/2026-10-03/window2/5b-receipt.md) closed with Step 5. **Step 5C (2026-10-04, local dry run, no external writes):** 1,416 corroborated groups admitted, 28 contradicted and 1,749 unverified groups reverted to baseline; the independent verifier passes on the full corpus; raw PPP changes by more than 0.05 for 399 of 1,310 full-season team-seasons ([5c-receipt](plans/2026-10-03/window2/5c-receipt.md)). **Step 5 is closed (2026-10-04; `f7c3a47`, `e33d63d`, `ea53c07`).** The [pre-6A integrity and rebuild contract](plans/2026-10-04/02-pre-stage6-integrity-and-rebuild.md) is **Approved**: repair missing-source/null-opportunity handling, season isolation and retained-baseline admission semantics before integrating corrected measurements, priors and offsets. Task 1 semantic repairs are implemented on `dev` and passing tests; Tasks 1–3 are done: the manifest-driven rebuild (eleven stages, committed run at `1724c51`) passed full verification and was published to Preview R2 and the Preview catalog on 2026-10-05 (49 dataset versions, independent readback clean, identical retry wrote nothing; [contract Amendment 7](plans/2026-10-04/02-pre-stage6-integrity-and-rebuild.md)). Task 4 is also done and published to Preview R2 on 2026-10-05 (run `6a-task4-r1`: attribution deltas, read-only comparison with the published statistics, signed receipt checksum `efcedf3e…9d15e`; [Amendment 9](plans/2026-10-04/02-pre-stage6-integrity-and-rebuild.md)); **the corrected foundation is Preview-only evidence and is not certified for serving or production**. 6A permits immutable Preview R2 and verified Preview catalog/schema/lineage/reconciliation metadata writes; serving and production writes are excluded. **Stage 6B (completed-week reconstruction, Weeks 0-5)** is **Implemented** ([2026-10-05/01](plans/2026-10-05/01-stage6b-completed-week-reconstruction.md)): all 12 stages independently verified on build `eca6871`; signed receipt `7441d7a6…` published to Preview R2 (`rebuild/6b/6b-replay-20261005-r1`; root raw-byte SHA-256 `6fb59797…`, internal checksum `32105bbe…`; re-read 2026-10-07: signature valid, all 112 objects re-hash) and five reconstruction Gold datasets registered in Preview catalog (271 offsets, 271 frames, 542 predictions, 541 selections, 541 grades); zero-write idempotence retry proven; Preview-only evidence; no serving, selection, authorization, or production writes occurred. Stage 7B remains a separate gate.

<!-- status.md line 79 -->
- **Data-integrity planning (2026-10-04):** [contract 04](plans/2026-10-03/04-data-integrity-two-window-implementation.md) retains independent Window 1 delivery; implementation is closed and its production decision remains open. Step 5 is closed. Amendment 3 and the approved pre-6A contract now govern the repair prerequisites and rebuild. Window 2 evaluates full R1 with per-allocation evidence admission, rebuilds the full historical corpus under the unchanged model design, and fixes cutover N only when the certified release packet is ready. No live selections or scoreboard values change in this documentation session.

<!-- status.md line 83 -->
- Matchup Share button (released to `main` with the default-on matchup page): exports a fixed 1080x1350 card per matchup (`ShareCard`/`ShareButton`); e2e covers the export size and canvas fit.

<!-- status.md line 84 -->
- Team stats punt-leak fix ([plan](plans/2026-10-02/03-team-stats-feeds-ratings.md)): code released to `main`, Preview republished 2026-10-02. Production was republished with the fix on 2026-10-07 17:05:40Z (as-of weeks 1-5, user-run; see Release state and [evidence](plans/2026-10-07/team-stats-republish/summary.md)). Matchup pages remain default-on with stale-data limitations tracked in [known issues](data/known_issues.md). V5 per-play companion repairs and the shared metric source belong to Window 2; the accepted served rating path is PPP-only.

<!-- status.md line 85 -->
- Approved: [game venue location](plans/2026-10-01/08-game-venue-location.md): venue data live in production (271 games); the city/state UI now renders on the real Picks/Results cards (prototype port released).

<!-- status.md line 86 -->
- V6 ratings lab: closed 2026-09-30 (`RETAINED_AS_BENCHMARK`); research only.

<!-- status.md line 94 -->
- **Track 1 (2026-10-07): promoted.** `main` was fast-forwarded from `562319aa` to `0cd0a3c0` (the commit that passed CI run `37641359773`; PR #2 merged) and Production deployment `dpl_25cfxMwDLqXRkphiPQCvT9Db18sY` is Ready. See [release packet](plans/2026-10-07/track1-release-packet.md) and [recapture evidence](plans/2026-10-07/track1-recapture-0cd0a3c0/summary.md).
