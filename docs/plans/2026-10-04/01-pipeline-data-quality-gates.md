# Pipeline Data-Quality Gates

- **Status:** Approved (2026-10-04). Tasks 1-6 delivered on `dev`; **not yet marked Implemented** because the deferred items in Amendment 3 are open and need a user decision
- **Created:** 2026-10-04
- **Planner:** Claude (planning chat, with the user)
- **Approval source:** The user chose a separate contract parallel to Window 1 covering ingestion, Silver/Gold, the publish boundary and the web read side, then reviewed the draft and approved it on 2026-10-04 with three stipulations below.
- **Stipulations:**
  1. **Strict sequencing:** Tasks 1–6 start only after the Window 1 code is completed, verified and committed. Task 4 edits `publish_to_db.py` and must not collide with active Window 1 changes.
  2. **Web row parsing (Task 5):** parsers consume `rowsOf()` / `existsFrom()` from `web/src/lib/db-result.ts` (the Neon HTTP driver returns `{ rows }`) and must work under `CFB_UI_TEST_MODE=1`.
  3. **Survey verification:** re-verify the unverified survey entry points (file and line references marked agent-reported) before starting Tasks 2 and 3.
- **Implementation log:** Pending
- **Commit policy:** Separate plan commit. Implementation commits per task, each independently revertible.

## Goal

Make bad data fail loudly and leave evidence, at every stage, before it can reach the site. Today the checks that exist are scattered, mostly manual, and often unrecorded. The Window 1 investigation found defects (non-monotone score streams, zero-filled PPA, missing venue city, a served Away-spread line ordering that its own verifier shared) that stayed invisible because no check compared the output with the source or with an independent rule.

Observable success:

- Every pipeline run emits one machine-readable quality receipt with named checks, severities and counts.
- One entry point (`make data-quality`) runs the checks that apply to a stage and exits non-zero on any blocking failure.
- CI runs the data-free checks; operators run the data-bound checks and keep the receipts.
- A shape or null change in the Neon rows the web app reads shows an explicit unavailable state instead of rendering wrong numbers.

## Current State

Source: a read-only survey of existing checks. Line references are **agent-reported and not re-derived**, except where marked verified (re-checked this session).

- **Schema contracts:** hand-rolled `DatasetSchema`/`validate_frame` in `data/schema_contracts.py`; called on the lake write path (`data/lake.py:219-222`, verified).
- **Reconciliation:** `data/reconciliation.py` classifies score-versus-box conflicts and `require_reconciled` raises. Callers are only the phase2c research build and `scripts/pipeline/build_team_game_dataset.py` (verified).
- **Orphaned validator:** `utils/validation.py` (`DataValidationService`) is referenced only by its own tests (verified).
- **Audit toolkit:** `data/evidence_audit.py` and `audit/` (lineage, signatures, metric recompute, immutable audit writer). Strong but aimed at certification of research artifacts, not routine runs.
- **Operational audits:** `make audit-data` (feature frame, catalog, exact markets), `scripts/pipeline/audit_market_quote_coverage.py` (manual), `check_prepared_week.py` freshness.
- **Publish:** `make contracts-check` is static (schema/SQL/TS sync, migrations, logos); it never inspects data. `require_venue_cities` runs at publish (verified at `publish_to_db.py:868`) and only under `--require-city` in the venue publisher.
- **Web:** no runtime parser for Neon rows; tests cover the publication boundary with fixtures.
- **Not found:** Bronze checks for freshness, row counts, nulls, ranges or uniqueness on CFBD and Odds API pulls; any data check in CI.

Contract 04 "Prevention Gates" status (agent-reported): gate 1 partial, gate 2 partial, gate 3 implemented, gate 4 partial, gate 5 partial to implemented, **gate 6 missing**.

## Proposed Approach

One small shared library, thin per-stage check modules, one receipt format. Reuse what exists (`validate_frame`, `reconciliation`, `ImmutableAuditWriter`, `ops` CLI) rather than add a framework dependency.

