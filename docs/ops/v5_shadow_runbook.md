# V5 Shadow Operations Runbook

> **Current policy:** [V5 model development is complete](../modeling/v5_status.md). The Week 4 refresh below gates a current forecast, not model completion. Contract 06 freezes and outcome reports continue as monitoring; six qualifying slates are not a site cutover prerequisite. The [cutover contract](../plans/2026-09-22/04-v5-authority-simplification-and-site-cutover.md) requires Preview serving rehearsal and V4 rollback proof before a separate activation decision.

> **Status:** Active (V5-05C + live adapter, 2026-09-22) · **Environment:**
> Preview R2 only · **Production authority:** V4 is unchanged; nothing here
> writes Neon, web, or production state · **Next gate:** stabilized Week 4
> finals, then fresh verified Contract 07/08 parents

## Purpose and authority

This runbook operates the V5 shadow tooling built by contracts
[V5-05A/05B/05C](../archive/v5-contracts/2026-09-13/05-v5-prospective-readiness-and-shadow-tooling.md)
and the code-ready live research path in
[plan 03](../archive/v5-contracts/2026-09-22/03-v5-live-research-tooling-completion.md):
outcome-free Contract 09 forecasts, Contract 05 readiness/freeze/scoring, and
Contract 06 evidence reports. All operations are Preview-only. Live forecast
outputs use `artifacts/research/data-first-football-v1/forecasts/live-runs/`;
shadow outputs use
`artifacts/research/data-first-football-v1/possession-v1/shadow/`; Contract 06
evidence uses
`artifacts/research/data-first-football-v1/possession-v1/evidence/runs/`.

Two evidence classes exist and never mix:

| Class | Meaning | Counts prospectively? |
|---|---|---|
| `diagnostic_only` | Historical rehearsal or fixture-driven output | Never |
| prospective | Live slate frozen before kickoff with verified `ready` readiness | Yes (via Contract 06) |

Current code state: the live forecast producer/verifier, versioned shadow
adapter, and Contract 06 evidence runner/verifier are implemented and covered
by synthetic tests. No operational forecast preflight/apply, refreshed-parent
readiness, evidence attempt, or qualifying slate has been run. The older
verified blocked readiness assessment records its historical missing inputs;
it is not a substitute for checking the refreshed Week 4 lineage. The live
sequence remains gated on stabilized Week 4 finals and new, independently
verified Contract 07 and 08 manifests. Contract 06 opens only after the exact
live forecast has independently verified Contract 05 `ready` status. Diagnostic
rehearsals and retrospective replays never count.

## Historical diagnostic refs (fixtures only)

The refs below document the certified historical diagnostic rehearsal. They
are not eligible operational parents for the 2026 live forecast or readiness.
After Week 4 finals stabilize, refresh Contracts 07 and 08 under new immutable
run IDs and use those exact verified manifest URIs. Do not substitute the
Weeks 0–3 Contract 08 replay for the Week 4 refresh.

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

Historical config: `conf/research/data_first_football_v1/shadow_v1.yaml` (sealed:
T-2h target / T-1h hard lead, 24h stabilization, ≥40 paired games,
`diagnostic_only` class, `production_activation_authorized: false`).
The versioned live adapter uses
`conf/research/data_first_football_v1/shadow_live_v1.yaml`; Contract 09 uses
`live_forecast_v1.yaml`; Contract 06 uses `prospective_evidence_v1.yaml`.

## Tooling map

| Command | Kind | Purpose |
|---|---|---|
| `scripts/research/run_v5_shadow_readiness.py` | producer | Source availability + optional `--replay` frozen-algorithm proof |
| `scripts/research/run_v5_shadow_freeze.py` | producer | Plan/apply an immutable freeze (`--diagnostic` for fixtures) |
| `scripts/research/run_v5_shadow_score.py` | producer | Outcome-versioned scoring + evidence counter |
| `scripts/research/run_v5_shadow_rehearsal.py` | producer | Full diagnostic rehearsal incl. six negative cases |
| `scripts/research/verify_v5_shadow.py` | **independent verifier** | Reconstructs any shadow manifest from sources; writes `verification/verifier-manifest.json` |
| `scripts/research/run_v5_live_forecast.py` | producer + verifier | Contract 09 live forecast preflight, evidence-bound Preview apply, independent verify/repeat |
| `scripts/research/run_v5_prospective_evidence.py` | producer + verifier | Contract 06 evidence preflight, immutable apply/repeat, or manifest verification |
| `scripts/research/verify_v5_prospective_evidence.py` | **independent verifier** | Reconstructs Contract 06 reports from verified readiness, freeze, score, outcome, and optional quote parents |

