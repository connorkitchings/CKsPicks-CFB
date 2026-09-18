# Session: V5-05B Freeze, Scoring, and Evidence Ledger Implementation (Terra)

## TL;DR
- **Worked On:** Implemented Contract 05B Tasks 1–3 (measured immutable shadow freeze, outcome-versioned scoring, evidence ledger/counter, freeze & score CLI runners, and Phase 05B Preview certification).
- **Outcome:** All tasks completed and certified in Preview:
  - Certified Freeze Artifact: `artifacts/research/data-first-football-v1/possession-v1/shadow/runs/shadow-v1-20260918-73e8e9b-05b-freeze/freeze-manifest.json` (45 paired games, 90 prediction rows, T-2h lead 7200s, idempotent repeat verified).
  - Certified Score Artifact: `artifacts/research/data-first-football-v1/possession-v1/shadow/runs/shadow-v1-20260918-7aec1c8-05b-score/score-manifest.json` (45 paired games scored, 90 evaluation rows, 1 qualifying slate in evidence ledger, idempotent repeat verified).
- **Plan Contract:** `docs/plans/2026-09-17/05-v5-05b-freeze-score-ledger.md` (Implemented)
- **Approval / Status:** User authorized implementation and executed intermediate code commits (`0ae3a1c`, `73e8e9b`, `d49d050`, `7aec1c8`). All DoD items satisfied.
- **Blockers:** None.
- **Next:** User executes final evidence documentation commit checkpoint -> proceed to Phase 05C (diagnostic rehearsal, verification, runbook).

## Context and Decisions
- Entry gate verified: 05A Implemented at `2467a64` with certified Preview artifact `shadow-v1-20260917-cd07d8b-05a`. All 6 shadow schemas and constants in `shadow_v1.yaml` are sealed.
- Contract 05B approved: implements measured shadow freeze with T-2h target / T-1h hard lead, >=40 paired games, population preservation (broader, paired, excluded), slate digest, and outcome-versioned scoring with 24h stabilization gate, trustworthy completion timestamps, error/CRPS/coverage metrics, and no-double-counting evidence ledger.
- Data structures and schemas: `shadow_freeze` (compact), `shadow_prediction` (partitioned by season, week), `shadow_evaluation` (partitioned by season, week, outcome_version), and `shadow_evidence_counter` (compact).
- Idempotency & fail-closed rules: byte-identical reruns return `already_applied` with zero writes; any partial prefix or identity mismatch aborts permanently.
- Fail-closed execution repair: initial apply caught null defaults in synthetic prediction and boolean type requirement on `coverage_95` in `shadow_evaluation`; these were repaired, verified via tests, committed, and clean certification runs executed on fresh commit SHAs.

## Work Completed

### Task 1 — Measured Immutable Freezes
- Extended `src/cks_picks_cfb/forecast/shadow.py`:
  - `FreezePlan` dataclass.
  - `plan_freeze()`: derives first kickoff from schedule, enforces `lead_seconds >= freeze_hard_lead_seconds` (3600s / T-1h), pairs V5 with V4 predictions on `(game_id, target)`, enforces `paired_count >= min_paired_games` (40), computes SHA-256 slate digest and identity SHA, formats `shadow_freeze` row and `shadow_prediction` DataFrame with non-null fallbacks.
- Created `scripts/research/run_v5_shadow_freeze.py`:
  - Preflight dry-run: verifies parent chain and config, plans datasets, validates frames against schema, outputs deterministic JSON plan.
  - Apply: publishes publication plan first, writes `shadow_prediction` partitions via `PartitionedDatasetWriter`, writes `shadow_freeze` compact dataset version, writes terminal `freeze-manifest.json` last.
- Created `tests/test_v5_shadow_freeze.py`:
  - 18 focused tests covering T-2h target, T-1h hard gate rejection, kickoff rejection, naive timestamp rejection, 39-vs-40 game boundary, V4 missing pairs, population preservation, and slate digest determinism.

### Task 2 — Outcome-Versioned Scoring and Counting
- Extended `src/cks_picks_cfb/forecast/shadow.py`:
  - `ScoreResult` dataclass.
  - `score_freeze()`: verifies >=24h (86400s) stabilization window from last trustworthy game completion, rejects missing/null timestamps, computes error, CRPS, boolean 95% coverage, MAE margin/total, formats `shadow_evaluation` DataFrame and `shadow_evidence_counter` record.
  - `update_evidence_counter()`: deduplicates by `(candidate, season, week)`, prevents double-counting across corrections, preserves version links.
