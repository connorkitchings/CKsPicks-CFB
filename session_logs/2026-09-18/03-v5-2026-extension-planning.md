# Session: V5 2026 Extension Planning — Bottleneck Removal (Sol)

## TL;DR
- **Worked On:** Start-session refresh, bottleneck investigation (three parallel explores), and the 2026 extension plan.
- **Outcome:** Bottleneck chain B1–B8 mapped; user decided Repair extension / three layered contracts / full season from Week 0; Contracts 07/08/09 persisted as Approved; plan index updated. No implementation started per explicit instruction.
- **Plan Contract:** `docs/plans/2026-09-18/07-v5-2026-repair-and-measurement-extension.md`, `.../08-v5-2026-rating-state-replay.md`, `.../09-v5-2026-forecast-and-readiness.md` (all Approved)
- **Approval / Status:** User approved the plan ("Yes, update the contracts. Do not start implementation.") on 2026-09-18.
- **Blockers:** None for planning. Execution blocker chain documented in contracts (Preview 2026 Silver sync is the 07 entry gate).
- **Next:** Ops fast path: sync Preview 2026 Silver (prepare-week W4). Then fresh Terra task implements Contract 07.

## Context and Decisions
- Start-session verified: `main` clean at `3147812`; `CFB_STORAGE_BACKEND='r2'` with all source/preview R2 credentials present (no secrets exposed).
- V5 queue state confirmed: contracts 00–05 Implemented and Preview-certified; 06 Approved but blocked (`ready` gate unmet, 0 qualifying slates).
- Three parallel explore agents surveyed: (a) V5 measurement/rating/forecast runners + `conf/research/data_first_football_v1/` configs; (b) 2026 ingestion + V4 weekly pipeline + live Silver/Gold state; (c) shadow modules, readiness sources, runbook CLIs, 06 entry gates.
- Key findings: season pinning fail-closed via `DEVELOPMENT_SEASONS`; `timing_class` sealed to `historically_reconstructed` in ~20 schema contracts; parent run-IDs hardcoded at each layer; population counts hardcoded (8936/8935); Preview DB lags production (W1/0-results/2025W16-replay vs 157-games/100-results/W3).
- User decisions via question tool: Repair extension over V4-Silver-direct; three layered contracts over single contract; full season from Week 0 over current-week-forward.
- Plan presented in chat (plan mode read-only); on approval, mode switched to build for docs-only persistence.

## Work Completed
- Bottleneck inventory B1–B8 with ordered unblock dependencies.
- Three decision-complete contracts written (goal, entry gate, tasks with acceptance/validation, testing, risks, DoD, amendment process).
- `docs/plans/index.md`: new "V5-07/08/09 2026 extension sequence" section with status/dependency rows.
- This planning session log.

## Files Modified
- `docs/plans/2026-09-18/07-v5-2026-repair-and-measurement-extension.md` - new contract (Approved)
- `docs/plans/2026-09-18/08-v5-2026-rating-state-replay.md` - new contract (Approved)
- `docs/plans/2026-09-18/09-v5-2026-forecast-and-readiness.md` - new contract (Approved)
- `docs/plans/index.md` - 07/08/09 section added
- `session_logs/2026-09-18/03-v5-2026-extension-planning.md` - this log

## Validation
- [x] `git diff --check` — clean (end-session re-run)
- [x] `uv run mkdocs build --quiet` — clean (end-session re-run)

## Amendments and Blockers
- None. Scope note: the Preview 2026 Silver sync (07 entry gate) is an ops fast-path task using existing `prepare-week` tooling, intentionally left out of the contracts.

## Handoff Notes
- **Resume at:** Ops fast path — sync Preview 2026 Silver through latest completed week. Then open a fresh Terra task with the implement-plan skill and the exact path `docs/plans/2026-09-18/07-v5-2026-repair-and-measurement-extension.md`.
- **Watch out for:** 08 must not start before 07 is Implemented; 09 must not start before 07+08 are Implemented; 06 collection must not start before 09 certifies `ready`. No production/Neon/web writes in any of 07–09. Historical certified artifacts (R6, 03, 04B, Repair v2) are never mutated.

**tags:** ["v5", "planning", "2026-extension", "contract-07", "contract-08", "contract-09", "bottleneck"]
