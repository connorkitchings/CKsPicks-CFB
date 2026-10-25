# Contract: CI speed and stability cleanup

- **Status:** Implemented
- **Created:** 2026-10-23
- **Approval source:** Owner approved the corrected plan and asked for it to be implemented in this session.
- **Implementation log:** `session_logs/2026-10-23/02-ci-speed-and-stability.md`
- **Commit policy:** Single branch `connorkitchings/ci-speed-stability` off `dev`, merged through a PR whose CI run supplies the timing comparison. Owner executes Git operations.

## Goal and acceptance

Shorten the CI critical path (`general`, then `web`) and remove Playwright hydration flakes. Complete means `general` runs with `--dist worksteal`, Playwright runs against a fixture production build with an explicit hydration marker, and per-job timings are compared against baseline run `39854431096` (`general` 5m54s, `web` 4m03s). Combined coverage stays at or above 60%.

## Phases

1. **Workflow-only (`.github/workflows/ci.yml`):** `--dist worksteal` for `general`; drop `fetch-depth: 0`; single-thread BLAS env on `general` and `ratings` (keep only if timing does not regress and SHA tests pass).
2. **Repeated tournament work (test-only, done in PR #8):** share the preflight/apply and unperturbed tournament setup in `tests/test_possession_rating_verification.py` and `tests/ratings/test_possession_rating_materializer.py`. Assertions unchanged. `general` fell from 5m19s to 3m20s in CI.
3. **Web stability:** a separate fixture-mode build step; `next start` under `CI`; `HydrationMarker` plus `gotoHydrated` replacing `networkidle` waits; flake gate `--repeat-each=20` with 0 retries; audit triage.
4. **Backlog (separate contracts):** web coverage floor, component tests, visual regression, degraded-state pages, temporal-integrity inventory.

## Amendments

- Audit triage: `npm audit --audit-level=high` and `pip-audit` both exit 0 on the current lockfiles, so no audit change is made.
