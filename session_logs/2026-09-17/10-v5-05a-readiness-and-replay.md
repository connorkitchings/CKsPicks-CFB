# Session: V5-05A Readiness and Replay Implementation (Terra)

## TL;DR
- **Worked On:** Implemented Contract 05A Tasks 1–3 (shadow contracts, readiness validation, frozen replay, CLI with apply path)
- **Outcome:** All code complete, 15 focused tests green, adjacent suites green, contracts/mkdocs/ruff green. Task 4 certification pending user commit (apply requires clean worktree).
- **Plan Contract:** `docs/plans/2026-09-17/04-v5-05a-readiness-and-replay.md` (In Progress)
- **Approval / Status:** User explicitly authorized this exact path 2026-09-17; contract flipped Draft → Approved → In Progress
- **Blockers:** (1) Task 4 needs a committed worktree — user executes git. (2) Pre-existing full-suite failure unrelated to this work (see below).
- **Next:** User commits code checkpoint → fresh session runs 05A certification (preflight/apply/verify/repeat) → user commits evidence checkpoint

## Context and Decisions
- Entry gate verified: Contract 04 Implemented (`forecast-v1-20260917-4600ddd-04b` certified in this environment); no V5 shadow code/config/schemas existed — assumption confirmed.
- Pre-existing worktree changes (planning docs, readiness assessment, session logs 08/09) preserved untouched; implementation added only new files plus additive schema registration.
- Producer code lives in `src/cks_picks_cfb/forecast/shadow.py` per plan; verifier boundary deferred to 05C.
- Certification assessment targets 2026 Week 4 (expected `blocked`: no 2026 measurement/rating pipeline, Preview lag) — verified assessment decides, expectation does not substitute.
- Replay bounded to 2024–2025 seasons with full-history fits; byte-identity + perturbation invariance proven twice (unit + certification preflight).

## Work Completed

### Task 1 — Shadow data contracts and config
- New `src/cks_picks_cfb/data/data_first_shadow_v1.py`: six dataset registry, column tuples, `validate_shadow_config()`, `verify_candidate_parents()` (exact 04/R6/Repair chain via forecast `verify_rating_parent`), `shadow_identity()`, `shadow_manifest()` (signed, manifest-last, readiness-only refs).
- Registered `_SHADOW_SCHEMAS` + `schema_for` branch in `schema_contracts.py`.
- New `conf/research/data_first_football_v1/shadow_v1.yaml` (timing constants, 40-game gate, `production_activation_authorized: false`).
- 7 contract tests: schema resolution, config drift rejection, URI-substitution/tamper rejection, identity pinning, manifest shape.

### Task 2 — Source availability and readiness report
- New `src/cks_picks_cfb/forecast/shadow.py`: `check_source_availability()` (six sources, capture-vs-cutoff timing, neutral fallback for priors only), `readiness_overall()` (ready iff all mandatory pre-cutoff), `build_readiness_report()`.
- New `scripts/research/run_v5_shadow_readiness.py`: preflight (verify config+parents, stream R6/rating frames, availability, report, optional replay, plan) + evidence-bound apply (replay loader, idempotency guard, partial-prefix rejection, compact write, manifest last) + `--replay` mode.
- Verified live: complete fixture → `ready`; 2026W4 fixture → `blocked` (no schedule rows, no team states).

### Task 3 — Frozen algorithm replay proof
- `replay_frozen_forecast()` (earlier-only fits, cutoff-season enforcement, optional reference-digest proof) + `perturbation_invariance_proof()` in `shadow.py`; `--replay` mode runs double-replay byte-identity + perturbation proof in preflight.
- 8 function tests: ready/blocked matrices, post-cutoff rejection, neutral fallback, determinism, reference binding, cutoff enforcement, perturbation invariance.

