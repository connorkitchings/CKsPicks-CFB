# Current Status

> **Single source of truth for live run IDs, week state and the scoreboard.**
> Other docs link here instead of naming runs. Update this page (and only this
> page) when a week opens, freezes, closes, or a release changes the selected run.
>
> **Last updated:** 2026-10-05 · **Verified from:**
> `session_logs/2026-09-30/01-verify-deploy-freeze-week5-close-contract.md`,
> the Step 5 close-out and pre-6A planning records (2026-10-04; no new cloud-state verification), and the [repaired-V5 release packet](plans/2026-09-29/v5-intended-update-production-release-packet.md).

## Product and model

- **Product:** public Vercel site showing every FBS game's spread and total lean
  vs the market. Display-only; staking and wagering are deferred
  ([betting policy](modeling/betting_policy.md)).
- **Serving model family:** V5 possession ratings + Ridge bridge, repaired
  "intended-update" release (2026-09-30). Model development is complete and
  accepted ([V5 status](modeling/v5_status.md)).
- **Rollback:** V4 ten-route bundle `week0-2026-v4-strict-20260818-r2`
  (frozen V4 runs) and the prior V5 best-quote replay runs.
- **V6 ratings lab:** closed 2026-09-30, `RETAINED_AS_BENCHMARK`; does not
  affect production.

## Week state (2026 season)

| Week | State | Selected run |
|---|---|---|
| 0–4 | Scored; **retrospective replay** (not prospective evidence) | `2026w{0..4}-v5repair-20260929-p1` |
| 5 | **Scored** 2026-10-04, 56/56/56, 112 grades (56 spread, 56 total). First live V5 slate. | `2026w5-v5repair-20260929-p2` |
| 6 | Not opened | — |

**Rollback set (exact):** `2026w{0..4}-v5replay-bestquote-20260926-r3` and
`2026w5-5d436e58c072`. An earlier Week 5 run, `2026w5-d6366e59fd43`, is
superseded and kept only as an audit record.

## Scoreboard

**Primary success metric:** prospective ATS win % vs the 52.4% break-even at
-110, reported separately for spreads and totals. MAE, calibration and the
pre-registered promotion gates remain diagnostics.

| Evidence class | Spread | Total | Notes |
|---|---|---|---|
| **Prospective (frozen before kickoff)** | 28-27-1 (50.9%) | 25-30-1 (45.5%) | Week 5 is the first live V5 slate (55 decided spreads, 55 decided totals; 1 push each) |
| Retrospective replay, Weeks 0–4 | 100-112-3 (47.2%) | 112-102-0 (52.3%) | Not prospective evidence (unconstrained; 212 decided spreads, 214 decided totals; 1 unlined W3 total) |

Neither target clears 52.4% YTD. In the 2025 holdout the market had
lower error than V5 on both targets, and the docs do not claim V5 beats V4.

## Branches

`main` is production (Vercel deploys from it); `dev` is the working branch. Work on `dev`, then merge `dev` into `main` to release. No other long-lived branches. Details: `AGENTS.md` (Branching).

## Release state

`main` was fast-forwarded to `dev` at the 2026-10-02 close-out (previous release `53d346b`). That release carries the Picks/Results prototype port (city/state and sportsbook-behind-the-line on the production slate cards; rank badges stay off the cards by design; the `/test-picks` and `/test-results` routes are removed), the unconstrained-grading pipeline changes, the team-stats punt fix (code), and the matchup refinements including the Share card. Matchup pages are default-on; `CFB_MATCHUP_ENABLED=0` is the emergency opt-out. Their remaining data-integrity work is governed by the two-window contract below. CI's browser suite now runs with `CFB_PUBLICATION_MODE=predictions` set by `web/playwright.config.ts` (see `web/README.md`). **Picks/Results card redesign (complete, released 2026-10-02):** the bet-cell cards ("Best bets" panel, team filter, grid/list toggle) replace the old slate cards. Closing it out fixed two regressions the browser suite caught (Results cards had lost their Matchup button; the Best-bets columns overflowed a 390px phone) and updated the e2e tests to the new controls and card text; the suite is 43/43.