- **Check result:** `{check_id, stage, severity: block|warn|info, scope, observed, expected, passed, detail}`. A run is blocked if any `block` check fails.
- **Receipt:** canonical JSON with run identity, code SHA, input identities and the check list, written through the existing immutable writer. Receipts are evidence, not logs: never overwritten.
- **Severity policy:** only checks that can establish a defect block. Statistical sanity checks (distribution drift) warn.
- **Where it runs:** each stage's existing entry point calls its checks before writing; `make data-quality STAGE=… YEAR=… ENV=…` runs them standalone through `python -m cks_picks_cfb.ops`.
- No third-party validation framework in v1: the existing hand-rolled contracts already cover schema, and a new dependency would split the conventions.

## Scope

### Included

- Shared check/receipt library and the `ops data-quality` command with a Make target.
- Bronze ingestion checks, Silver/Gold invariants, publish-boundary assertions, web read-side parsing.
- Contract 04 gate 6 (earlier-game refresh pinning) and persistence of gates 2 and 4 as receipts.
- CI job for the data-free checks.
- Retiring or adopting the orphaned `utils/validation.py` (decision in Task 1).

### Excluded

- Window 1/Window 2 behavior changes. This contract adds checks; it does not change selection, scoring, ratings or serving semantics.
- New model features or imputation.
- A third-party data-quality platform.
- Preview/production writes. Applying receipts to environments stays user-run.
- Monitoring/alerting infrastructure beyond the notifier already in `ops/notifier.py`.

## Affected Components and Contracts

- New: `src/cks_picks_cfb/quality/` (check types, receipt writer, registry), `ops` subcommand, Make target, CI workflow step.
- Edited entry points: CFBD and Odds API fetchers, Silver builders, `publish_to_db.py`, `publish_game_venues.py`, `score_to_db.py`, `build_team_game_dataset.py`.
- Web: `web/src/lib/` row parsers and the loaders in `queries.ts`/`v5.ts`/`matchup.ts`; unavailable-state components.
- Docs: a checks catalog under `docs/data/`, known-issues register, status.

## Implementation Tasks

### Task 1 — Shared check library, receipts, CLI

**Files:** new `src/cks_picks_cfb/quality/{__init__,checks,receipt,registry}.py`; `src/cks_picks_cfb/ops/__main__.py`; `Makefile`; tests.

**Changes:**
- Define the check result type, severity policy, registry and receipt writer on top of the existing canonical JSON and immutable writer.
- Add `ops data-quality --stage {ingest,silver,gold,publish} --year --environment`.
- Decide `utils/validation.py`: delete if nothing in the new library needs it, otherwise port the manifest row-count and duplicate-partition checks into the registry.

**Acceptance criteria:**
- A failing `block` check produces a non-zero exit and a receipt that names it; a passing run produces a receipt with every check listed.
- Receipts are deterministic for identical inputs and refuse to overwrite a different existing receipt.

**Validation:** unit tests for severity, exit codes, determinism, collision refusal.

### Task 2 — Ingestion (Bronze) checks

**Files:** `scripts/data/fetch_odds_api_market_quotes.py`, the CFBD fetch/capture modules (`data/plays.py`, `games.py`, `game_stats.py`, `history_*capture.py`), quality check modules.

**Changes:**
- Per pull: row count against the expected schedule (games, plays per completed game, drives), key uniqueness, required-column presence, null rates and numeric ranges for fields that feed measurements (score, period, clock, yards, PPA presence), capture timestamp and freshness against the cutoff.
- Record PPA missingness at capture, before any compatibility fill.
- Odds API: persist unmatched events, event-to-game match status, per-quote price presence (actual versus absent) so gate 4 has a stored fact.
- Pin each capture by URI, timestamp and SHA-256 in the receipt.

**Acceptance criteria:**
- A truncated pull, duplicate keys, or a week with games but no plays blocks the run.
- Price provenance is stored per quote, not inferred later.