All producer applies are evidence-bound: `--apply` requires
`--preflight-evidence` from a reviewed dry run, a completely clean committed
worktree, and `--expected-code-sha` equal to `git rev-parse HEAD`.

## 2026 live sequence (gated; code-ready only)

Do not start this sequence until Week 4 finals have stabilized and Contracts 07
and 08 have been refreshed through Week 4 under new immutable run IDs, with
independent verifier receipts. Use those exact Preview refs. The Weeks 0–3
Contract 08 replay and the older diagnostic refs above cannot satisfy this
gate. The Contract 09 runner independently checks the Week 4 gate and fails
closed on missing or mismatched parents.

### Preview serving rehearsal after a verified Contract 09 forecast

Pin the exact live forecast manifest URI and raw SHA in a review copy of
`conf/weekly_bets/v5_preview_2026.yaml`. Keep
`production_activation_authorized: false`. The standard `make readiness` and
`make publish-week` paths select the explicit `v5_weekly_serving_v1` mode and
independently reconstruct the forecast from its 07/08/11C and schedule parents
before writing the normal immutable prediction-run artifact. They reject a
changed serving schedule, incomplete margin/total pairs, late sources, and a
production environment without a separate activation decision.

Use the Preview Neon branch and a new run ID; record the exact config SHA,
forecast manifest SHA, prediction-run artifact SHA, game coverage, `/api/health`
result, and two checked home-margin/market-line examples. Re-publish V4 in
Preview and verify the active run and site view return to V4. Record the V4 run
ID and rollback time. This is a rehearsal, never public activation. The
[production runbook](production_runbook.md) retains the rollback-by-reselection
procedure for an approved future cutover.

### 1. Contract 09 forecast

Run the following read-only preflight after the parent gate passes. The
placeholders must be replaced with the new verified Contract 07 measurement
manifest, Contract 08 rating replay manifest, and immutable complete 2026
schedule ref. The runner also pins the fixed 11C final-fit bridge from its
approved config; it does not fit or select on 2026 outcomes.

```bash
SHA=$(git rev-parse HEAD)
AS_OF=<UTC forecast cutoff>
RID=<new immutable forecast run id>
MEASURE=<fresh verified Contract 07 manifest URI>
RATING=<fresh verified Contract 08 manifest URI>
SCHEDULE=<immutable 2026 schedule object URI>
ARGS="--run-id $RID --expected-code-sha $SHA --environment preview --as-of $AS_OF --measurement-manifest-uri $MEASURE --rating-manifest-uri $RATING --schedule-ref-uri $SCHEDULE"
PYTHONPATH=.:src uv run python scripts/research/run_v5_live_forecast.py $ARGS > preflight-$RID.json
```

Review exact parents, full future-slate coverage, cutoff timing, output
membership and digests. Only after review, run the same command with
`--apply --preflight-evidence preflight-$RID.json` on a clean committed
worktree. The runner writes the terminal manifest last. Verify it independently
and repeat the same apply to establish idempotence:

```bash
PYTHONPATH=.:src uv run python scripts/research/run_v5_live_forecast.py $ARGS \
  --verify-manifest-uri <live forecast manifest URI>
PYTHONPATH=.:src uv run python scripts/research/run_v5_live_forecast.py $ARGS \
  --apply --preflight-evidence preflight-$RID.json
```

The verifier must reproduce all predictions and raw parent/output digests. The
repeat must return `already_applied`. The manifest remains Preview-only with
`production_activation_authorized: false`.

### 2. Contract 05 live readiness, freeze, and score

Use the verified Contract 09 live manifest as `--candidate-manifest-uri`, plus
the exact refreshed Contract 07/08 and Repair refs. Readiness loads 2026 sources
through the versioned live adapter rather than the historical fixed-population
loader. Request the next slate only when its sources meet the pre-cutoff gate;
use `--replay` to check the frozen update algorithm. A signed, independently
verified `blocked` report is useful evidence only when it names the exact
missing dependency. Only independently verified `ready` opens Contract 06.
Use the exact current refs in the live readiness command:

```bash
SHA=$(git rev-parse HEAD)
AS_OF=<UTC readiness cutoff>
FORECAST=<independently verified Contract 09 live manifest URI>
RATING=<fresh verified Contract 08 manifest URI>
MEASURE=<fresh verified Contract 07 manifest URI>
V4=<immutable V4 slate predictions URI>
INPUTS=<immutable source input-refs JSON URI>
SLATE=<immutable declared slate/schedule URI>
REPAIR=<verified Repair parent manifest URI>
RID=<new readiness run id>
PYTHONPATH=.:src uv run python scripts/research/run_v5_shadow_readiness.py \
  --run-id "$RID" --expected-code-sha "$SHA" --environment preview \
  --config conf/research/data_first_football_v1/shadow_live_v1.yaml \
  --as-of "$AS_OF" --candidate-manifest-uri "$FORECAST" \
  --rating-manifest-uri "$RATING" --measurement-manifest-uri "$MEASURE" \
  --repair-manifest-uri "$REPAIR" --season 2026 --week <week> \
  --v4-prediction-ref-uri "$V4" --input-refs-uri "$INPUTS" \
  --slate-ref-uri "$SLATE" --replay > readiness-preflight-$RID.json
```

