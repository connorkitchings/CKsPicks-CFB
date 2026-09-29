# Session: Task 4 preflight — versioned forecasts and replacement scores

## TL;DR
- **Worked On:** Task 4 of `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md` — successor forecasts (W0–4 replay + W5 prospective candidate) and serving predictions + grades, preflight only.
- **Outcome:** Forecast build, serving build, and serving verifier all pass locally. 215-game MAE reconciles exactly with the research counterfactual. No R2/Neon mutation, no freeze, no commit.
- **Plan Contract:** `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md` (`In Progress`).
- **Approval / Status:** User approved release tag `20260929-p1` and doing the MAE reconciliation now. Exact production release remains a later packet-specific decision.
- **Blockers:** None for preflight. All `--apply` paths need a clean checkout at the expected SHA; checkout is dirty by design.
- **Next:** Task 5 (lineage-aware release/selection) and Task 6 (Preview rehearsal + exact packets).

## Context and Decisions
- R2-mode builds require published successor URIs + verifier records (don't exist until `--apply`), so preflight used the local-cache path: Task 2 bundle dir + Task 3 ratings dir + a glue-assembled cache in `/var/…/opencode/v5-intended-update/` (accepted replay/live features, schedule, W0–4 market snapshots/quotes — all SHA-verified against the lock). Never repository `./data/`.
- Cache assembly needed one glue script (`assemble_task4_cache.py`, lives in /tmp, not the repo). Task 3's `PYTHONPATH=.:src` requirement applied to all four scripts.
- Runs: `2026w{W}-v5repair-20260929-p1`; W0–4 `frozen`/replay, W5 `candidate`/`pending` (unfrozen — freezing is a Task 6 decision gated on the 2026-10-02 kickoff).

## Work Completed
- Assembled Task 4 cache: 215 replay + 56 live feature rows, 761-game schedule, W0–4 market frames (all content SHAs match lock).
- Forecast build: 6 manifests, game counts 8/43/49/57/58/56, rows 2× each; parents bound to Task 2 bundle (`30c4f1eb…`), Task 3 ratings (`a15d76f3…`), lock (`eaecabec…`).
- Serving build: W0–4 predictions + scores; quote counts 16/86/98/113/116 (W3's 113 = known Houston total gap, the only allowed miss).
- Serving verifier: all 5 weeks `verified` (best-quote selection, edge math, grade math vs certified finals).
- 215-game MAE reconciliation vs the 2026 counterfactual report.

## Files Modified
- `scripts/pipeline/verify_v5_intended_update_serving.py` — whitespace-only `ruff format` (was the only unformatted Task 4 file).
- `session_logs/2026-09-29/05-v5-intended-update-task4-preflight.md` — this log.

## Validation
- [x] Forecast populations == locked games per week; replay/live disjoint; live targets Week 5 only.
- [x] Serving keys == locked selection; spreads fully quoted; total gaps == allowed W3 game only; finals present for all 215.
- [x] Serving verifier: W0–4 verified, receipts written to /tmp verification dir.
- [x] MAE reconciliation: new margin MAE **14.512** == research full-refit **14.512**; new total **12.123** == research **12.123**. Per-week margin: W0 11.306 / W1 18.303 / W2 13.840 / W3 12.349 / W4 14.838 (matches the report's "Week 1 worse" note). No unexplained difference — promotion not blocked.
- [x] Ruff format + lint clean (3 files, after one whitespace reformat). Focused estimator tests: 5 passed. `git diff --check`: clean.
- [ ] R2 `--apply` (forecasts, serving, verifiers), Neon projection/selection, W5 freeze — deferred to Tasks 5–6 after commit.

## Amendments and Blockers
- No architecture amendment. Preflight-only execution is within Task 4's acceptance sequence.
- Runbook notes for Task 6: scripts need `PYTHONPATH=.:src`; Task 4 preflight needs the /tmp cache assembly step (or committed equivalent) until R2 `--apply` is done.

## Handoff Notes
- **Resume at:** Task 5 (migration 0018, `v5_intended_update_release.py`, `public_selection.py`, `publish_to_db.py`, web lineage scoping) then Task 6 Preview rehearsal with the exact packets.
- **Watch out for:** W5 first kickoff 2026-10-02T00:00Z — re-check kickoff/freeze state before any prospective decision. Retrospective W0–4 must be labeled replay, never prospective picks. No `--apply` until commit order is resolved.

**tags:** ["ratings", "v5", "production", "implementation", "task4"]