**Validation:** fixture-driven tests including truncated and duplicated captures; a read-only dry run against Preview R2.

### Task 3 — Silver/Gold invariants and gate 6

**Files:** `data/reconciliation.py`, `data/team_stats.py`, `features/byplay/enrichment.py`, `ratings/possession_measurements.py`, `scripts/pipeline/build_team_game_dataset.py`, quality modules.

**Changes:**
- Run score-versus-box reconciliation in the standard Silver build path, not only research builds, and record each comparison in the receipt (gate 1).
- Assert invariants after each build: scores monotone within a game or flagged, drive numbering contiguous, eligible-play and possession counts consistent, points identity (offense, non-offense, excluded, overtime, final) holds or the game is marked unusable (gate 5), missing PPA stays distinguishable from zero.
- Gate 6: a refresh of a completed game must carry a pinned capture, version, timestamp and hash before it can enter a new measurement build; unpinned refreshes block.

**Acceptance criteria:**
- Each known Window 1 defect has a regression check that fails on the old behavior.
- An unpinned earlier-game refresh blocks.

**Validation:** unit tests on constructed defects; run against the pinned October investigation inputs read-only and compare counts with the recorded findings.

### Task 4 — Publish-boundary assertions

**Files:** `scripts/pipeline/publish_to_db.py`, `publish_game_venues.py`, `score_to_db.py`, `publish_matchup_data.py`, quality modules.

**Changes:**
- Before any Neon write: key uniqueness, required non-null fields, numeric ranges (spreads, totals, probabilities), game coverage against the eligible FBS schedule (gate 2 persisted), venue city for every published game (gate 3, always on, not opt-in), selected quote consistent with the best-quote rule and tie rule.
- After the write: read back counts and key sets and compare with the payload.
- Write the receipt to the same location as the release evidence.

**Acceptance criteria:**
- A payload with a duplicate key, a null required field, or a missing scheduled game does not write.
- Read-back mismatch fails the run and is recorded.

**Validation:** unit tests with a recording cursor; a real Preview rehearsal by the user before any production use.

### Task 5 — Web read side

**Files:** `web/src/lib/` (row parsers and shared types), `queries.ts`, `v5.ts`, `matchup.ts`, page components, tests.

**Changes:**
- Parse rows returned from Neon at the loader boundary into typed, validated records. On a shape or null-contract violation, return an explicit unavailable state for that section and log the violation; never coerce to zero.
- Keep existing fixtures and publication behavior.

**Acceptance criteria:**
- A row missing a required field renders the section's unavailable state and does not throw the page.
- No parser changes any valid value.

**Validation:** unit tests in `npm run test:publication`, lint, typecheck, build. Playwright is user-run.

### Task 6 — CI wiring, catalog and issue register

**Files:** `.github/workflows/ci.yml`, `Makefile`, `docs/data/` checks catalog, `docs/data/known_issues.md`, `docs/status.md`.

**Changes:**
- CI runs the data-free checks (check registry integrity, fixture-based invariant tests, web parsers). Data-bound stages stay operator-run, and their receipts are referenced from status.
- Document every check: id, stage, severity, why it exists, which defect it prevents.

**Acceptance criteria:** CI fails on a removed or unregistered check; the catalog and registry agree.

**Validation:** `make all`, docs build.

## Testing Strategy

- Unit tests for every check with a passing case and a constructed failing case.
- Regression checks tied to named defects from the October 3 investigation.
- Read-only dry runs on Preview R2 and the pinned investigation inputs; no writes without a user-run session.
- Web unit, lint, typecheck, build; Playwright run by the user.

## Risks and Edge Cases

