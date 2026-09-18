# Session: V5-05C Rehearsal, Verification, and Runbook Implementation (Terra)

## TL;DR
- **Worked On:** Contract 05C Tasks 1–4: independent shadow verifier, diagnostic rehearsal, readiness refresh, runbook, Preview certification.
- **Outcome:** All tasks completed and certified in Preview:
  - Rehearsal run `shadow-v1-20260918-6dc87e0-05c` (preflight 431.6s, apply, independent verify, idempotent repeat).
  - Independent verifier confirms the rehearsal plus the certified 05A/05B artifacts end-to-end from source datasets.
  - Real-season 2026 W4 readiness re-verified `blocked`; umbrella V5-05 closed.
- **Plan Contract:** `docs/plans/2026-09-17/06-v5-05c-rehearsal-verification-runbook.md` (Implemented)
- **Approval / Status:** Draft approved as-is by user 2026-09-18 (`276fafc`). Code checkpoint committed by user (`6dc87e0`).
- **Blockers:** None.
- **Next:** User executes the certified-evidence documentation commit checkpoint. Then Contract 06 only after the 2026 measurement/rating pipeline extension exists.

## Context and Decisions
- Entry gate verified: 05A/05B Implemented with certified Preview artifacts; all six schemas registered; `shadow_v1.yaml` sealed; clean worktree.
- Boundary rule: `shadow_verification.py` imports only constants/schemas, generic lake readers, phase2d signing, schema contracts, storage. Enforced by an AST import-boundary test. The rehearsal runner (producer side) may import producer modules; the verifier never does.
- The 05A applied manifests carry no replay digest (preflight-only evidence); freeze/score manifests are unsigned by 05B design. The verifier handles both as built — observation, not an amendment.
- Live 2026 readiness remains `blocked` (structural: certified parents contain no 2026 rows). A verified `blocked` verdict is the contractually complete outcome.

## Work Completed

### Task 1 — Independent shadow verifier
- `src/cks_picks_cfb/forecast/shadow_verification.py`: verifier-owned reconstruction of readiness (all six sources + verdict from the certified parent chain), replay evidence (structural: digest/byte-identity/perturbation claims), freeze timing/population/digest/identity/predictions (own diagnostic-rule re-derivation), scores (stabilization + own error/CRPS/coverage/MAE math), counter (no-double-count + diagnostic-never-qualifies), rehearsal records (permanent `diagnostic_only`, case totals, replay digest, verifier ref). Signed verifier manifest writer with immutable-collision idempotency.
- `scripts/research/verify_v5_shadow.py` CLI (`--manifest-uri`, `--expected-code-sha`, `--environment preview`, source-URI overrides, `--write-manifest`).
- `tests/test_v5_shadow_verification.py`: 26 tests (AST boundary, producer-perturbation, tampered bytes, wrong parent, identity mismatch, stabilization, evaluation perturbation, counter total, diagnostic qualifying, readiness ready/blocked, replay evidence, rehearsal cases, verifier-manifest idempotency/collision).

### Task 2 — Diagnostic rehearsal
- `scripts/research/run_v5_shadow_rehearsal.py`: mainline (readiness on the pinned 2025 W10 slate, frozen replay with perturbation proof, freeze validation, stabilized scoring, diagnostic counter) + six negative cases; `diagnostic_only` on every output; evidence-bound apply with the terminal rehearsal manifest written last; `--season-range`, historical parent refs, `--negatives` selection.
- `tests/test_v5_shadow_rehearsal.py`: 11 tests (all negatives dispense correctly, gate-removal detected, correction counted once, ledger reset, diagnostic permanence, apply/idempotency/partial-prefix, preflight-evidence validation).

### Task 3 — Readiness report, runbook, closure docs
- Read-only re-run of the 05A readiness logic for 2026 W4 (cutoff 2026-09-18T13:43:12Z): `blocked` (no schedule rows, no team states for 2026). Nothing written.
- Refreshed `docs/research/2026-09-17-v5-live-readiness-assessment.md` (verified-refresh section; historical sections preserved).
- New `docs/ops/v5_shadow_runbook.md` (pinned refs, five CLIs, four sequences with exact commands, recovery, counter rules, Contract 06 handoff) + mkdocs nav entry.

