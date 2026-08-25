# Session: Phase 3 V4 Benchmark Recovery

## TL;DR

- **Worked On:** Implemented the isolated recovery interface for the missing
  historical game-level V4 benchmark required by Phase 3.
- **Outcome:** A Preview-only, immutable replay CLI now rebuilds frozen Games
  1--4 routes from the strict reports and creates a separately labeled,
  chronological established-route compatibility replay. No V4, Neon, public,
  or Preview artifact was changed in this session.
- **Plan Contract:**
  [`phase3-v4-benchmark-recovery.md`](../../docs/plans/2026-08-25/phase3-v4-benchmark-recovery.md)
  (`In Progress`).
- **Approval / Status:** The user explicitly authorized the recovery plan on
  2026-08-25. Code/configuration must be committed before the first Preview
  write.
- **Blockers:** Preview materialization is intentionally blocked until the
  user commits this implementation, because the CLI verifies tracked,
  byte-identical recovery paths before it touches R2.
- **Next:** Commit the listed files, then run the Preview-only recovery command
  with the committed SHA and a new run ID; do not begin Phase 3 construction
  until the resulting audit passes.

## Decisions and Safety Boundaries

- V4 early routes are reconstructed only from the immutable strict selection
  and locked reports; the workflow cannot reselect candidates or tune routes.
- The established route is permanently labeled
  `derived_compatibility_replay`, because no archived game-level V4 OOF output
  exists for it. It uses the exact V4 direct-Ridge feature order and only
  preceding established rows in each fold.
- Candidate generation executes from a detached temporary worktree at
  `33432e8`, the corrective V4 materialization commit. The historical bundle's
  recorded `5371d7f...` code SHA remains visible as a warning rather than being
  retroactively corrected.
- All outputs are constrained to
  `artifacts/research/rating-successor/v4-benchmark-replay/{design_id}/runs/{run_id}/`;
  production, catalog registration, bundle writes, and publication are absent.

## Files Modified

- `conf/ratings/v4_benchmark_replay_v1.yaml` — frozen V4 sources, integrity
  expectations, engine commit, and research prefix.
- `src/cks_picks_cfb/ratings/v4_benchmark.py` — versioned benchmark frame,
  frozen-route extraction, temporal validation, report parity, and audit.
- `scripts/pipeline/build_rating_v4_benchmark.py` — Preview-only immutable
  recovery CLI, committed-code gate, temporary pinned-engine replay, and
  fail-closed ref publication.
- `tests/ratings/test_v4_benchmark.py` — route filtering, duplicate,
  established-label, temporal, audit-parity, CLI isolation, successful
  immutable publication, and same-run rerun tests.
- `docs/plans/2026-08-25/phase3-v4-benchmark-recovery.md` — approved recovery
  contract; `phase3-structured-margin-total-baseline.md` records it as a
  prerequisite.

## Validation

- [x] `uv run pytest tests/ratings/test_v4_benchmark.py -q` — 8 passed.
- [x] `uv run pytest tests/ratings -q` — 71 passed.
- [x] `uv run pytest -q` — 485 passed, 2 skipped.
- [x] Scoped Ruff — passed.
- [x] `uv run python contracts/validation.py` — passed.
- [x] `make contracts-check` — passed.
- [x] `uv run mkdocs build --strict --quiet` — passed.
- [x] `git diff --check` — passed.

## Handoff

### Amendment 1 -- Pre-materialization lineage hardening

- The audit now records the actual prediction manifest URI rather than the
  Parquet data URI.
- The pinned replay uses the configured V4 experiment path, and rejects any
  differing established spread/total feature order.
- A local-storage integration test now proves successful ref publication and
  byte-identical reruns before Preview access.

The recovery configuration design ID is
`341285d246cb24c1e4d978e60eeed306b67a5734931324c807b17da799bf97c3`.
After committing this session's files, run through the Preview wrapper with a
fresh UTC run ID and the commit SHA:

```bash
zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/build_rating_v4_benchmark.py \
  --environment preview \
  --as-of <UTC_CUTOFF> \
  --run-id <UTC_RUN_ID> \
  --expected-code-sha <COMMITTED_SHA> \
  --predictions-ref-uri artifacts/research/rating-successor/v4-benchmark-replay/341285d246cb24c1e4d978e60eeed306b67a5734931324c807b17da799bf97c3/runs/<UTC_RUN_ID>/predictions/ref.json \
  --report-uri artifacts/research/rating-successor/v4-benchmark-replay/341285d246cb24c1e4d978e60eeed306b67a5734931324c807b17da799bf97c3/runs/<UTC_RUN_ID>/audit/report.json \
  --manifest-uri artifacts/research/rating-successor/v4-benchmark-replay/341285d246cb24c1e4d978e60eeed306b67a5734931324c807b17da799bf97c3/runs/<UTC_RUN_ID>/manifest.json
```

Record the returned prediction-ref and audit checksums in the recovery
contract. If any parity or coverage check fails, retain only the diagnostic
report and return for a remediation contract.

**tags:** ["ratings", "phase3", "v4", "replay", "research-isolation"]
