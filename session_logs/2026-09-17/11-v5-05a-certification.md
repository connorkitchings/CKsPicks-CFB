# Session: V5-05A Certification Execution (Terra)

## TL;DR
- **Worked On:** Contract 05A Task 4 — Phase 05A Preview certification
- **Outcome:** Full preflight/apply/verify/repeat cycle passed. Certified Preview artifact `shadow-v1-20260917-cd07d8b-05a` with verified `blocked` readiness and frozen-replay proof.
- **Plan Contract:** `docs/plans/2026-09-17/04-v5-05a-readiness-and-replay.md` (Implemented)
- **Approval / Status:** Contract authorized 2026-09-17; Tasks 1–3 committed prior session (`0b66657`→`cd07d8b`); Task 4 certification completed this session.
- **Blockers:** Pre-existing umbrella-04 lifecycle test failure (not in scope).
- **Next:** User commits evidence checkpoint → approve and implement 05B (shadow freeze, scoring, evidence ledger).

## Context and Decisions
- Entry: clean worktree on `main` at `cd07d8b`, Tasks 1–3 committed, R2 credentials verified.
- Certification run ID: `shadow-v1-20260917-cd07d8b-05a`
- Used `--as-of 2026-09-17T18:36:21Z`, `--season 2026 --week 4`, `--replay`.
- Readiness verdict: **blocked** (as expected). Two unavailable sources:
  - `schedule`: "no schedule rows for 2026 week 4"
  - `team_states`: "no team states for 2026"
- Four sources available (`pre_cutoff`): candidate, completed_games, priors, scoring.

## Work Completed

### Task 4 — Phase 05A certification execution

1. **Preflight (dry run):** ~433s. Streamed 142 adjusted_history partitions (23.5M rows), 10 scoring_events partitions (78K events), 270K priors, 1.07M team_states. Zero warnings. Readiness built: 6 rows, overall `blocked`. Replay proof SHA `e4d798bac7d3104e07830ff782cbfb43aef07076caf760a93b42dfefc9ff123a`. Identity SHA `b729ae95a2acc8f84705754875dca7c333fa9c4d105dbf9e3434f870417bea7f`.

2. **Evidence-bound apply:** ~429s. All parent chains verified (forecast `e28b278b`, rating `7568c910`, measurement `449cdebc`, repair `b55af0dd`). Readiness record and manifest written to R2 Preview at `artifacts/research/data-first-football-v1/possession-v1/shadow/runs/shadow-v1-20260917-cd07d8b-05a/shadow-manifest.json`. `already_applied: false`, `state: applied`.

3. **Idempotent repeat:** Instant. `state: already_applied`, zero writes. Same manifest URI returned.

### Certified artifact identity
- **Run ID:** `shadow-v1-20260917-cd07d8b-05a`
- **Code SHA:** `cd07d8b5e962dc9ec2d3a0fc9bc57712e0dd207d`
- **Identity SHA:** `b729ae95a2acc8f84705754875dca7c333fa9c4d105dbf9e3434f870417bea7f`
- **Config SHA:** `4667b0e93e63825b4e551b9e55fbb724af6a6caefa34e163d8f28dccdda3561f`
- **Readiness SHA:** `bb5fb8d97c45082a92b6e1535c19f29f13061aabe2d3d13354152d1b09a647a0`
- **Replay SHA:** `e4d798bac7d3104e07830ff782cbfb43aef07076caf760a93b42dfefc9ff123a`
- **Manifest:** `artifacts/research/data-first-football-v1/possession-v1/shadow/runs/shadow-v1-20260917-cd07d8b-05a/shadow-manifest.json`
- **`production_activation_authorized: false`**

## Files Modified
- `docs/plans/2026-09-17/04-v5-05a-readiness-and-replay.md` — In Progress → Implemented, DoD checked
- `docs/plans/index.md` — 05A row updated to Implemented with certified artifact
- `session_logs/2026-09-17/11-v5-05a-certification.md` — this log

## Validation
- [x] Preflight: zero warnings, readiness plan complete, replay byte-identical
- [x] Apply: evidence-bound write succeeded, `applied` state
- [x] Idempotent repeat: `already_applied`, zero writes
- [x] Focused 05A test suite: 15/15 passed warnings-as-errors
- [x] `ruff check .` — clean
- [x] `contracts/validation.py` — passed
- [x] `mkdocs build --quiet` — clean
- [x] `git diff --check` — clean (pending commit)

## Amendments and Blockers
- Pre-existing umbrella-04 lifecycle test failure unchanged (not in scope).
- No amendments to 05A contract.

## Handoff Notes
- **Resume at:** User commits evidence checkpoint. Then approve and implement 05B (shadow freeze, scoring, evidence ledger). 05B's entry gate is met: 05A Implemented with committed SHA and reviewed deterministic preflight evidence.
- **Watch out for:** 05B/05C must not execute before prior-phase certification. The readiness assessment doc is uncommitted planning evidence — Terra preserves and refreshes it in 05C.

**tags:** ["v5", "contract-05", "certification", "shadow-operations", "terra"]
