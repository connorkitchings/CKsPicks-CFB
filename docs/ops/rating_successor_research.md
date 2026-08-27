# Successor-v2 Rating Research Operations

This runbook governs R1–R4 only. It is Preview-only and never changes V4
bundles, production Neon state, publication, or rollback authority. Candidate
v1 remains a separate O2 diagnostic lane in the worktree pinned to `ac1fba1`.

## R1 — Capture and certify history

Use a committed successor-v2 implementation and Preview configuration. The
operation uses `--year 2026` only to bind the protected inference context; it
captures historical seasons, never 2026 outcomes.

```bash
PYTHONPATH=.:src uv run python -m cks_picks_cfb.ops prepare-rating-history \
  --year 2026 --as-of "$AS_OF" --environment preview \
  --pipeline-run-id "r1-history-$(git rev-parse --short HEAD)"
```

The command captures CFBD teams, games, venues, game statistics, and plays for
2015–2018; imports the existing 2019 archive; and builds new isolated
successor-v2 Silver/reconciled-team-game refs. It reuses the certified
2021–2025 immutable refs when assembling the full corpus. Plays use the
Preview-only `history_play_capture_v1` profile: one sequential, process-isolated
request per provider week, with a 120-second SDK deadline, 300-second worker
deadline, four attempts, and an append-only attempt ledger.

On a failed play week, rerun the *same* pipeline ID. The stored request plan is
validated, completed checksummed weeks are reused, and only missing/failed
weeks are requested again:

```bash
PYTHONPATH=.:src uv run python -m cks_picks_cfb.ops prepare-rating-history \
  --year 2026 --as-of "$AS_OF" --environment preview \
  --pipeline-run-id "$R1_RUN"
```

Do not use `--skip-capture` to resume an incomplete capture set. It is only for
downstream-only recovery after every 2015–2018 `play-capture-set-v1` manifest is
complete and read-only verification has passed. Each manifest is written under
`artifacts/research/rating-successor-v2/r1/$R1_RUN/` and lists the ordered
request identities, capture IDs, checksums, rows, returned/missing game IDs,
policy SHA, and code SHA. Successor Silver consumes those explicit capture IDs;
it never broadly queries a play ingestion run.

For the four known abandoned 2015 diagnostics, reconcile only after confirming
the outer pipeline run and `capture_successor_history_2015_plays` step are
already failed. This preserves all existing evidence and never deletes objects:

```bash
PYTHONPATH=.:src uv run python -m cks_picks_cfb.ops \
  reconcile-history-play-captures --year 2026 --environment preview \
  --pipeline-run-id "r1-reconcile-$(git rev-parse --short HEAD)" \
  --ingestion-run-id "$ABANDONED_INGESTION_RUN_ID"
```

Before the full 2015 set, run the controlled Week 1 compatibility verification
and require the known 15,369-play result. It is read-only and creates no Bronze,
projection, or Silver object:

```bash
PYTHONPATH=.:src uv run python -m cks_picks_cfb.ops \
  verify-history-play-sample --year 2026 --environment preview \
  --pipeline-run-id "r1-2015-week1-verify-$(git rev-parse --short HEAD)"
```

Record every request SHA, attempt,
capture ID, checksum, returned/missing game IDs, timeout, and retry in the R1
session log. A failed or incomplete set is diagnostic-only: it must not write a
partial legacy `raw/plays/year=<season>` projection or reach Silver.

After true-PPSO measurements, terminal states, and schema checks have produced
the coverage counts, write the exact ref set and certification report. Pass
each dataset ref explicitly; the command rejects missing/extra seasons,
conflicting immutable payloads, and any 2020 lineage.

```bash
PYTHONPATH=.:src uv run python scripts/pipeline/certify_successor_history.py \
  --environment preview \
  --coverage-evidence-json "$R1_COVERAGE_EVIDENCE" \
  --dataset-ref "2015:games:$GAMES_2015_REF" \
  --dataset-ref "2015:plays:$PLAYS_2015_REF" \
  # …repeat every required season/dataset ref… \
  --ref-set-uri "artifacts/research/rating-successor-v2/r1/$R1_RUN/ref-set.json" \
  --coverage-report-uri "artifacts/research/rating-successor-v2/r1/$R1_RUN/coverage.json"
```

Do not proceed to R2 unless the report says `tournaments_permitted: true`.
That requires every eligible season's coverage gates and at least three passing
seasons from 2015–2019.

## R2–R4 — Sealed selection sequence

The roster is frozen in
`conf/ratings/successor_v2_tournaments.yaml`. R2 uses target seasons 2018,
2019, 2022, 2023, and 2024; 2025 is its one locked confirmation. R3 uses
2017–2019 and 2021–2024, then locks 2025. R4 runs only after the selected R2
prior and R3 updater are immutable.

- Never add an unsealed candidate after any selection result exists.
- Use football measurements, venue/weather, rating outputs, uncertainty, pace,
  completed-game counts, and context admitted by the eligibility contract.
- Do not use team categorical memorization, market data, future observations,
  or diagnostic-only context.
- The candidate-v2 gate uses seed 42 and exactly 2,000 paired bootstrap samples
  for Games 1–3, plus individual full-season and locked-2025 non-regression.

Each R2/R3/R4 session log records code/config SHA, ref-set SHA, exact folds,
candidate roster, context-admission decision, artifact URIs/checksums, and
whether the next stage is authorized. A failed stage produces an immutable
diagnostic report and leaves v1 and V4 unchanged.

## Protected 2026 boundary

No 2026 outcome enters R1–R4. Candidate v2 gets a new prospective policy and
six-slate counter only after its committed implementation and freeze. There is
no retrospective freeze and no transfer of O2 candidate-v1 evidence.
