# V5 Replay and Preview Rehearsal

- **Status:** Implemented
- **Created:** 2026-09-24
- **Planner:** Sol (plan-session)
- **Approval source:** User selected the full Preview rehearsal and replay-first scope, then requested this plan be documented. This does not authorize production activation.
- **Implementation log:** `session_logs/2026-09-24/03-v5-replay-preview-rehearsal.md`
- **Commit policy:** Separate plan commit recommended; user authorized the current session's Git commit. Keep the implementation checkpoint and this plan in separate reviewable commits.

## Goal

Complete the next dependency in the [V5 Product Transformation](../2026-09-23/01-v5-product-transformation.md): write and independently verify the immutable Weeks 0–3 retrospective replay from clean committed code, publish and score Week 0 on Preview, prove populated Preview serving and same-week V4 rollback, then reselect V5. This milestone does not authorize a current-slate V5 forecast or production activation.

## Current State

The pinned inference bundle passed 8,935-game equivalence. The read-only 2026 replay reconstructed 157 games and 314 paired target predictions with zero gaps from certified Weeks 0–3 Contract 07/08 parents. Preview has migration 0013, V5 release policy, and 452 rating snapshots, but no V5 replay manifest or public selection. The worktree is dirty; `build_v5_replay.py --apply` requires a reviewed preflight and a matching clean committed code SHA. Preview Week 0 has a complete, frozen V4 fallback run `2026w0-a0edb9e72cb1` with eight stored predictions. `current_week` currently points to a 2025 replay, so a Week 0 historical selection does not change that singleton.

The web's selected-week queries currently filter out V4 runs. A V4 reselection would therefore fail to render as a rollback. `/api/health` reports only the `current_week` singleton and cannot prove a historical Week 0 selection. These are required repairs before the rehearsal.

## Proposed Approach

Use two clean-code checkpoints: first commit the reviewed replay and rollback-capable code, then apply the immutable replay; next pin its manifest in the serving config and commit that pin before Preview publication. Use the exact certified September 22 measurement and rating replay parents, not a refreshed or partially completed Week 4 parent. Keep all replay timestamps and evidence labels retrospective. Use explicit run selection only after the immutable weekly serving run is fully published and scored.

## Scope

### Included

- Replay manifest, independent receipt, gap artifact, Week 0 serving artifact, Preview publication and scoring, explicit selection, populated site checks, V4 reselection, and V5 restoration.
- Fixes needed for selected V4 rendering and selected-week health visibility; focused tests and operating evidence.

### Excluded

- Week 4 07/08 refresh, current-slate Contract 09 forecast, prospective freeze, production migration or activation, scheduler, and V4 retirement.
- Any V5 refit, 2026 outcome-based model selection, or claim that replay was frozen before kickoff.

## Affected Components and Contracts

- The existing replay builder, replay serving adapter/config, ops state machine, selected-run query, forecast page, health route, and focused tests.
- Preview R2 and Neon only; the Vercel Preview deployment must be bound to the isolated Preview Neon branch.
- The parent [product transformation contract](../2026-09-23/01-v5-product-transformation.md) and [weekly runbook](../../ops/weekly_pipeline.md) remain authoritative for release policy and operations.

## Implementation Tasks

### Task 1 — Make rollback render correctly and establish clean code

Allow the explicit selected run for a 2026 week to be V5 or an eligible legacy V4 rollback. Include selected V4 weeks in navigation and render their own model label, game predictions, and grades. Show the V5 performance banner only when the viewed week selects V5. Add a health response for an explicitly requested season/week that reports that week's selection, run identity, state, coverage, and whether it agrees with `current_week` when both refer to the same slate. A missing selection must not guess a run.

Run focused selection, site, and publication tests plus the existing quality gates. Review the whole dirty V5 milestone and have the user commit it. Record the full SHA and verify `git status --porcelain` is empty before replay apply.

**Acceptance:** V5 selection, V4 fallback, and missing selection behave distinctly in tests. The first checkpoint is clean and committed.

### Task 2 — Write and verify the retrospective replay

Use the certified 2026 measurement manifest `possession-v1-measurements-20260922-2026c` and independently verified rating replay `possession-v1-rating-replay-20260922-fcaa571`, with their exact manifest URIs from Contracts 07/08. Choose a unique run ID derived from the first checkpoint's short SHA; check its R2 prefix is empty. Save the dry-run JSON under `/tmp`, not the repository, and review parents, 157 games, 314 paired target rows, zero gaps, finite values, and independent digest. Apply with identical arguments, `--preflight-evidence`, and the committed SHA. Verify manifest, predictions, gaps, and signed verifier receipt independently; rerun verification for idempotence. A partial prefix or changed evidence requires a new run ID after diagnosis.

Pin the resulting replay manifest URI and raw SHA-256 in `conf/weekly_bets/v5_replay_2026.yaml`. Have the user commit this pin as the second checkpoint and confirm a clean worktree before serving publication.