- **False blocks.** A too-strict range or count check can stop a legitimate run. Start new checks at `warn`, promote to `block` only after a clean review of real receipts.
- **Overlap with contract 04 / Window 2.** Window 2's metric ledger and null semantics will define new invariants. This contract provides the receipt mechanism; Window 2 registers its checks into it. Avoid duplicate definitions.
- **Window 1 interaction.** Task 4 touches `publish_to_db.py`, which has uncommitted Window 1 changes. Start only after Window 1's code commit lands.
- **International venues** may have no state; the city check must keep allowing city-only records.
- **Frozen records.** No check may rewrite or invalidate original frozen predictions, quotes or grades; failures are reported, not repaired.
- **Cost.** Bronze row-count expectations need the schedule snapshot; reuse the pinned schedule, not a fresh pull.

## Definition of Done

- [ ] All tasks and acceptance criteria complete.
- [ ] Required validation passes; Preview dry runs reviewed.
- [ ] Checks catalog, issue register, status and session log updated.
- [ ] Plan status updated to `Implemented`.

## Amendments

### Amendment 1: Task 1 implementation choices (2026-10-04)

**Reason:** Task 1 was started under the user's authorization after Window 1 code landed in `850ca38`.

**Original approach:** add an `ops data-quality` subcommand; decide whether to delete or port `utils/validation.py`.

**Revised approach:**
- The CLI is the standalone `python -m cks_picks_cfb.quality` (`--stage`, `--year`, `--environment`, `--output`, `--list`, `--verify-registry`), with `make data-quality STAGE=… [YEAR=…] [ENV=…]` and `make quality-check` (registry integrity, added to `make all`). Reason: `ops/__main__.py` is about 2,600 lines and routes every command through its resumable state machine, which a stateless check run does not need. Exit codes: 0 pass, 1 a blocking check failed or the registry is invalid, 2 usage.
- Receipts are canonical JSON, content-addressed, deterministic (no clock), refuse to overwrite different bytes, and are written to `artifacts/quality/quality/receipts/<stage>/<id>.json` locally (git-ignored) or through a storage backend.
- `utils/validation.py` (1,701 lines, legacy CSV-partition era, referenced only by its own two test files) is **left in place and not ported**. Nothing in the new library needs it. Deleting it is a separate prune once Tasks 2–3 confirm no check should be ported; recorded here so it is not forgotten.

**Impact:** Task 1 delivers the library, receipt format, CLI and registry integrity check with zero registered data checks. Tasks 2–4 register the real checks. Task 4 stays held until the Preview venue dry run passes and the Window 1 receipt is signed off.

### Amendment 2: Task 4 implementation choices (2026-10-04)

**Reason:** Task 4 was started on the user's authorization after Window 1 was signed off.

**Deviation from "start new checks at `warn`":** the eleven `publish.*` checks register at `block`. They are the contract's own acceptance criteria (a duplicate key, a null required field or a missing scheduled game must not write) and each establishes a structural defect rather than a statistical drift. Calibration on real Preview data (read-only) showed no false blocks: every selected run's prediction count equals the Neon schedule count, null leans are common and allowed, and observed ranges sit well inside the bounds (spread within +/-100, totals 10 to 200, deviations in (0, 60], edges at least 0).

**What is checked:** before any write, `publish_week` builds the exact payload and runs keys, required fields, value ranges, schedule coverage (every game Neon schedules for the week), best-quote consistency (recomputed independently from the frozen quotes: lowest line for Away and Over, highest for Home and Under) and, for `published` runs, venue city. After the writes and inside the same transaction it reads back the prediction keys and the selections (quote, side, point); a mismatch raises before commit, so the transaction rolls back. `publish_game_venues.py` always requires a city for every game when it writes (a dry run only when `--require-city` is given) and reads the venue rows back. `score_to_db.publish_scored_run` reads v2 grades back and recomputes each from the frozen side, point and certified score.

**Operator override:** `publish_to_db.py --allow-partial-slate` lets a run omit scheduled games. It never admits a game outside the schedule and is written into the receipt.

