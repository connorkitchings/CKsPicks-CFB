# Implementation Contracts

`docs/plans/` holds task-level implementation contracts prepared by Sol and executed by a fresh Terra task. It is distinct from `docs/planning/`, which holds strategic roadmaps and long-lived initiatives.

## Location and naming

Store each contract at:

```text
docs/plans/YYYY-MM-DD/<descriptive-slug>.md
```

The date folder is the chronological ordering. Prefix a same-day filename with `01-`, `02-`, and so on only when implementation order matters.

Copy the template from `.agent/skills/plan-session/assets/implementation-contract-template.md`. A contract records status, approval source, implementation log, and commit policy as well as the goal, current state, tasks, validation, risks, definition of done, and amendments.

## Lifecycle

| Status | Meaning |
| --- | --- |
| `Draft` | Sol is investigating or the user has not approved the contract. |
| `Approved` | The contract is ready for Terra, either by recorded approval or an explicit user handoff for the exact path. |
| `In Progress` | Terra is implementing the contract. |
| `Implemented` | All definition-of-done items and required validation have passed. |
| `Superseded` | A later contract replaces this one. |

Terra must not execute a Draft contract without an explicit user instruction naming that exact path. In that case, Terra records the instruction as the approval source and changes the status to `Approved` before code changes.

## Current active contracts

The [V6 ratings research platform](2026-09-28/v6-ratings-research-platform.md)
is Closed (2026-09-30, `RETAINED_AS_BENCHMARK`); see
[Phase 5](2026-09-30/07-v6-phase5-finishing-drives.md). It built isolated research
data, rating replay, and historical comparison without changing V5 production.

**Operational snapshot:** see [Current Status](../status.md) for selected runs and week state. Historical contract lifecycle metadata below is retained as recorded.

The former 07/08 checkpoint said “Week 4 refresh awaits stabilized finals”; that gate was satisfied on 2026-09-27. Six slates are not a launch prerequisite for prospective V5 activation; they remain a monitoring window.

The [V5 Product Transformation](2026-09-23/01-v5-product-transformation.md) is the approved implementation contract for the V5-only site and operating path. It supersedes the narrower [V4-to-V5 site transition draft](2026-09-22/05-v4-to-v5-site-transition.md) where their release or public-history policies differ. The older contract remains as an audit record.

The [V5 replay and Preview rehearsal](2026-09-24/01-v5-replay-preview-rehearsal.md) is Implemented under the product transformation. It covered clean-code replay publication, Preview scoring and serving, and same-week V4 rollback with V5 restoration. It does not authorize the current-slate or production cutover.

The [V5 weekly operator and exact release gates](2026-09-24/02-v5-weekly-operator-and-release-gates.md) contract is Implemented (2026-09-25) under its approved production-role amendment: the exact dual-identity guard, Keychain production wrapper, restricted `cks_prod_pipeline` role, and production migration 0014 are verified, and a fixture-class Preview operator rehearsal exercised the full controller. Subsequent exact replay authorizations selected V5 history; the separately authorized Week 5 live run is now selected.

The [Week 4 finals to live Preview evidence](2026-09-25/01-v5-week4-finals-to-live-preview.md) plan is Implemented (user handoff 2026-09-25; closed out 2026-10-01). The Week 4 finals gate, 07/08 refresh, and verified Week 5 forecast and Preview candidate were completed on 2026-09-27. The separate Week 5 release record (`session_logs/2026-09-27/06.md`) documents the subsequent prospective production decision and activation.

The [complete Week 4 replay site cutover](2026-09-25/02-v5-week4-replay-site-cutover.md) was Approved (2026-09-25) and executed to show V5 for all 2026 Weeks 0–4, including truthfully labeled retrospective history. Week 4 was later scored after certified finals. It used separate exact replay authorizations and did not create a prospective V5 Week 4 run or authorize Week 5 live activation.

The [V5 current status guide](../modeling/v5_status.md) is the entry point for the accepted model, exact lineage, historical results, and remaining operational work. V5 replay serves the public site; V4 remains the tested rollback.

