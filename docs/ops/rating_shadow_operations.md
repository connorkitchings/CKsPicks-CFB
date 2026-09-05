# Rating Shadow Prospective Operations

!!! warning "Historical candidate-v1 compatibility only"
    This page preserves the frozen candidate-v1 procedure at `ac1fba1`. It is
    not the active research sequence. New prospective work follows the
    [data-first roadmap](../planning/data-first-football-forecasting-roadmap.md)
    after Phases 1–5 produce a frozen candidate.

O2 / Phase 5 is a manual, Preview-only diagnostic workflow for frozen
candidate v1. It never publishes,
freezes, scores, or changes V4 production runs. The production V4 run must
already be frozen under the normal production runbook.

## Preconditions

- The Phase 5 implementation is committed and the freeze/evaluator code paths
  match that commit.
- `PREVIEW_DATABASE_URL` is configured, distinct from `DATABASE_URL`, and the
  Preview Neon branch is available. The immutable R2 bucket may be shared when
  artifact namespaces remain environment-specific.
- Week `W` is at least 1, has at least 40 eligible games, and the production
  V4 run is frozen at least one hour before the earliest kickoff.
- Run `make prepare-week YEAR=2026 WEEK=W ENV=preview AS_OF=<cutoff>` before
  the candidate preflight. The output is the immutable input-ref set at
  `artifacts/preview/pipeline-runs/<run-id>/rating_input_ref_set.json`.

## Pregame workflow

Run the read-only preflight first. It must be green while at least one hour
remains before the earliest kickoff; two hours is the operating target.

```bash
PYTHONPATH=.:src uv run python scripts/pipeline/build_rating_shadow_freeze.py \
  --environment preview --season 2026 --week "$WEEK" --as-of "$AS_OF" \
  --input-ref-set-uri "artifacts/preview/pipeline-runs/$PREP_RUN/rating_input_ref_set.json" \
  --games-ref-uri "artifacts/preview/pipeline-runs/$PREP_RUN/games_ref.json" \
  --outcomes-ref-uri "artifacts/preview/pipeline-runs/$PREP_RUN/game_outcomes_ref.json" \
  --v4-run-id "$V4_RUN_ID" --expected-code-sha "$GIT_SHA" --preflight-only
```

Repeat the command without `--preflight-only` only after recording its exact
run IDs, cutoff, earliest kickoff, policy hash, and go/no-go result. Repeat the
identical freeze invocation once to verify the immutable no-op.

## Postgame workflow

After all Week `W` finals are authoritative and the 24-hour stabilization
period has elapsed, prepare Week `W+1` in Preview. Use that run's games and
outcomes refs to score Week `W`; it is the correction-verification input.

```bash
PYTHONPATH=.:src uv run python scripts/pipeline/build_rating_shadow_score.py \
  --environment preview --season 2026 --week "$WEEK" --as-of "$SCORE_AS_OF" \
  --games-ref-uri "artifacts/preview/pipeline-runs/$POST_RUN/games_ref.json" \
  --outcomes-ref-uri "artifacts/preview/pipeline-runs/$POST_RUN/game_outcomes_ref.json" \
  --expected-code-sha "$GIT_SHA"

PYTHONPATH=.:src uv run python scripts/pipeline/audit_rating_prospective_evidence.py \
  --environment preview --through-week "$WEEK" \
  --verification-games-ref-uri "artifacts/preview/pipeline-runs/$POST_RUN/games_ref.json" \
  --verification-outcomes-ref-uri "artifacts/preview/pipeline-runs/$POST_RUN/game_outcomes_ref.json" \
  --expected-code-sha "$GIT_SHA"
```

Only pass a cancellation waiver when the latest authoritative schedule marks
the frozen game `cancelled`, `canceled`, or `postponed`. Repeat both commands
identically after success.

## Recovery rules

- Late candidate/V4 freeze, sub-40-game slate, incomplete refs, partial
  canonical artifacts, or missing finals: retain diagnostics only; do not
  count the week.
- Schedule change or later score correction: never overwrite evidence; record
  a diagnostic and exclude the week from the cumulative count until an approved
  amendment resolves it.
- R2 collision: compare the exact payload. Identical content is a no-op; any
  difference fails closed.
- Catalog failure: do not retry with a different input. R2 canonical artifacts
  remain authoritative, and catalog registration may be retried only after
  identity verification.

Each weekly session log must record the preparation run, V4 run, cutoff,
measured lead, manifest/evidence/summary URIs and SHAs, waivers, diagnostics,
and whether the week counted.
