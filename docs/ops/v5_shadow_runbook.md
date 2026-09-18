# V5 Shadow Operations Runbook

> **Status:** Active (V5-05C, 2026-09-18) · **Environment:** Preview R2 only ·
> **Production authority:** V4 is unchanged; nothing here writes Neon, web, or
> production state · **Next gate:** Historical Contracts 10–12

## Purpose and authority

This runbook operates the V5 shadow tooling built by contracts
[V5-05A/05B/05C](../plans/2026-09-13/05-v5-prospective-readiness-and-shadow-tooling.md):
readiness validation, frozen replay, immutable freezes, outcome-versioned
scoring, the evidence ledger, the diagnostic rehearsal, and independent
verification. All operations run in the Preview R2 bucket under
`artifacts/research/data-first-football-v1/possession-v1/shadow/`.

Two evidence classes exist and never mix:

| Class | Meaning | Counts prospectively? |
|---|---|---|
| `diagnostic_only` | Historical rehearsal or fixture-driven output | Never |
| prospective | Live slate frozen before kickoff with verified `ready` readiness | Yes (via Contract 06) |

Current verified state: **live readiness is `blocked`** (see the
[verified readiness assessment](../research/2026-09-17-v5-live-readiness-assessment.md)).
Only diagnostic operations may run. Contracts 10-12 must close and historical
readiness must be explicitly accepted before the deferred 2026 application path
is re-reviewed. A diagnostic rehearsal or retrospective replay never counts as
forecast-quality or prospective evidence.

## Pinned parents (exact URIs)

```text
FORECAST   artifacts/research/data-first-football-v1/forecasts/runs/forecast-v1-20260917-4600ddd-04b/forecast-manifest.json
RATING     artifacts/research/data-first-football-v1/possession-v1/ratings/runs/possession-v1-ratings-20260917-d029526-cert/retained-rating-manifest.json
MEASURE    artifacts/research/data-first-football-v1/possession-v1/measurements/runs/possession-v1-measurements-20260915-18fb0aa-r6/measurement-manifest.json
REPAIR     artifacts/research/data-first-football-v1/repair/v2/runs/repair-v2-20260909T1417Z/repair-manifest.json
READINESS  artifacts/research/data-first-football-v1/possession-v1/shadow/runs/shadow-v1-20260917-cd07d8b-05a/shadow-manifest.json
FREEZE     artifacts/research/data-first-football-v1/possession-v1/shadow/runs/shadow-v1-20260918-73e8e9b-05b-freeze/freeze-manifest.json
SCORE      artifacts/research/data-first-football-v1/possession-v1/shadow/runs/shadow-v1-20260918-7aec1c8-05b-score/score-manifest.json
SLATE      artifacts/research/data-first-football-v1/possession-v1/shadow/fixtures/diagnostic_schedule_2025w10.parquet
V4PREDS    artifacts/research/data-first-football-v1/possession-v1/shadow/fixtures/diagnostic_v4_predictions_2025w10.parquet
OUTCOMES   artifacts/research/data-first-football-v1/possession-v1/shadow/fixtures/diagnostic_outcomes_2025w10.parquet
```

Config: `conf/research/data_first_football_v1/shadow_v1.yaml` (sealed:
T-2h target / T-1h hard lead, 24h stabilization, ≥40 paired games,
`diagnostic_only` class, `production_activation_authorized: false`).

## Tooling map

| Command | Kind | Purpose |
|---|---|---|
| `scripts/research/run_v5_shadow_readiness.py` | producer | Source availability + optional `--replay` frozen-algorithm proof |
| `scripts/research/run_v5_shadow_freeze.py` | producer | Plan/apply an immutable freeze (`--diagnostic` for fixtures) |
| `scripts/research/run_v5_shadow_score.py` | producer | Outcome-versioned scoring + evidence counter |
| `scripts/research/run_v5_shadow_rehearsal.py` | producer | Full diagnostic rehearsal incl. six negative cases |
| `scripts/research/verify_v5_shadow.py` | **independent verifier** | Reconstructs any shadow manifest from sources; writes `verification/verifier-manifest.json` |

All producer applies are evidence-bound: `--apply` requires
`--preflight-evidence` from a reviewed dry run, a completely clean committed
worktree, and `--expected-code-sha` equal to `git rev-parse HEAD`.

## Sequence 1 — readiness check (any time, read-only)

```bash
SHA=$(git rev-parse HEAD)
AS_OF=$(date -u +%Y-%m-%dT%H:%M:%SZ)
PYTHONPATH=.:src uv run python scripts/research/run_v5_shadow_readiness.py \
  --run-id shadow-v1-$(date -u +%Y%m%d)-readiness \
  --expected-code-sha "$SHA" --environment preview --as-of "$AS_OF" \
  --candidate-manifest-uri "$FORECAST" --rating-manifest-uri "$RATING" \
  --measurement-manifest-uri "$MEASURE" --repair-manifest-uri "$REPAIR" \
  --season 2026 --week 4
```