| Current contract | Purpose | State |
| --- | --- | --- |
| [V5 ratings publication and navigation](2026-09-26/03-v5-ratings-publication-and-navigation.md) | Publish verified ratings to production Neon, enable /ratings nav, link game cards, and document weekly cadence | Implemented |
| [Ratings lifecycle integration](2026-09-27/04-ratings-lifecycle-integration.md) | Enforce rating currency in prepare-week, require rating manifest on V5 prediction runs, and formalize pipeline ops | Implemented; migration 0017 applied to Preview and production on 2026-09-27 |
| [V5 authority and cutover](2026-09-22/04-v5-authority-simplification-and-site-cutover.md) | Simplify authority and prepare a verified Preview serving rehearsal and rollback | Implemented (closed out 2026-10-01) |
| [07: 2026 measurements](2026-09-18/07-v5-2026-repair-and-measurement-extension.md) | Repair and certify current 2026 football data | Week 4 refresh independently verified (215 games) |
| [08: 2026 ratings](2026-09-18/08-v5-2026-rating-state-replay.md) | Replay the fixed V5 rating design on 2026 games | Week 4 refresh independently verified (860 rating states) |
| [09: live forecast](2026-09-18/09-v5-2026-forecast-and-readiness.md) | Apply and independently verify the fixed forecast to the next slate | Week 5 forecast verified; candidate published in Preview and then production |
| [06: prospective monitoring](2026-09-13/06-v5-prospective-evidence-and-recommendation.md) | Preserve pre-kickoff attempts, outcome reports, and quote diagnostics | Week 5 frozen 2026-09-30; outcome report follows certified finals |
| [Weekly ratings history replay](2026-09-27/05-weekly-ratings-history-replay.md) | Replay the frozen rating design at post-Week 0/1/2 cutoffs, project three generations, serve week-labeled tabs | Implemented 2026-09-28; six week tabs live and verified |
| [2026 V5 intended-update production repair](2026-09-29/v5-intended-update-2026-production-repair.md) | Versioned V5 successor with the intended one-game-one-observation update: repaired history and refit bridge, 2026 rating generations, replacement W0–4 predictions/scores, prospective next-slate forecast, atomic selection with rollback | Implemented (2026-09-30); Week 5 `p2` frozen |
| [Performance dashboard](2026-10-01/01-performance-dashboard-enhancements.md) | Interactive performance page (units, graded game log) | Implemented |
| [Authentic team stats pipeline](2026-10-01/10-authentic-team-stats-pipeline.md) | Play-by-play team stats in Neon for the default-on matchup page; supersedes the former 02 draft | Approved (code on `dev`; data live on Preview and production; released 2026-10-02) |
| [Matchup data layer v2](2026-10-02/01-matchup-data-layer-v2.md) | Everything the V5 ratings use per team per week: raw V5 metrics, separate adjusted values, game log, rating decomposition; one lineage-agnostic publisher | Approved (Task 0 done; Phase A is 2026, then 2025) |
| [Dead-code prune](2026-10-01/05-dead-code-prune.md) | Remove modules, configs, web leftovers and `research/` with no references | Implemented |
| [Docs cleanup and archive](2026-10-01/06-docs-cleanup-and-archive.md) | Close out stale contracts, archive August logs, delete legacy files, fix links | Implemented |
| [Game venue location](2026-10-01/08-game-venue-location.md) | Show city/state next to kickoff; new `game_venues` table + publish script | Approved (UI done; data live on Preview and production; released 2026-10-02) |
| [High-quality team logos](2026-10-01/07-high-quality-team-logos.md) | Replace the 32 px logos with self-hosted, id-keyed, theme-aware WebP | Implemented 2026-10-01 (fetched on the user's machine; legacy files removed) |
| [Production boundary refactor](2026-10-01/04-production-boundary-refactor.md) | Move production V5 logic from `scripts/research` into `src/` | Draft |
| [Team stats as the source of basic stats](2026-10-02/03-team-stats-feeds-ratings.md) | Fix the returned-punt leak in team stats (Phase 1, done); ratings read team stats at the next rebuild (Phase 2 design, absorbed as D4 in the unified rollout) | Draft (Phase 1 implemented) |
| [Port picks/results prototypes to production](2026-10-02/02-port-picks-results-prototypes.md) | Replace `/` and `/results` slate UI with the proven prototype lean-sentence design; delete `/test-*` routes and the old stack | Implemented (released to `main` 2026-10-02) |
| [Remove edge constraints and grade all games](2026-10-02/04-remove-edge-constraints-grade-all-games.md) | Set thresholds to 0.0, re-score Weeks 0–4 in Neon, update system_stats, and grade all games based on model vs market | Implemented |
| [Data issues: review and rerun together](2026-10-02/05-data-issues-review-and-rerun.md) | One workflow for the open data issues (play-by-play score stream, V5 punt companions, zero-PPA plays): investigate read-only, decide once, rerun Preview then production together | Superseded 2026-10-03 by the unified rollout below |
| [Unified data fix and matchup rollout](2026-10-03/01-unified-data-fix-and-matchup-rollout.md) | Historical read-only investigation and original one-batch proposal | Superseded by contract 04 |
| [Week 5 data-issue investigation](2026-10-03/02-week5-data-issue-investigation.md) | Read-only deep dive producing decision-ready evidence for D1–D4: score-stream cause classification, V5 `ppp` quarantine simulation, drive-metric hand-checks, zero-PPA audit, venue-gap root cause | Approved (investigation only; no writes) |
| [Data integrity decision packet](2026-10-03/03-data-decision-packet.md) | Reviewed evidence register and recorded D1-D9 decisions from the read-only investigation | Evidence packet; execution authority is contract 04 |
| [Data integrity repair in two windows](2026-10-03/04-data-integrity-two-window-implementation.md) | Window 1 independent fixes; Window 2 full-corpus scoring certification, unchanged-design rebuild, replay and prospective cutover ([data specification](2026-10-03/window2/data-contracts-and-certification.md), [release/schema/web specification](2026-10-03/window2/release-schema-and-web.md)) | Window 1 implementation closed; production decision open. Step 5 closed; 6A (pre-Stage-6 contract 02) Implemented 2026-10-05, Preview-only; 6B scoped in the 2026-10-05 execution contract; Stages 7-8 not started |
| [Pre-Stage-6 integrity and rebuild](2026-10-04/02-pre-stage6-integrity-and-rebuild.md) | Repair shared-contract gaps, integrate corrected lineage, rebuild/refit and certify in Preview under contract 04 | Implemented (2026-10-05); Preview-only evidence, 6B separate |
| [Stage 6B completed-week reconstruction](2026-10-05/01-stage6b-completed-week-reconstruction.md) | Rebuild forecasts, original-quote selection and retrospective grades for 2026 Weeks 0-5 on the corrected 6A foundation, as new immutable Preview artifacts | Draft (awaiting user review) |
| [Pipeline data-quality gates](2026-10-04/01-pipeline-data-quality-gates.md) | Shared check/receipt library with ingestion, Silver/Gold, publish-boundary and web read-side gates, plus contract 04 gates 2, 4 and 6 | Implemented 2026-10-04 (six follow-ups tracked in Amendment 3) |

The [V5 contract archive](../archive/v5-contracts/index.md) preserves completed and superseded methodology, audit, diagnostic, and code-readiness records. Historical contract statuses describe what happened at the time; the current guide and cutover contract govern what happens next. The unrelated V4 feature schema v5 diagnostic is archived with those records and is not the V5 ratings successor.

### Other active work

The [data-first roadmap](../planning/data-first-football-forecasting-roadmap.md) retains the broader research context. The [production runbook](../ops/production_runbook.md) retains V4 rollback procedures; the [V5 weekly operator](../ops/v5_weekly_operator.md) governs current V5 stages and exact release gates. The [local artifact archive](2026-09-27/03-archive-unique-local-artifacts.md) remains In Progress while Preview R2 lifecycle proof is unavailable; all 11 backups were byte-verified and no local candidate was pruned.

**Numbering notes:** `2026-10-01/` has no `09` (the former `02` matchup-stats draft became `10`) and `2026-09-30/` has no `04`; neither was renamed, to keep links stable. On 2026-10-01 twenty contracts from August–September that were still `In Progress`, `Approved` or `Draft` were closed out; each file's status line records its prior status.

## When to use a contract

Use the Sol-to-Terra workflow for architecture, data/model lineage, schemas or migrations, production/deployment behavior, security-sensitive work, or changes that span multiple subsystems. Use the normal fast path for a small, localized change that follows an established pattern.

## Amendments and commits

Terra may append a minor amendment and continue only when it preserves architecture, public interfaces, scope, and acceptance criteria. A material conflict requires stopping and returning to Sol for a revised contract.

Record whether the plan should receive a separate commit. A separate plan commit is recommended for multi-session work, asynchronous review, migrations, production changes, or difficult-to-reverse decisions. Git operations remain user-controlled.