**Consequences to know:**
- The best-quote check recomputes the rule that the October served runs violated: on real stored runs it flags exactly the previously sized wrong-line Away spreads (Week 0: 4 games, Week 1: 14, Week 2: 14, Weeks 3 and 4: none) and passes the Week 1 rehearsal run. Re-publishing any of those legacy runs would now be refused. They are immutable (`frozen`/`scored`) anyway, and their replacement is Window 2 work.
- Week 5 (`p2`): the stored-database reconstruction flags 1 game (0.5 point) and the earlier R2-artifact sizing found 2 (1.0 point). Resolved: the second game, 401864513, is a legacy null-lean record whose selection side was defaulted to Home, so it has no real Away selection to check; the sizing counted it by the model's direction. Neither game changes a grade.
- Non-V5 legacy publishes of partial slates would now need `--allow-partial-slate`.
- Receipts are written locally (`artifacts/quality/receipts/publish/`, git-ignored). Storing them next to release evidence in R2 is not done.

**Not done:** an R2 copy of publish receipts; a fake-connection test of the full `main()` of `publish_game_venues.py` (its checks and the venue payload and readback logic are unit-tested; the dry run was validated against Preview).

### Amendment 3: Tasks 5 and 6 delivered; items still open (2026-10-04)

**Task 5 (web read side).** `web/src/lib/row-guard.ts` is a dependency-free guard that checks rows at the loader boundary and throws `RowContractError` on a null in a required field, a NaN or infinite number, a non-integer, an unknown enum value, an invalid date, or a rank outside its cohort. It never coerces: valid rows are returned unchanged. It is applied to `getTeamSeasonStats`, `getTeamPossessionStats`, `getGamesForWeek`, `getCurrentRatings` and `getV5PerformanceDetail`. Pages already turn a thrown loader error into their "temporarily unavailable" state; the matchup page now distinguishes `statsUnavailable` ("Team stats are temporarily unavailable.") from "not published". The two stats loaders previously swallowed every error and returned an empty list; they now rethrow contract violations so a violation is no longer indistinguishable from "no stats". The contracts were checked read-only against real Preview rows (11,506 season stats, 6,276 possession stats, 1,213 current ratings, 271 predictions, 541 grades) with zero violations, so no page should newly show an unavailable state. The user's stipulation that parsers consume `rowsOf()`/`existsFrom()` from `web/src/lib/db-result.ts` is met in a narrower way than written: those helpers cover only the five raw `execute()` existence probes, which already use them, while all other reads use typed drizzle selects (not raw `{ rows }` results), so the guard sits on the selected rows. Fixtures stay valid under `CFB_UI_TEST_MODE=1` (a test asserts it) and test game `987655` renders the unavailable state.

**Task 6 (CI and catalog).** `docs/data/data_quality_checks.md` documents all 27 checks with the reason and the defect each prevents; `tests/test_quality_catalog.py` fails CI if the catalog and the registry disagree on ids, severity or stage (drift was verified to be detected). CI's lint job now runs `python -m cks_picks_cfb.quality --verify-registry`; the check-registry integrity step is also in `make all` via `make quality-check`. Data-bound stages stay operator-run. The full Python suite passes with CI's own flags (warnings as errors, parallel workers), and the web lint, typecheck, publication tests, build and Playwright (50 tests) pass.

**Still open, so the contract is not yet Implemented:**
1. Task 2 inputs for `ingest.capture_completeness`, `ingest.odds_unmatched_events` and `ingest.schema_contract` are not wired (they report `skipped`), and the ingesters do not yet call their checks before writing.
2. The five unpinned multi-version datasets (`game_outcomes`, `legacy_market_references`, `offseason_context_family`, `schedule_revisions`, `team_aliases`) are not reviewed.
3. Task 3 Gold-stage checks are not written, and no quality receipt is emitted from the Silver build scripts.
4. No check other than the structural `publish.*` set has been reviewed for promotion to `block`.
5. Receipts are stored locally only; an R2 copy next to the release evidence is not done.
6. The decision on `utils/validation.py` (left in place, unreferenced) is still open.
**Options:** accept 1-6 as follow-ups and mark this contract Implemented, or keep it In Progress until they are done.