### Task 4 — Phase 05C certification execution
- Preflight: 431.6s; readiness `ready` (historical slate); replay digest `e4d798bac7d3104e…` byte-identical to the certified 05A proof; freeze 45/0 at T-2h; score 45 (MAE 7.0); qualifying 0; 7/7 cases.
- Apply: publication-plan first, rehearsal dataset, terminal `rehearsal-manifest.json` last. Rerun → `already_applied`.
- Independent verify: rehearsal confirmed + signed verifier manifest; certified 05A readiness (`blocked`, six sources), 05B freeze (45 paired, digest `16ae8420df3a…`), 05B score (MAE 7.0/51.0, 1 slate) all reconstructed from source datasets with the final code.
- R2 inventory: 16 objects under the Preview shadow prefix only; no production/Neon/web writes.

## Amendments
- **Amendment 1:** `iter_partitioned_dataset` part-key check is set-based, not order-based. The writer stores part partitions with canonically sorted keys, which made the certified 05B `shadow_evaluation` (keys `season, week, outcome_version`) unreadable via the generic reader. No stored bytes/digests/identities change; all alphabetical datasets behave identically.
- **Amendment 2:** verifier loads the readiness population through the compact-or-partitioned generic loader (R6 population is partitioned). No stored bytes/interfaces change.
- **Authority-test lifecycle rule:** V5 lifecycle test accepts umbrella progression (`04-` may be Implemented; umbrella contracts may move Approved → In Progress → Implemented); index 04 row corrected to Implemented. Fixes a pre-existing failure on clean `276fafc`; statuses and index rows remain cross-checked.

## Files Modified
- `src/cks_picks_cfb/forecast/shadow_verification.py` — new verifier module
- `scripts/research/verify_v5_shadow.py` — new verifier CLI
- `scripts/research/run_v5_shadow_rehearsal.py` — new rehearsal runner
- `tests/test_v5_shadow_verification.py`, `tests/test_v5_shadow_rehearsal.py` — new suites (37 tests)
- `src/cks_picks_cfb/data/lake.py` — Amendment 1 reader repair
- `tests/test_data_first_documentation_authority.py` — lifecycle-rule repair
- `docs/ops/v5_shadow_runbook.md` — new runbook; `mkdocs.yml` nav entry
- `docs/research/2026-09-17-v5-live-readiness-assessment.md` — verified refresh
- `docs/plans/2026-09-13/05-v5-prospective-readiness-and-shadow-tooling.md` — umbrella closure
- `docs/plans/2026-09-17/06-v5-05c-rehearsal-verification-runbook.md` — Implemented + certification record
- `docs/plans/index.md` — 04/05/05C rows; `docs/planning/data-first-football-forecasting-roadmap.md` — 03/05 rows + checkpoint
- `session_logs/2026-09-18/02-v5-05c-rehearsal-verification-runbook.md` — this log

## Validation
- [x] Full suite 1058 passed, 2 skipped, warnings-as-errors (re-run after doc/test edits below)
- [x] `uv run ruff check .` — clean
- [x] `uv run python contracts/validation.py` + `make contracts-check` — pass
- [x] `uv run mkdocs build --quiet` — clean
- [x] `git diff --check` — clean
- [x] Certification: preflight/apply/verify/repeat under lineage `6dc87e0`; R2 Preview-only inventory

## Handoff Notes
- **Resume at:** User commits the docs checkpoint below; then Contract 06 is gated on the 2026 measurement/rating pipeline extension (separate contract).
- **Watch out for:** The six qualifying pre-frozen slates for Contract 06 do not yet exist (counter holds one diagnostic-certified 05B slate only). Diagnostic rows never count. Week 3 close is pending in production (unrelated to V5).
- **Commit command proposal:**
  ```bash
  git add \
    src/cks_picks_cfb/forecast/shadow_verification.py \
    docs/plans/2026-09-17/06-v5-05c-rehearsal-verification-runbook.md \
    docs/plans/2026-09-13/05-v5-prospective-readiness-and-shadow-tooling.md \
    docs/plans/index.md \
    docs/planning/data-first-football-forecasting-roadmap.md \
    docs/ops/v5_shadow_runbook.md \
    docs/research/2026-09-17-v5-live-readiness-assessment.md \
    mkdocs.yml \
    session_logs/2026-09-18/02-v5-05c-rehearsal-verification-runbook.md
  git commit -m "docs(v5): certify V5-05C rehearsal, verification, and runbook in Preview"
  ```
- **Certified URIs:**
  - Rehearsal Manifest: `artifacts/research/data-first-football-v1/possession-v1/shadow/runs/shadow-v1-20260918-6dc87e0-05c/rehearsal-manifest.json`
  - Verifier Manifest: `artifacts/research/data-first-football-v1/possession-v1/shadow/runs/shadow-v1-20260918-6dc87e0-05c/verification/verifier-manifest.json`

**tags:** ["v5", "shadow", "verification", "rehearsal", "preview", "certification", "contract-05c"]