- Created `scripts/research/run_v5_shadow_score.py`:
  - Preflight dry-run: loads freeze manifest + freeze datasets + outcomes, executes scoring and counter update, outputs deterministic JSON plan.
  - Apply: publication plan first, writes `shadow_evaluation` partitioned by `(season, week, outcome_version)`, writes `shadow_evidence_counter` compact dataset version, writes terminal `score-manifest.json` last.
- Created `tests/test_v5_shadow_score.py`:
  - 22 focused tests covering 24h stabilization gate edge cases, missing timestamp rejection, scoring calculations, error/CRPS/MAE correctness, correction version linking, counter no-double-count rule, multiple week counting, and empty/missing outcome errors.

### Task 3 — Phase 05B Preview Certification
- Built diagnostic rehearsal fixtures for 2025 Week 10 (45 games) in Preview R2.
- Freeze Certification:
  - Run ID: `shadow-v1-20260918-73e8e9b-05b-freeze`
  - Preflight: dry run complete, 45 paired games, slate digest `16ae8420df3a`.
  - Apply: wrote `shadow_prediction` (90 rows) and `shadow_freeze` (1 row), terminal manifest `freeze-manifest.json`.
  - Idempotent repeat: verified `already_applied`, zero writes.
- Score Certification:
  - Run ID: `shadow-v1-20260918-7aec1c8-05b-score`
  - Preflight: dry run complete, 45 paired games scored, qualifying `true` (normal_coverage).
  - Apply: wrote `shadow_evaluation` (90 rows) and `shadow_evidence_counter` (1 row, qualifying count = 1), terminal manifest `score-manifest.json`.
  - Idempotent repeat: verified `already_applied`, zero writes.

## Files Modified / Created
- `src/cks_picks_cfb/forecast/shadow.py` — extended with `plan_freeze()`, `score_freeze()`, `update_evidence_counter()`
- `scripts/research/run_v5_shadow_freeze.py` — new freeze CLI runner
- `scripts/research/run_v5_shadow_score.py` — new score CLI runner
- `tests/test_v5_shadow_freeze.py` — new freeze unit tests (18 tests)
- `tests/test_v5_shadow_score.py` — new score unit tests (22 tests)
- `docs/plans/2026-09-17/05-v5-05b-freeze-score-ledger.md` — updated to Implemented, DoD completed, certified artifacts recorded
- `docs/plans/index.md` — updated 05B to Implemented, 05C entry gate marked met
- `session_logs/2026-09-17/12-v5-05b-freeze-score-ledger.md` — this log

## Validation
- [x] `PYTHONPATH=.:src uv run pytest tests/test_v5_shadow_freeze.py tests/test_v5_shadow_score.py tests/test_v5_shadow_readiness.py -W error -q` — 55 passed in 1.58s
- [x] `uv run ruff check .` — all checks passed
- [x] `uv run python contracts/validation.py` — passed
- [x] `uv run mkdocs build --quiet` — clean
- [x] Freeze certification: preflight, apply, repeat verified in Preview R2
- [x] Score certification: preflight, apply, repeat verified in Preview R2
- [x] `git diff --check` — clean

## Handoff Notes
- **Resume at:** User commits evidence checkpoint documentation. Then proceed to Contract 05C (diagnostic rehearsal, verification, and runbook).
- **Commit command proposal:**
  ```bash
  git add \
    docs/plans/2026-09-17/05-v5-05b-freeze-score-ledger.md \
    docs/plans/index.md \
    session_logs/2026-09-17/12-v5-05b-freeze-score-ledger.md
  git commit -m "docs(v5): certify V5-05B shadow freeze and score manifests in Preview"
  ```
- **Certified URIs:**
  - Freeze Manifest: `artifacts/research/data-first-football-v1/possession-v1/shadow/runs/shadow-v1-20260918-73e8e9b-05b-freeze/freeze-manifest.json`
  - Score Manifest: `artifacts/research/data-first-football-v1/possession-v1/shadow/runs/shadow-v1-20260918-7aec1c8-05b-score/score-manifest.json`

**tags:** ["v5", "shadow", "freeze", "scoring", "evidence_ledger", "preview", "certification"]