## In flight

- Week 5: **Closed and scored 2026-10-04** (certified finals verified in CFBD, scored via `score_to_db.py`, and graded via `backfill_v5_unconstrained_grades.py --week 5 --grades-only` on Preview and Production; 56 spread and 56 total grades, 112 total).
- Week 6: Not opened in the recorded state. This is not a rebuild hold: weekly operation continues under existing exact decisions, and cutover N is fixed only when the certified release packet is ready.
- Approved, in progress: [authentic team stats pipeline](plans/2026-10-01/10-authentic-team-stats-pipeline.md). **Code released to `main` (`53d346b`); data live on Preview and production** as of 2026-10-02 (Silver promoted, migrations 0019/0020 applied, team stats weeks 1-5 = 10,460 rows, venues = 271), run by the user and verified read-only; checked against CFBD (Amendment 1). Matchup pages are now default-on; the former enablement step is superseded. Reconcile remaining completion against contract 04 and re-run team stats through the approved weekly path.
- Draft contract: production-boundary refactor
  (`plans/2026-10-01/04-production-boundary-refactor.md`).
- Done 2026-10-01: [dead-code prune](plans/2026-10-01/05-dead-code-prune.md) and [docs cleanup/archive](plans/2026-10-01/06-docs-cleanup-and-archive.md) (Implemented).
- Approved, in progress: [matchup data layer v2](plans/2026-10-02/01-matchup-data-layer-v2.md): everything the V5 ratings use per team per week (raw V5 metrics shown on matchups, separate adjusted values, per-game log, rating decomposition), bound to the served rating manifest. **Phase A (2026) is live on Preview and production** (user-run 2026-10-02): migration 0021, the four data tables published with Preview's payload hash `a4a1062d…71215` and verified read-only (0 rows differing, 11 gates ok), and the Silver stats republished with the V5 play filter. Web code reading the new tables is released to `main`; the former enablement step is superseded by default-on matchups. Remaining corrected repinning and Phase B (2025) belong to contract 04 Stage 8.
- **Window 1 progress (2026-10-04, on `dev`; not yet released to `main`):** selection/tie/null-lean/frozen-grading fixes, `ppa_missing` masking, the accuracy-only Performance page and the pinned venue publisher are committed (`850ca38`, `562b2b2`); Playwright 28/28 and the full Python suite pass. Preview `game_venues` is 271/271 with city (user-run, verified 2026-10-04). The Week 1 Preview serving rehearsal passed with public state unchanged, and the user closed Window 1 for implementation on 2026-10-04 (receipt: `session_logs/2026-10-04/02-window1-completion.md`); the production release decision is open and production venues are not yet published. The corrected verifier shows 34 wrong-line Away spreads in the served Weeks 0-5 artifacts (known issue 13); they are replayed in Window 2, and frozen Week 5 is unchanged. The data-quality gates contract ([plans/2026-10-04](plans/2026-10-04/01-pipeline-data-quality-gates.md)) has Tasks 1-6 delivered on `dev` (check library, ingest, Silver and publish-boundary checks, web row guards, CI registry check, [checks catalog](data/data_quality_checks.md)); it is Implemented (2026-10-04) with six follow-ups tracked in its Amendment 3 (ingest input wiring, unpinned-dataset review, Gold checks and build-script receipts, promotion of checks to `block`, R2 receipt copy, `utils/validation.py` decision). **Window 2 step 5A (2026-10-04):** full baseline reproduction done; historical sizing found 3,193 changed scoring-allocation groups in 2,324 of 8,936 games; the CFBD corroboration gate **passes at 44.4%** (25% needed), carried by attribution-only groups (points-recovery groups are 1.9% corroborated); report and caveats in [5a-sizing-report](plans/2026-10-03/window2/5a-sizing-report.md); closed by the user (not a signed release receipt). **Step 5B (2026-10-04):** shared data contracts built and tested locally (metric registry, four Gold dataset contracts, `team_game_metrics` builder, nullable PPA opt-in, null-aware ledger consumers, stream-score reconciliation resolving issue 7, served-PPP isolation tests); full suite 1814 passed; no dataset built or published; draft receipt [5b-receipt](plans/2026-10-03/window2/5b-receipt.md) closed with Step 5. **Step 5C (2026-10-04, local dry run, no external writes):** 1,416 corroborated groups admitted, 28 contradicted and 1,749 unverified groups reverted to baseline; the independent verifier passes on the full corpus; raw PPP changes by more than 0.05 for 399 of 1,310 full-season team-seasons ([5c-receipt](plans/2026-10-03/window2/5c-receipt.md)). **Step 5 is closed (2026-10-04; `f7c3a47`, `e33d63d`, `ea53c07`).** The [pre-6A integrity and rebuild contract](plans/2026-10-04/02-pre-stage6-integrity-and-rebuild.md) is **Approved**: repair missing-source/null-opportunity handling, season isolation and retained-baseline admission semantics before integrating corrected measurements, priors and offsets. Task 1 semantic repairs are implemented on `dev` and passing tests; Tasks 1–3 are done: the manifest-driven rebuild (eleven stages, committed run at `1724c51`) passed full verification and was published to Preview R2 and the Preview catalog on 2026-10-05 (49 dataset versions, independent readback clean, identical retry wrote nothing; [contract Amendment 7](plans/2026-10-04/02-pre-stage6-integrity-and-rebuild.md)). Task 4 is also done and published to Preview R2 on 2026-10-05 (run `6a-task4-r1`: attribution deltas, read-only comparison with the published statistics, signed receipt checksum `efcedf3e…9d15e`; [Amendment 9](plans/2026-10-04/02-pre-stage6-integrity-and-rebuild.md)); **the corrected foundation is Preview-only evidence and is not certified for serving or production**. 6A permits immutable Preview R2 and verified Preview catalog/schema/lineage/reconciliation metadata writes; serving and production writes are excluded.
- **Data-integrity planning (2026-10-04):** [contract 04](plans/2026-10-03/04-data-integrity-two-window-implementation.md) retains independent Window 1 delivery; implementation is closed and its production decision remains open. Step 5 is closed. Amendment 3 and the approved pre-6A contract now govern the repair prerequisites and rebuild. Window 2 evaluates full R1 with per-allocation evidence admission, rebuilds the full historical corpus under the unchanged model design, and fixes cutover N only when the certified release packet is ready. No live selections or scoreboard values change in this documentation session.
- Open data issue: the play-by-play running score is non-monotonic for about a third of team-games, which blanks some points-per-scoring-opportunity values; documented in [known data issues](data/known_issues.md). Step 5 admitted corroborated historical changes only; residual baseline errors remain, and the corrected durable rebuild is pending.
- Matchup Share button (released to `main` with the default-on matchup page): exports a fixed 1080x1350 card per matchup (`ShareCard`/`ShareButton`); e2e covers the export size and canvas fit.
- Team stats punt-leak fix ([plan](plans/2026-10-02/03-team-stats-feeds-ratings.md)): code released to `main`, Preview republished 2026-10-02. Production repair is governed by independent Window 1 of [contract 04](plans/2026-10-03/04-data-integrity-two-window-implementation.md); local changes do not establish a completed production republish. Matchup pages remain default-on with stale-data limitations tracked in [known issues](data/known_issues.md). V5 per-play companion repairs and the shared metric source belong to Window 2; the accepted served rating path is PPP-only.
- Approved: [game venue location](plans/2026-10-01/08-game-venue-location.md): venue data live in production (271 games); the city/state UI now renders on the real Picks/Results cards (prototype port released).
- V6 ratings lab: closed 2026-09-30 (`RETAINED_AS_BENCHMARK`); research only.

## Where to look next

- [V5 status](modeling/v5_status.md) · [Weekly operator](ops/v5_weekly_operator.md)
  · [Weekly pipeline](ops/weekly_pipeline.md) · [Production runbook](ops/production_runbook.md)
  · [Implementation contracts](plans/index.md)
