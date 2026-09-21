# Session: V5 2025 Market-Line Diagnostic Study (Contract 02 Implementation)

## TL;DR
- **Worked On:** Terra execution of `docs/plans/2026-09-21/02-v5-2025-market-line-diagnostic-study.md`.
- **Outcome:** Contract 02 is fully **Implemented**. Preview run `market-diagnostic-2025-v1-20260921` published signed evidence (manifest SHA `e879b6b4...`), passed independent re-read (`verified: true`) and idempotent repeat (`already_applied`). Report published. Headline diagnostic: on the 762-game 2025 intersection, provider-recorded lines beat conditional V5 forecasts — margin MAE 11.846 vs 14.167 (Δ −2.32, CI [−2.97, −1.72]); total MAE 12.366 vs 13.280 (Δ −0.91, CI [−1.32, −0.49]). Closer counts: margin 447–315, total 422–340 for the market.
- **Plan Contract:** `docs/plans/2026-09-21/02-v5-2025-market-line-diagnostic-study.md` (Status: Implemented)
- **Approval / Status:** User authorized Terra execution ("proceed to terra execution"). All 8 DoD items pass.
- **Blockers:** None.
- **Next:** Plan the Contract 11 sub-contract decomposition (11B ratings-from-r9 → 11C bridge + through-2025 fit → 11D verification closing Findings 002/004). The staged Odds API authentic-line backfill remains available only if the program wants timestamped 2025 quotes later.

## Context and Decisions
- Reconciliation found all contract assumptions true: 12A loader/SHA pins reusable; replay `input_refs.json` discoverable at `artifacts/preview/pipeline-runs/replay-2025-v4-w{1..16}/`; `market_snapshots` schema (`spread_line`, `total_line`) with checksum-verified `lake.read_dataset`; quarantined catalog state asserted via read-only SELECT (no catalog writes).
- Market identity pinned from immutable replay refs, unanimous 16/16: version `e4061aab93b1e667a34ce780`, content SHA `6df93ed5...`, schema `market_snapshots_v1`, policy `consensus_then_median_v1`, catalog state `quarantined`.
- Sign convention validated before metrics: r(pred, market-implied)=0.656, r(actual, pred)=0.457, r(actual, market)=0.676 — all gates pass.
- Population: 934 V5 games ∩ 762 lined games = 762/762 per target (both targets fully lined); 172 excluded games per target (unlined, FBS-FCS-heavy) with IDs recorded.
- Known inherited quirk (shared with 12A): published manifests record `code_sha: "unknown"` because the shared publication `ROOT` resolves one directory above the repo (`parents[4]` instead of `parents[3]`), so `git rev-parse` fails into the `except` branch. Left as-is: fixing it post-apply would require a fresh run_id for a metadata-only gain, and substantive guarantees (pinned inputs, checksums, deterministic recompute, independent verifier) all hold. A future cleanup may correct the `ROOT` constant in both publication modules; it must not alter any published artifact.

## Certified Evidence
- **Run ID:** `market-diagnostic-2025-v1-20260921`
- **Diagnostic URI:** `artifacts/research/data-first-football-v1/market-diagnostics/v1/runs/market-diagnostic-2025-v1-20260921/market-diagnostic.json` (raw SHA `60f9c31c...`)
- **Manifest URI:** `.../diagnostic-manifest.json` (raw SHA `e879b6b4b5fec7a68bf8784ee4cf05db246d614277806dd553c7c06a79be2b81`)
- **Entry identities:** 11A pins (raw `5a7e7d48...`, canonical `7ce47863...`, record `7ee050b4...`); market version `e4061aab93b1e667a34ce780` / SHA `6df93ed5...`; replay ref agreement unanimous 16/16; catalog `quarantined`.
- **Report:** `docs/research/2026-09-21-v5-2025-market-line-diagnostic-report.md`
- **Headline deltas (market − V5 MAE, + favors V5):** margin −2.321 [−2.967, −1.720]; total −0.914 [−1.323, −0.491]. Only total/stage-2 is near parity (+0.094, CI straddles zero). Edge means: margin +1.38, total +2.57 (V5 forecasts run higher than lines on average).

## Work Completed
- Implemented `src/cks_picks_cfb/forecast/market_diagnostic.py` (entry gates, sign validation, population, paired metrics with seeded bootstrap, report rendering).
- Implemented `src/cks_picks_cfb/forecast/market_diagnostic_publication.py` (preflight/apply/verify mirroring the 12A pattern).
- Implemented `scripts/research/run_v5_market_diagnostic.py` CLI (preflight/apply/verify; clean-worktree guard on apply).
- Implemented `tests/test_market_diagnostic.py` (19 tests: positive, negative fail-closed, determinism, labeling).
- Executed Preview preflight → user committed code → apply (`applied`, `verified: true`) → repeat (`already_applied`) → verify (`verified: true`).
- Rendered and saved the diagnostic report with mandatory `diagnostic_comparison_only` labeling.
- Updated contract to Implemented (DoD 8/8) and `docs/plans/index.md`.

## Files Modified
- `src/cks_picks_cfb/forecast/market_diagnostic.py` — created
- `src/cks_picks_cfb/forecast/market_diagnostic_publication.py` — created
- `scripts/research/run_v5_market_diagnostic.py` — created
- `tests/test_market_diagnostic.py` — created
- `docs/research/2026-09-21-v5-2025-market-line-diagnostic-report.md` — created
- `docs/plans/2026-09-21/02-v5-2025-market-line-diagnostic-study.md` — In Progress → Implemented, DoD checked
- `docs/plans/index.md` — row updated to Implemented with headline result
- `session_logs/2026-09-21/05-v5-2025-market-line-diagnostic-study.md` — this log

## Validation
- [x] `uv run pytest tests/test_market_diagnostic.py` — 19 passed
- [x] `uv run pytest -q` (full suite) — 1212 passed, 2 skipped
- [x] `uv run ruff check` + `ruff format` on touched paths — clean
- [x] Preflight exit 0 (~18s); apply exit 0 (`applied`); repeat (`already_applied`); verify (`verified: true`)
- [x] `uv run python contracts/validation.py` — passed
- [x] `uv run mkdocs build --strict --quiet` — passed
- [x] `git diff --check` — clean

## Amendments and Blockers
- None (no scope/interface/acceptance change). The `code_sha: unknown` quirk is documented above as a known inherited limitation, not an amendment.

## Handoff Notes
- **Resume at:** Sol planning session for the Contract 11 decomposition (11B/11C/11D) against the r9 measurement parent — the critical path to closing Findings 002/004.
- **Watch out for:** This study changes nothing about readiness; its permitted use stays `diagnostic_comparison_only`. Do not feed its deltas into selection or Contract 12.

**tags:** ["v5", "contract-02", "market-diagnostic", "publication", "verified"]