After reviewing and publishing readiness, freeze with the same exact candidate,
07/08/Repair, V4, and slate refs; add the verified readiness manifest, season,
week, and a pre-kickoff `--as-of`; use
`--config conf/research/data_first_football_v1/shadow_live_v1.yaml`. The freeze
CLI enforces T−2h target, T−1h hard lead, and paired coverage. After outcome
stabilization, score with the exact freeze manifest and final outcome ref using
`run_v5_shadow_score.py` and the same live config. Use `--help` for each
runner's apply/preflight-evidence flags and follow the same clean committed-code
gate for each immutable publication. Do not use `--diagnostic` outside an
explicitly diagnostic fixture rehearsal.

Freeze only after verified `ready`, at the T−2h target and never later than
T−1h before first kickoff, with the existing >=40 complete paired-game gate.
After all included games have final timestamps and at least 24 hours have
elapsed since the last completion, score against an exact immutable outcome
version. Independently verify readiness, freeze and score. Corrections append a
new score version linked to the preceding score manifest and cannot increment
the same candidate-season-week twice. Diagnostic freezes remain excluded.

### 3. Contract 06 evidence report

After eligible live artifacts exist, create an ordered
`data_first_v5_evidence_input_v1` descriptor containing the candidate and each
attempt's season/week/run ID, readiness manifest and verifier receipt, freeze
manifest and verifier receipt, schedule and V4 refs, and ordered score-version
manifest/verifier/outcome refs. Optionally add an authentic signed Preview quote
manifest and timezone-aware cutoff, or a signed Contract 06 review input. A
missing or invalid attempt is preserved with its blocker; do not invent a
qualifying count.

```bash
SHA=$(git rev-parse HEAD)
RID=<new immutable evidence run id>
AS_OF=<UTC evidence cutoff>
DESC=<local immutable input descriptor JSON>
PYTHONPATH=.:src uv run python scripts/research/run_v5_prospective_evidence.py \
  preflight --run-id "$RID" --expected-code-sha "$SHA" --environment preview \
  --as-of "$AS_OF" --input-descriptor "$DESC" \
  --write-preflight "preflight-$RID.json"
```

Review all dispositions, independent qualifying count, outcome-versioned
football metrics, quote omissions, and recommendation. Apply only against that
reviewed preflight on a clean committed worktree, then use the independent
verifier and repeat the same apply. Before six qualifying slates, the only
permitted recommendation is `continue_shadowing` with concrete blockers. At
six, the report uses one of Contract 06's existing categories; it never
activates V5. Quote presence or changes cannot affect football metrics or
eligibility. See [Contract 06](../plans/2026-09-13/06-v5-prospective-evidence-and-recommendation.md)
for the recommendation meanings.

```bash
PYTHONPATH=.:src uv run python scripts/research/run_v5_prospective_evidence.py \
  apply --run-id "$RID" --expected-code-sha "$SHA" --environment preview \
  --as-of "$AS_OF" --input-descriptor "$DESC" \
  --preflight-evidence "preflight-$RID.json"
PYTHONPATH=.:src uv run python scripts/research/verify_v5_prospective_evidence.py \
  --manifest-uri <evidence manifest URI from apply> \
  --expected-code-sha "$SHA" --environment preview
# Repeat the identical apply command; it must return already_applied.
```

## Historical compatibility readiness check (read-only)

The command below is for the pinned historical/diagnostic lineage only. It
does not assess 2026 readiness and must not be used for the live sequence above.
Supply the historical refs from the table only when reproducing the archived
readiness artifact.

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

Read-only dry run (stdout JSON). Add `--replay` only for the historical
compatibility replay. A historical `ready` result cannot open live collection.

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

## Live freeze/score reference

Use “Contract 05 live readiness, freeze, and score” above for current 2026
operations. The old checklist here was superseded by the versioned 2026 adapter
and must not be executed with the historical parent URIs.

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

Tooling refs for 06: the shadow and evidence CLIs above, the sealed
`shadow_v1.yaml`, the versioned live configs, the evidence input schema
`data_first_v5_evidence_input_v1`, and this runbook. The older readiness
assessment is a preserved historical blocker record; refreshed-parent live
readiness must be verified independently when its gate is met.

---

_Last updated: 2026-09-22 (V5-05C and live research code readiness)_
