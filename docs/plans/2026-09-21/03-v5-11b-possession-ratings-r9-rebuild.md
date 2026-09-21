# V5-11B: Possession Ratings Rebuild from r9 Measurements

- **Status:** In Progress
- **Created:** 2026-09-21
- **Planner:** Sol
- **Approval source:** User authorized the full Contract 11 decomposition on 2026-09-21 ("Let's do it all"); final-fit design and targeted-closure vehicle confirmed by structured decision the same day.
- **Implementation log:** `session_logs/2026-09-21/07-v5-11b-ratings-r9-rebuild.md`
- **Commit policy:** Separate commits — pin-swap checkpoint, then evidence checkpoints per phase. User controls Git operations.

## Goal

Re-derive the possession rating artifact from the certified r9 measurement
parent (`possession-v1-measurements-20260921-r9`), replacing the R6-derived
retained artifact in the full lane. Success is a new independently verified
rating run whose retained candidate (whatever the gates select — the r6 winner
`ppp__rho_0_60__exposure` is not guaranteed to repeat) becomes the sole
eligible rating parent for 11C.

## Current State

- Certified rating run `possession-v1-ratings-20260917-d029526-cert` descends
  from superseded r6; its lineage cannot serve the full lane after the r9 fix
  (81 corrected team-game score-ledger keys change rating observations).
- Runner `scripts/research/run_data_first_possession_ratings.py` (preflight dry
  run / evidence-bound apply / `already_applied` repeat) plus independent
  verifier `scripts/research/verify_data_first_possession_ratings.py` (zero
  producer imports, AST-enforced) are proven by Contract 03.
- Parent binding is fail-closed code pins in
  `src/cks_picks_cfb/data/data_first_possession_rating_v1.py:22-24`
  (`REQUIRED_R6_CERTIFICATION_SHA256`) and `:291` (measurement run-id pin).
- Repair parent is unchanged: `repair-v2-20260909T1417Z` was proven 100%
  correct; only its verifier was replaced.

## Proposed Approach

Swap the two ratings-layer pins to r9 (no logic changes — the 60-candidate
grid, advancement gates, regression guards, and tie-breaks re-run unchanged
against the corrected observations), then execute the established
preflight → apply → verify → repeat sequence under a fresh run identity. The
r9 `certification_sha256` (the `manifest_sha256` of r9's signed verifier
manifest) is resolved from R2 during implementation and pinned in code.

## Scope

### Included

- Pin swap: r9 certification SHA + run-id `possession-v1-measurements-20260921-r9`;
  updated fixtures in `tests/test_data_first_possession_rating_runner.py:70` and
  `tests/test_possession_rating_verification.py:69`.
- Fresh run `possession-v1-ratings-20260921-<shortsha>-r9cert` with
  `--measurement-manifest-uri
  artifacts/research/data-first-football-v1/possession-v1/measurements/runs/possession-v1-measurements-20260921-r9/measurement-manifest.json`,
  unchanged `--repair-manifest-uri`, `--expected-code-sha` = new HEAD,
  config `conf/research/data_first_football_v1/possession_rating_v1.yaml`.
- Full 60-candidate tournament (2 definitions × 6 priors × 5 updaters), outer
  seasons 2018/2019/2021–2025, 2020 forbidden, population 8,936/8,935 enforced.
- Independent verifier run + signed `verification/verifier-manifest.json` +
  idempotent repeat; user review of the retained manifest before 11C.

### Excluded

- Any change to rating methodology, gates, config, or the repair parent.
- 11C/11D work; any edit to historical 11A/12A/10B/03/04 evidence or pins.
- Neon/catalog/production writes; V4 or weekly-ops changes.

## Affected Components and Contracts

- `src/cks_picks_cfb/data/data_first_possession_rating_v1.py` (pins only).
- Two test files (fixture pins only). No producer, verifier, or config logic.
- New Preview R2 run prefix under
  `artifacts/research/data-first-football-v1/possession-v1/ratings/runs/`.
- Unblocks 11C; supersedes the R6-derived rating artifact in the full lane only.

## Implementation Tasks

### Task 1 — Pin swap and fixture update

**Files:**

- `src/cks_picks_cfb/data/data_first_possession_rating_v1.py`
- `tests/test_data_first_possession_rating_runner.py`
- `tests/test_possession_rating_verification.py`

**Changes:**

- Resolve r9's verifier-manifest `manifest_sha256` from R2; replace
  `REQUIRED_R6_CERTIFICATION_SHA256` and the `:291` run-id pin with the r9
  values. Update the two test literals in lockstep. Nothing else changes.

**Acceptance criteria:**

- Preflight against the r9 manifest passes parent binding; preflight against
  any other measurement identity fails closed.

**Validation:**

- Focused unit tests for the pin swap (accept r9, reject r6 and unknown ids).

### Task 2 — Rating run: preflight, apply, verify, repeat

**Files:**

- `scripts/research/run_data_first_possession_ratings.py`
- `scripts/research/verify_data_first_possession_ratings.py`

**Changes:**

- Execute the certified sequence under the fresh `-r9cert` run id in Preview;
  record the retained candidate and full selection evidence. If selection flips
  from `ppp__rho_0_60__exposure`, record the gate margins that decided it —
  no re-tuning, no second attempt.

**Acceptance criteria:**

- Byte-identical evidence between preflight and apply; independent verifier
  reconstructs every prior, state, bridge prediction, and the complete
  selection; repeat returns `already_applied`; population 8,936/8,935 holds.

**Validation:**

- Full focused suites for ratings modules; ruff; phase heartbeats reviewed;
  `git diff --check`.

## Testing Strategy

- Unit: pin accept/reject matrix, negative parent cases, fixture consistency.
- Integration: end-to-end Preview cycle (preflight/apply/verify/repeat).
- Regression: existing ratings + verification suites must pass unchanged apart
  from the two fixture pins.

## Risks and Edge Cases

- **Selection flip:** r9 corrections may promote a different candidate; the
  contract records (not retries) the outcome, and 11C re-pins to the winner.
- **Partial-prefix poisoning:** a failed apply permanently retires the run-id;
  use a fresh run-id, never reuse.
- **Long phases** (measurement-scale, ~15–30 min): use extended timeouts and
  review heartbeat streams; do not parallelize phases.
- **Evidence-bound discipline:** as-of, URIs, config SHA, and code SHA must
  byte-match between preflight and apply.

## Definition of Done

- [ ] r9 pins resolve from R2 and are the only accepted measurement identity.
- [ ] New `-r9cert` run completes preflight/apply/verify/repeat in Preview.
- [ ] Retained candidate recorded with selection evidence; user has reviewed it.
- [ ] Tests, ruff, contracts validation, strict MkDocs, `git diff --check` pass.
- [ ] This contract and `docs/plans/index.md` updated to `Implemented`.

## Amendments

None. A selection flip, population-count deviation, or verifier disagreement
returns to Sol — never re-run the grid under a tweaked design.
