# Session: Surgical docs pruning and byplay_v2 planning

## TL;DR
- **Worked On:** Start-session review of the October repair track; critique of documentation and contract sprawl; a surgical docs prune; the `byplay_v2` contract.
- **Outcome:** `AGENTS.md` and `docs/status.md` were trimmed with dated history moved verbatim to `docs/status_history.md`. Contract statuses were normalized to the five lifecycle values. The index was split into open and completed contracts. `docs/plans/2026-10-09/01-byplay-v2-play-identity.md` was written (Approved). Phase A validation results are recorded below.
- **Plan Contract:** `docs/plans/2026-10-09/01-byplay-v2-play-identity.md`
- **Approval / Status:** User approved the three-phase plan in-session on 2026-10-09 after two review rounds. The byplay_v2 contract is Approved; implementation is for a fresh implement-plan session.
- **Blockers:** None for the docs work. Task 1 of the contract is a stop gate: the user reviews the impact and clock-reversal numbers before Task 2.
- **Next:** User-run checkpoint commit (Phase A), then the docs/contract commit, then a fresh implement-plan session for the byplay_v2 contract.

## Context and Decisions
- Scope order chosen by the user: cleanup first, impact-first `byplay_v2`, Production keeps the hold screen until the corrected packet is certified (Week 7 only if the Sunday 2026-10-11 checkpoint is met, otherwise Week 8 or later).
- Review corrections adopted: `uv run pytest` works (memory note corrected); no rewrite of the approved October 8 contract (append-only Amendment 1); `status.md` keeps every active serving fact; no new status keywords.
- Ordering rule: period first, then the provider's `drive_number`/`play_number`. The clock is diagnostic only, and clock reversals are counted but never excluded. Provider IDs are non-monotonic (negative and 18-digit IDs share one position), so they are never an ordering key. `source_play_id` is a string; float input is rejected.
- A stale fact was found and corrected rather than moved: the pre-Week-6 audit line said Production's team stats had 10,460 rows and waited for a republish, but the republish happened on 2026-10-07 and both databases hold 11,506 rows.

## Work Completed
- `AGENTS.md`: replaced the "Current focus (2026-10-04)" paragraph and the historical-checkpoint block with a pointer. The block was moved verbatim to `docs/status_history.md`, with link targets rebased to that folder. The weekly-checklist anchor and the test commands are untouched.
- `docs/status.md`: the former "In flight" section became "Open work" (the repair contract, release timing, Week 5/6, the production-boundary draft, matchup/team stats, the open score-stream issue, the pre-Week-6 audit with a dated correction, Stage 7B foundations). Twelve lines or blocks were moved verbatim (closed items, the long Window 1/Step 5/6A/6B paragraph, the stray banner and trailing Track 1 note). Week 7 wording was made conditional on the integrity-first rule. All Preview/Production differences, pins and receipts remain.
- Contract statuses: Track 1 promotion, game venues and the team-stats pipeline are Implemented; V6 (was Closed), the data decision packet (was Reviewed), the Stage 1 decision brief (was Decided) and the 5A/5B/5C receipts are Implemented as evidence records; Stage 7B is In Progress with its two evidence packets; four files with no status line received one. 87 Implemented, 36 Superseded, 8 In Progress, 2 Draft, 2 Approved.
- `docs/plans/index.md`: the active table was split into "Open contracts" and "Completed and superseded contracts (record)"; the repair-track, Stage 7B, V5 Product Transformation, archive-artifacts and byplay_v2 contracts were added to the open table; four stale state cells were refreshed. Six empty date folders were removed (untracked in git).
- Wrote the byplay_v2 contract and appended Amendment 1 to the October 8 repair-track contract. Corrected the memory note about `uv run pytest`.

## Files Modified
- `AGENTS.md`, `docs/status.md`, `docs/status_history.md` (new), `docs/plans/index.md`
- Status headers of about 17 contracts under `docs/plans/` (see the list above)
- `docs/plans/2026-10-09/01-byplay-v2-play-identity.md` (new), `docs/plans/2026-10-08/02-repair-track-certification-and-closure.md` (Amendment 1 appended)
- `session_logs/2026-10-09/02-cleanup-and-byplay-v2-planning.md` (this log)

## Validation
- [x] `uv run mkdocs build --strict --quiet` exits 0.
- [x] Every line moved out of `AGENTS.md` appears in `docs/status_history.md`; the `status.md` lines moved were copied by script.
- [x] Every contract status line starts with one of the five lifecycle values.
- [x] Phase A (run before the docs edits finished): full suite with `-W error` gave 2,239 passed, 14 skipped, 1 failed in 361 s. The failure was `test_data_first_documentation_authority.py::test_current_entry_points_link_single_v5_guide[AGENTS.md]`, caused by this session's AGENTS.md trim (the moved block held the `v5_status.md` link and the "Week 4" text). The pointer now restores both; that file passes (17 passed). No other test reads these docs, so the rest of the run stands, but the full suite was not rerun after the fix.
- [x] `ruff format --check .` (735 files already formatted), `ruff check .` and `git diff --check` pass.

## Amendments and Blockers
- Amendment 1 appended to the October 8 contract (pointer to the byplay_v2 contract). No other contract body was changed.

## Handoff Notes
- **Resume at:** Fresh implement-plan session on `docs/plans/2026-10-09/01-byplay-v2-play-identity.md`, Task 1 only, then report the numbers.
- **Deferred cleanup (do after the repair track closes, not mid-repair):** one weekly runbook merging `v5_weekly_operator.md` and `weekly_pipeline.md`; V4 staleness in `.codex/MAP.md`, `docs/project_org/feature_registry.md` and `production_runbook.md`; backfill `docs/decisions/decision_log.md` with the 2026 decisions; a glossary of the parallel naming schemes (Stage/Window/Track/Step/Amendment/c2/B2); an `operating_model.md` one-pager.
- **Open contracts for a later user decision (not closed here):** `2026-09-13/06`, `2026-09-23/01`, `2026-09-27/03`, `2026-10-03/04` (In Progress); `2026-10-02/01`, `2026-10-03/02` (Approved); `2026-10-02/03` (Draft, Phase 1 implemented).
- **Watch out for:** the clock must never become an exclusion rule without a separate decision on the Task 1 census; do not use provider IDs for ordering; do not copy run IDs outside `docs/status.md`.
- **Commit proposals (user-run):**
  1. After Phase A passes: `feat(quality): enforce schedule-based ingestion coverage, version policy and byplay_v1 collision guard`
  2. Docs only: `docs: prune status/AGENTS history, normalize contract statuses, add byplay_v2 contract`

**tags:** ["documentation", "planning", "integrity", "pipeline"]
