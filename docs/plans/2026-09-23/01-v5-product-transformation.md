# V5 Product Transformation

- **Status:** In Progress
- **Approval source:** User requested implementation of the full proposed plan and confirmed “proceed” in this task on 2026-09-23.
- **Implementation log:** `session_logs/2026-09-23/01-v5-product-transformation.md`
- **Commit policy:** Reviewable milestone commits proposed; Git operations remain user-controlled.

## Goal and acceptance

Turn the existing R2 → Neon → Vercel repository into a V5-only public forecasting product with 2026 retrospective replay and live forecasts, a ratings-focused site, one resumable weekly workflow, and retired V4 execution after one successful V5 publish/freeze/close cycle. Preserve V4 records privately and preserve the accepted V5 mathematics. Production activation requires review of exact release artifacts and Preview evidence.

## Ordered work

1. Correct the current-state handoff, export an immutable inference bundle equivalent to the through-2025 bridge, extract production APIs from research CLIs, and replace routine Week-4-specific checks with requested-slate freshness checks. Keep the first cutover's stabilized-Week-4 prerequisite.
2. Add explicit public season/week run selection and history, evidence class and truthful replay timestamps, replay earlier 2026 with point-in-time inputs, and authorize V5 at the final publication boundary. Rehearse Preview migration, forecast, scoring, and rollback before production release.
3. Publish version-bound rating projections to Neon. Build forecasts, ratings, team detail/history, performance, and methodology on the existing Next.js app. Keep replay and live results separate within a combined season view.
4. Make a resumable scheduled workflow with idempotent receipts and existing timing/provider limits. Simplify current docs and remove obsolete code, tests, configs, and dependencies only after dependency and recovery checks. Preserve migrations and immutable lineage.

## Validation

Focused model timing/equivalence tests; migrations and shared contracts; publication and rollback tests; web lint, typecheck, build, and browser checks; workflow retry/concurrency checks; strict documentation build and `git diff --check`. Verify live lineage and full coverage on Preview before preparing the exact production release packet.

## Limits and amendment policy

No 2026 outcome fitting, retroactive claim of live evidence, V4 public aggregate, or changed FBS-vs-FBS scope. Model/schema/release-policy changes outside this contract require an explicit amendment. The contract stays In Progress until every acceptance item has passed.

## 2026-09-24 implementation checkpoint

The certified 157-game 2026 measurement artifact and validated 761-game schedule now produce 58 outcome-free Week 4 target rows in a read-only R2 dry run. Source names are reconciled through the existing canonical team mapping. An independent as-of calculation agrees with the producer on that real lineage, and the ratings projection reads 452 rows from the partitioned replay artifact. The inference exporter now compares the complete eligible historical feature corpus and fails on nonfinite outputs. Its corrected dry run was interrupted during historical adjusted-history verification before reaching the equivalence comparison; that read path needs a bounded/runtime improvement. No inference bundle has been written or pinned.

The additive selection migration preserves the existing V4 serving view until activation. V5 publication and selection check the database policy regardless of process environment, direct prospective publication verifies the source forecast, and prospective evidence starts as pending. The freeze path uses database time and marks a missed one-hour boundary without a live timestamp. The site preserves an explicitly requested unavailable week and shows full team schedules. These changes have focused tests and static checks, but no disposable-database migration rehearsal or populated Preview browser check yet.

Remaining work follows the original stages: publish and pin the equivalence-certified bundle and as-of state release; build durable replay artifacts, explained gaps, rating projections and scoring; finish the resumable scheduler and product coverage; rehearse Preview and obtain the exact production activation decision after stabilized Week 4 finals; then complete one V5 weekly cycle before retiring V4 execution. None of these gates is waived by this checkpoint.

## 2026-09-24 continuation checkpoint

The historical feature loader now reads the bounded certified population, scoring, eligibility, and state inputs without repeating the large adjusted-history audit. The complete 8,935-game corpus passed finite-value and independent prediction-equivalence checks with zero exclusions and maximum absolute difference `2.842170943040401e-14`. An immutable inference bundle was written and pinned at SHA-256 `f80b63ef01211bc9679b4b65769a3f16c7302c06cfa2b7806f6b8d830f19da0b`. A read-only Week 4 preflight independently reconstructed 58 games and 116 target rows from certified Weeks 0–3 parents. It is not a frozen prospective forecast or a Contract 09 release.

Retrospective replay reconstruction passed a real 157-game, zero-gap dry run for Weeks 0–3, with 314 target rows and separate `replay` timing. Its immutable apply requires a reviewed preflight and a clean committed code SHA, so no replay artifact or public selection has been written from this dirty worktree. The V5 rating projection published 452 version-bound snapshots to Preview. Migration 0013 and Preview release policy were applied; the V4 active public run was unchanged. Local fixture browser checks passed for populated forecasts, ratings, team detail, and performance. These are interface checks, not populated Preview serving proof.

The resumable operator now has separate rating projection, replay publication, and replay scoring commands. Production scoring retains its legacy query until migration 0013 reaches production. The scheduled V5 workflow, durable replay and scoring, Preview public selection/rollback rehearsal, refreshed Week 4 07/08 parents, Contract 09 live artifact, and exact activation packet remain open. Production activation and V4 retirement are not authorized by this checkpoint.