Read-only dry run (stdout JSON). `overall: ready` is required before any
prospective freeze; `blocked` names the missing sources. Add `--replay` to
prove frozen-algorithm byte-identity (minutes of runtime; R6 streaming).

## Sequence 2 — diagnostic rehearsal (Preview, certifiable)

```bash
SHA=$(git rev-parse HEAD)                # clean committed worktree required for --apply
AS_OF=<run UTC timestamp>
RID=shadow-v1-$(date -u +%Y%m%d)-<shortsha>-05c
PYTHONPATH=.:src uv run python scripts/research/run_v5_shadow_rehearsal.py \
  --run-id "$RID" --expected-code-sha "$SHA" --environment preview --as-of "$AS_OF" \
  --candidate-manifest-uri "$FORECAST" --rating-manifest-uri "$RATING" \
  --measurement-manifest-uri "$MEASURE" --repair-manifest-uri "$REPAIR" \
  --readiness-manifest-uri "$READINESS" --freeze-manifest-uri "$FREEZE" \
  --v4-prediction-ref-uri "$V4PREDS" --slate-ref-uri "$SLATE" --outcome-ref-uri "$OUTCOMES" \
  --season 2025 --week 10 > preflight-$RID.json
# review: zero unexpected dispositions, qualifying count 0, replay digest present
PYTHONPATH=.:src uv run python scripts/research/run_v5_shadow_rehearsal.py <same args> \
  --apply --preflight-evidence preflight-$RID.json
```

Every rehearsal output carries `diagnostic_only = true` permanently; its
counter records never qualify. Idempotent rerun returns `already_applied`
with zero writes.

## Sequence 3 — independent verification (after any apply)

```bash
PYTHONPATH=.:src uv run python scripts/research/verify_v5_shadow.py \
  --manifest-uri <manifest-uri> --expected-code-sha <artifact code SHA> \
  --environment preview [--schedule-uri "$SLATE"] --write-manifest
```

- 05A readiness manifests: no source URIs needed (verifier streams the parents).
- Freeze/score manifests: pass `--schedule-uri` (the freeze manifest does not
  pin the slate fixture); V4/outcome sources default to the manifest parents.
- The verifier reconstructs timing, population, predictions, scores, counters,
  readiness, replay evidence, and rehearsal cases from source artifacts and
  must not import any producer module (AST-enforced).
- Signed output lands at `<run-prefix>/verification/verifier-manifest.json`
  (idempotent; byte-different rewrite is an immutable collision).

## Sequence 4 — future live freeze/score (gated on `ready`)

Only after readiness verifies `ready` for the slate (requires the 2026
measurement/rating extension and a real V5 replay output):

1. `run_v5_shadow_freeze.py --season S --week W --as-of <T-2h cutoff>` — dry
   run, review, then evidence-bound `--apply`. Freeze at T-2h; never below T-1h.
2. After all games complete + 24h stabilization: `run_v5_shadow_score.py
   --freeze-manifest-uri <freeze> --outcome-ref-uri <final outcomes>` — dry
   run, review, apply.
3. Verify both manifests (Sequence 3).
4. Corrections re-score under a new `--outcome-version`; the counter appends
   but never re-increments the qualifying count for that slate.

Until the blockers clear, any attempt to freeze a 2026 slate fails the
readiness parent check by design.

## Failure recovery

- **Partial prefix**: any files under `runs/<run-id>/` without the terminal
  manifest make that run ID permanently ineligible. Never resume; use a new
  run ID after a new commit.
- **Immutable collision**: same URI with different bytes aborts. Terminal
  manifests are compared by `identity_sha256`; identical reruns are
  `already_applied`, different identities are permanent failures.
- **Interrupted rehearsal**: re-execute from preflight; never write into the
  old prefix.
- **Idempotent repeat is mandatory evidence**: a certified run repeats
  byte-identically or the certification is invalid.

## Counter rules

- One qualifying slate = one `(candidate, season, week)` frozen pre-kickoff,
  scored after stabilization, ≥40 paired games.
- `diagnostic_only` rows never qualify (verifier-enforced).
- Corrections append rows; the deduplicated qualifying total is independently
  derivable from immutable refs.
- A changed candidate starts a fresh ledger (per-candidate counting).

## Contract 06 handoff

Contract 06 (prospective evidence and recommendation) must, per collected
slate:

1. Re-verify `ready` readiness for that exact slate and cutoff (Sequence 1).
2. Verify the freeze manifest (timing, population, predictions) and score
   manifest (stabilization, scores, counter) with Sequence 3.
3. Confirm the freeze timestamp precedes the slate's first kickoff with
   ≥3600s lead and that outcomes are final + 24h stabilized.
4. Append to the evidence ledger without double-counting; diagnostic runs are
   excluded.
5. Only after **six** qualifying paired slates (V5 vs V4) may the promotion
   review open — review, not automatic promotion. Phase 7 requires a separate
   approved contract.

Tooling refs for 06: the five CLIs above, the sealed
`shadow_v1.yaml`, this runbook, and the verified readiness assessment.

---

_Last updated: 2026-09-18 (V5-05C)_
