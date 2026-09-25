# Session: V5 Week 4 replay adapter implementation

## TL;DR

- **Worked On:** Phase 0 approval edits for the replay-cutover plan plus Phase 1 Task 1 (Week 4 factual boundary and replay adapter).
- **Outcome:** Plan 02 Approved with Amendment 1 (Week 4 grades vs frozen quotes); `build_v5_week4_replay.py` built with 9 focused tests; real dry run reconstructed 58/116 verified predictions against pinned parents. Immutable apply awaits a clean committed tree.
- **Plan Contract:** `docs/plans/2026-09-25/02-v5-week4-replay-site-cutover.md` (Approved).
- **Approval / Status:** User approved the replay lane on 2026-09-25 with three decisions (V5-labeled history; parallel with live plan; grades vs frozen quotes). No authorization or selection written yet.
- **Blockers:** Dirty worktree blocks `--apply` (builder enforces clean committed code). Needs the two commits below first.
- **Next:** After the user commits, `--apply` the replay run (`v5-week4-replay-20260925`) with the reviewed preflight evidence in tmp, then begin Task 2 (migration 0015 + replay admission lane).

## Context and Decisions

- The live-forecast loader's `_prior_weeks_gate` is reusable for a pre-kickoff slice, but its `_week4_gate` (defined, unwired) shows the live chain structurally targets stabilized evidence. The adapter therefore composes the shared math directly (`load_live_forecast_sources(target_week=4)`, `build_current_team_states`, `build_live_application_frame`, exported bridge) under a replay envelope with its own gates, rather than touching live semantics.
- Source cutoff = the certified W0–3 measurement `as_of` (2026-09-22T14:58:00Z); schedule = the pinned Silver games version `e3ead581...` already bound by that repair run. Inventory proved it holds exactly the same 58 games and kickoff times as the production-frozen W4 slate (zero mismatches).
- Whole-slate replay labeling (even the 57 not-yet-kicked games) is deliberate: avoids a mixed-evidence artifact and follows the approved conservative choice.

## Work Completed

- Approved plan 02 (status, approval source, Amendment 1, index sync) — validated strict MkDocs + `git diff --check`.
- Added `scripts/pipeline/build_v5_week4_replay.py` (compute/evidence/apply/verify; manifest schema `v5_week4_replay_manifest_v1`; `late_publication: true`; `evidence_class: replay`; actual `created_at_utc` recorded at apply).
- Added `tests/test_v5_week4_replay.py` (9 tests: evidence envelope, wrong-week, incomplete slate, post-kickoff cutoff, cutoff-before-parents, post-W3 population, changed bundle, verify happy path, prospective-label rejection).
- Real dry run: 58 games / 116 paired targets, independently verified, timing block records pre-kickoff cutoff and late publication. Evidence saved outside the repo at `/var/folders/.../T/opencode/v5-week4-replay-preflight.json`.

## Files Modified

- `docs/plans/2026-09-25/02-v5-week4-replay-site-cutover.md` - Approved status, approval source, Amendment 1.
- `docs/plans/index.md` - Approved replay-plan reference.
- `scripts/pipeline/build_v5_week4_replay.py` - new Week 4 replay adapter.
- `tests/test_v5_week4_replay.py` - new focused gates.

## Validation

- [x] `tests/test_v5_week4_replay.py`: 9 passed; ruff check + format clean on both new files.
- [x] Real `build_v5_week4_replay.py` preflight against pinned parents: 58/116, verified true, Task-1 acceptance values recorded.
- [x] Strict MkDocs build; `git diff --check`.
- [ ] Immutable `--apply` + verifier receipt (blocked on clean tree).
- [ ] Full pytest rerun after commit.

## Amendments and Blockers

Amendment 1 recorded in the plan (Week 4 replay grades vs frozen V4 pre-kickoff quotes). No code or R2/Preview/Neon mutation for serving yet; preflight only.

## Handoff Notes

- **Resume at:** User runs the two commits below, then `--apply` with `--preflight-evidence /var/folders/b5/wrh935896v148pd_2rvkcbz00000gn/T/opencode/v5-week4-replay-preflight.json` (HEAD must still equal the evidence `code_sha`; rerun preflight first if anything landed since).
- **Watch out for:** Do not regenerate the frozen W0–3 replay bytes; the W4 run-id prefix must stay distinct. Task 2 touches the live release-boundary code shared with the Week 5 path — keep changes additive.

**Suggested commits:**
1. `Approve V5 Week 4 replay site cutover plan` — plan doc, index, session log 08.
2. `Add Week 4 late-publication V5 replay builder` — adapter script, its tests, session log 09.

**tags:** ["v5", "replay", "week4", "planning"]
