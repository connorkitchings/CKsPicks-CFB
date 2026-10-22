# Session: V5 product transformation continuation

## TL;DR

- **Worked On:** Full-corpus inference export, current-slate verification, replay and rating publication, Preview migration, scoring compatibility, site pages, and resumable operations.
- **Outcome:** Pinned an equivalent immutable inference bundle; verified a 58-game Week 4 preflight and 157-game replay dry run; published 452 rating snapshots and migration 0013 to Preview. V4 remains public.
- **Plan Contract:** `docs/plans/2026-09-23/01-v5-product-transformation.md` (In Progress).
- **Approval / Status:** User authorized implementation; Git operations remain user-controlled. Production activation still needs a separate exact-artifact decision.
- **Blockers:** Dirty worktree prevents clean-code-gated replay apply and current live forecast apply. Week 4 07/08 refresh, populated Preview publication/rollback, and production release packet remain open.
- **Next:** Commit the reviewed milestone manually; rerun replay preflight against that clean SHA, apply and independently verify replay, pin its serving config, then publish/score/select on Preview. Refresh 07/08 after stable Week 4 finals.

## Context and Decisions

- The historical feature loader bypasses the redundant 24.2-million-row adjusted-history audit while reading signed, certified feature inputs directly. The full 8,935-game eligible corpus passed finite-value and independent prediction-equivalence checks: zero exclusions, maximum absolute difference `2.842170943040401e-14`.
- The immutable inference bundle at `artifacts/research/data-first-football-v1/forecasts/inference/f80b63ef01211bc9679b4b65769a3f16c7302c06cfa2b7806f6b8d830f19da0b/bundle.json` is pinned in `conf/research/data_first_football_v1/live_forecast_v1.yaml` with SHA-256 `f80b63ef01211bc9679b4b65769a3f16c7302c06cfa2b7806f6b8d830f19da0b`.
- Independent Week 4 preflight from certified Weeks 0–3 parents produced 58 games / 116 target rows and digest `b4b69567da5ad5e5efa89fd6fcb7ce3b28c904ee2ed3c4fb56496466fa209797`. This was a read-only dry run, not a frozen live forecast.
- Replay reconstruction produced 157 games / 314 paired target rows for Weeks 0–3 with zero gaps. Apply requires reviewed preflight evidence and a clean committed code SHA. Replay remains clearly distinct from frozen-before-kickoff forecasts.
- Preview migration 0013 and release policy were applied with branch-scoped credentials. The existing V4 active run was unchanged; no public V5 selection was made. The rating projection wrote 452 snapshots (314 pregame, 138 current) from rating source SHA `0c7bca598dcf5a377b7c619edba7eca34bb31dd7c61d489d47c06a5bfc38e3f0`.

## Work Completed

- Added independent bundle/forecast checks, signed replay artifact builder and verifier, weekly replay serving adapter, final publication boundary verification, rating projection, and resumable replay/score operator commands.
- Added migration and explicit public selection policy. Preserved pre-migration V4 scoring compatibility while production lacks 0013.
- Added V5 ratings, team, performance, and methodology site pages. Local fixture browser checks showed populated ratings, team detail, and replay/live performance.

## Validation

- [x] 88 focused Python tests passed.
- [x] Web lint, TypeScript check, and production build passed. The first build attempt hit a sandbox-only Turbopack local-port denial; a permitted rerun succeeded.
- [x] Strict MkDocs build and contracts validation passed.
- [x] Ruff and `git diff --check` passed.
- [x] Real R2 full-corpus bundle equivalence, Week 4 preflight, and replay/serving dry runs passed.
- [x] Preview migration 0013, release policy, V4 active-run preservation, and 452 rating rows checked.
- [ ] Clean-code durable replay apply, Preview replay scoring and public selection, populated Preview browser and V4 rollback rehearsal.
- [ ] Week 4 07/08 refresh and exact production activation packet.

## Amendments and Blockers

No model change or waiver. The transformation contract remains In Progress. The V5 scheduler and V4 execution retirement are still outstanding. Do not claim production V5 activation from this evidence.

## Handoff Notes

- **Resume at:** Review and manually commit this dirty milestone. Rerun replay preflight with that code SHA, then apply/verify, pin the replay manifest, and exercise Preview publication, scoring, selection, browser serving, and rollback.
- **Watch out for:** Preview DB commands need `zsh scripts/ops/with_preview_env.sh`; `.env` alone lacks the migrator role. Never print credentials. Keep V4 serving until an explicit activation decision and successful V5 publish/freeze/close cycle.

**Suggested commit message:** `Advance V5 replay, Preview serving, and inference verification`

**tags:** ["v5", "forecast", "replay", "ratings", "publication", "web"]