## Files Modified
- `src/cks_picks_cfb/data/data_first_shadow_v1.py` — new
- `src/cks_picks_cfb/data/schema_contracts.py` — shadow import + `_SHADOW_SCHEMAS` + lookup branch
- `src/cks_picks_cfb/forecast/shadow.py` — new
- `scripts/research/run_v5_shadow_readiness.py` — new
- `conf/research/data_first_football_v1/shadow_v1.yaml` — new
- `tests/test_v5_shadow_readiness.py` — new (15 tests)
- `docs/plans/2026-09-17/04-v5-05a-readiness-and-replay.md` — Draft → Approved → In Progress
- `session_logs/2026-09-17/10-v5-05a-readiness-and-replay.md` — this log

## Validation
- [x] Focused 05A suite — 15 passed warnings-as-errors
- [x] Adjacent forecast suites — 32 passed warnings-as-errors
- [x] `contracts/validation.py` + `make contracts-check` — passed
- [x] `ruff format` (touched files) + `ruff check .` — clean
- [x] `mkdocs build --quiet` — clean
- [x] CLI `--help` + `py_compile` — clean
- [x] `git diff --check` — clean
- [ ] Full warning-as-error suite — 980 passed, **1 pre-existing failure** (see Amendments)
- [ ] Task 4 Preview certification — pending user commit

## Amendments and Blockers

**Pre-existing failure (not caused by this work, not in scope to fix):**
`test_all_v5_contracts_are_linked_with_accurate_lifecycle[04-v5-forecast-bridge-and-fitting-window.md]` asserts umbrella-04 status == `Approved`, but the uncommitted worktree (from the prior 04B session, predating this task) flips it to `Implemented` with checked DoD boxes. The test reads only `docs/plans/2026-09-13/`; this session's sole change there is umbrella-05's appended section (status still `Approved`). Amending authority-test lifecycle semantics belongs to Sol planning (contract-00 territory), so it is reported, not silently fixed. Task 4 validation must record this same single failure.

**Task 4 blocked on user commit:** `--apply` requires a clean worktree and `--expected-code-sha` matching HEAD. Certification commands for the next session:
```bash
git add -A && git commit -m "feat(research): implement V5-05A readiness validation and frozen replay"
SHA=$(git rev-parse HEAD); SHORT=$(git rev-parse --short HEAD)
CUTOFF=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
EVIDENCE_DIR="$(mktemp -d)"
PYTHONPATH=.:src uv run python scripts/research/run_v5_shadow_readiness.py \
  --run-id shadow-v1-$(date -u +%Y%m%d)-$SHORT-05a --expected-code-sha $SHA \
  --environment preview --as-of $CUTOFF \
  --candidate-manifest-uri artifacts/research/data-first-football-v1/forecasts/runs/forecast-v1-20260917-4600ddd-04b/forecast-manifest.json \
  --rating-manifest-uri artifacts/research/data-first-football-v1/possession-v1/ratings/runs/possession-v1-ratings-20260917-d029526-cert/retained-rating-manifest.json \
  --measurement-manifest-uri artifacts/research/data-first-football-v1/possession-v1/measurements/runs/possession-v1-measurements-20260915-18fb0aa-r6/measurement-manifest.json \
  --repair-manifest-uri artifacts/research/data-first-football-v1/repair/v2/runs/repair-v2-20260909T1417Z/repair-manifest.json \
  --season 2026 --week 4 --replay > "$EVIDENCE_DIR/preflight.json"
# review, then apply with --apply --preflight-evidence, then idempotent repeat
```

## Handoff Notes
- **Resume at:** After user commits, run 05A certification (Task 4) in a fresh session, then close 05A Implemented and open 05B authorization.
- **Watch out for:** Do not amend the failing authority test or revert umbrella-04 as a drive-by — both need explicit user/Sol direction. 05B/05C must not execute before 05A certifies. Expected certification verdict: `blocked` (no 2026 pipeline); replay digest establishes the frozen-proof baseline.

**tags:** ["v5", "contract-05", "readiness", "shadow-operations", "terra"]