**Acceptance:** Immutable replay and independent receipt are stable, and the serving config binds exactly their manifest bytes.

### Task 3 — Publish, score, and select Week 0 on Preview

Verify Preview credentials and migration 0013 before mutations; production must not be targeted. Resolve the immutable Silver `game_outcomes` reference from the certified 2026 source. Use stable `--pipeline-run-id` values with the resumable `publish-replay-week` and `score-replay-week` operator commands, repeating them to prove resume behavior. Confirm eight complete Week 0 predictions and results, `evidence_class=replay`, no prospective freeze timestamp, and no change to `current_week`. Select the exact scored V5 Week 0 run with a recorded reason. Verify `site_week_selection_history` and selected-run health.

**Acceptance:** Week 0 is explicitly selected on Preview; all eight forecasts and final scores are present and the replay is never labeled live.

### Task 4 — Prove populated serving and V4 rollback

Verify the Vercel Preview deployment uses the isolated Preview Neon branch before deploying or browsing it. Check Week 0 forecasts, ratings, team detail, replay performance, selected-run health, and model labels against the exact Preview DB run. Fixtures do not count as this evidence. Reselect frozen V4 run `2026w0-a0edb9e72cb1` with `--allow-v4-fallback`, verify the page and selected-run health show V4, then reselect V5 and verify restoration. Record exact run IDs, SHAs, selection-history rows, screenshots or responses, and measured rollback time. Leave production unchanged.

**Acceptance:** Both selections render the expected model and data, and V5 is restored on Preview after the rollback test.

## Testing Strategy

Run focused replay, publication, selection, scoring, and web tests; contracts validation; web lint, typecheck, build, and populated Preview browser checks; strict MkDocs build; and `git diff --check`. Test retry with the same pipeline run ID. Check negative cases for a missing selection, wrong-week run, altered replay artifact, changed parent, and V4 fallback without an eligible complete run.

## Risks and Edge Cases

- Do not save preflight evidence inside the repository before the clean-code gate. Do not change the pinned forecast config between preflight and apply.
- A partial immutable R2 prefix cannot be overwritten. Stop and diagnose; create a new run ID only after the cause is understood.
- The Preview `current_week` singleton points to 2025; historical Week 0 selection must be verified separately. Do not repoint the singleton merely to make health pass.
- If the Vercel Preview database binding cannot be proven isolated, stop before deployment. A local fixture page is not a substitute.
- Missing market lines may yield no market grades, but all eight replay forecasts and completed outcomes must be present. Performance MAE remains separately checkable.

## Definition of Done

- [x] Both clean committed checkpoints exist and the replay manifest/receipt match their reviewed inputs.
- [x] Preview Week 0 publication, scoring, selection, browser serving, V4 rollback, and V5 restoration pass with recorded evidence.
- [x] Focused tests, contracts validation, web quality gates, strict docs build, and diff check pass.
- [x] The product transformation contract, operating docs, and implementation session log reflect the exact outcome and any blockers.
- [x] This plan's status is changed to `Implemented` only after every item passes.

## Amendments

Any change to parent lineage, clean-code requirement, replay evidence class, selected-run semantics, or Preview/production boundary requires a recorded amendment before implementation. Stop for a material conflict with the parent transformation contract.

### Amendment 1 (2026-09-24, user-authorized): Task 4 binding proof reordered

The Vercel Preview `DATABASE_URL` (created 2026-08-14 as a Sensitive value) is
non-decryptable via CLI (`env pull` is Development-only) or API (ciphertext),
and unrecoverable locally (Keychain holds only pipeline/migrator; the Preview
branch `cks_preview_web` password is unknown). No current Preview deployment
exists to probe. The user explicitly chose deploy-then-verify over rotation and
over stopping. Isolation will therefore be proven on the fresh Preview
deployment itself via unambiguous discriminators: `/api/health` must show the
Preview-only singleton `(2025, 16, v4replay-2025-w16)`, and
`/api/health?season=2026&week=0` must show the Preview-only selection
`2026w0-cb2252a0w0v5`. Production Neon can show neither (its singleton is the
live 2026 season; it lacks migration 0013). If any discriminator fails, the
deployment is torn down immediately and the binding is treated as unproven.
The Preview-only mutation boundary and zero-production-writes rule are
unchanged; the web role is read-only and a mispointed deployment could only
ever read already-public data.

### Amendment 2 (2026-09-24, user-authorized): rollback target lineage correction

The contract's Current State and Task 4 attributed frozen run
`2026w0-a0edb9e72cb1` to V4. The Preview database shows it is
`Trench Warfare V2 Preview` (`week0-2026-preview-20260814`, frozen, 8/8/8):
eligible legacy fallback mechanics, but not the V4-serving view. The true V4
run is published `2026w0-3e4fa1b9b07d` (`Trench Warfare V4`,
`week0-2026-v4-strict-20260818-r2`, 8/8/8). The user directed the rollback
drill at the true V4 run so the rehearsal proves return to V4 serving. The
V2-preview selection remains as fallback-mechanics evidence.
