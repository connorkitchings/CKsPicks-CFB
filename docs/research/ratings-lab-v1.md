# Ratings laboratory v1

The ratings laboratory is a separate, private research path for designing V6 candidates. Its normal CLI reads the exact accepted V5 historical parents and writes only to a dedicated R2 research bucket. It does not change the V5 forecast, production selection, Neon, or the public site. The implementation contract is [`v6-ratings-research-platform.md`](../plans/2026-09-28/v6-ratings-research-platform.md).

The [V5 intended-update repair experiment](2026-09-28-v5-intended-update-repair-experiment.md)
is an explicitly scoped local-output exception while that dedicated bucket is
unprovisioned. Its standalone research scripts use a read-only Preview source
adapter and write reports/traces locally; they do not publish through the
normal lab CLI or alter any accepted artifact.

## Storage and credentials

Provision a private bucket such as `cks-picks-cfb-research`. Give the source credential read-only access to the immutable V5 source bucket and the output credential read/write access only to the research bucket. The CLI requires separate `CFB_R2_LAB_SOURCE_{BUCKET,ACCOUNT_ID,ACCESS_KEY,SECRET_KEY}` and `CFB_R2_LAB_{BUCKET,ACCOUNT_ID,ACCESS_KEY,SECRET_KEY}` variables; optional endpoints are `CFB_R2_LAB_SOURCE_ENDPOINT` and `CFB_R2_LAB_ENDPOINT`. It never falls back to production or Preview credentials. The buckets must differ. Do not put secrets into manifests or documentation.

Research objects live under `ratings-lab/v1/` in the research bucket. Each stage writes content-addressed Parquet or JSON children, checks their hashes, then publishes a create-once stage manifest. A rerun with identical inputs produces the same identity; a changed object at the same key fails. Readers verify the stage and every child. A partial stage without its manifest is not a completed run. [Cloudflare R2's S3 API supports conditional `PutObject` with `If-None-Match`](https://developers.cloudflare.com/r2/api/s3/api/), which the writer uses to prevent replacement.

## Pinned corpus and information policy

The importer pins the signed Repair v2, September 21 measurement and retained rating manifests, accepted 11C forecast manifest, and independent 11D verifier by URI and SHA-256. It imports the full 8,936-game schedule, 8,935 eligible games, validated game-level measurements and scoring ledger, outcomes, exact V5 bridge features, and 7,318 frozen predictions for 3,659 games in 2022–2025. The actual V5 2025 MAEs independently recompute to 14.1596 margin and 13.3558 total. The corpus also retains lower-level source references so a later versioned recipe can build a new measurement without replacing the source lineage.

The default recipe `v5_raw_ppp_game_v1` emits individual game observations from accepted raw points per possession. Each is available at kickoff plus six hours and can enter only a **later week** in that season. This is a reconstructed historical information policy, not a claim that a live pre-kickoff capture existed. Missing values remain explicit. A separate cumulative snapshot contains the complete contributor game IDs and replaces earlier snapshots. The replay engine will not add cumulative exposures repeatedly or allow a snapshot to include inadmissible games.

The established historical sequence is 2015–2019, then 2021–2025; 2020 is rejected. The calendar gap from 2019 to 2021 is preserved when a prior decays. Only 2022–2025 are headline comparison seasons. Game counts and complete eligible game keys are fixed to the V5 denominator.

## Candidate interface and comparisons

Add a versioned class implementing `candidate_id`, `mode` (`incremental` or `cumulative`), `initialize(previous, gap)`, and `estimate(prior, evidence)`. Register it with `ratings_lab.replay.register`. The engine owns the game chronology, cutoffs, contributor validation, state provenance, and explanations; a candidate supplies only rating math. `CarryoverOnly` is an infrastructure reference: standardized prior-year terminal PPP decays with rho 0.60 over the calendar-season gap and has no current-season mean update. It is **not** a V5 replacement or a possession-count correction. The tests include synthetic update classes for both evidence modes.

The common bridge swaps only the four pregame rating values in the accepted V5 feature frame. It holds schedule, outcomes, non-offense offsets, venue indicators, and completed-game stages fixed. Alpha-10 Ridge fits separately for each candidate and target on strictly earlier seasons; Gaussian variance comes from earlier rolling-origin errors. The frozen V5 predictions are imported and rescored independently. `v5-common` refits the common bridge on V5's own states; use that as the apples-to-apples reference for candidate attribution. Reports include MAE, RMSE, bias, CRPS, 90% interval coverage and width where available, seasons and stages, plus 2,000 paired season/week bootstrap replicates with seed 20260928. A candidate missing one forecast-eligible game fails the population check.

## Candidate definitions via YAML

In addition to code-registered classes, candidates can be defined declaratively in `conf/research/candidates/*.yaml`. The CLI automatically loads and registers these configs via `load_candidate_configs()` on startup.

Each YAML file specifies a `ParameterizedDesign`:

```yaml
candidate_id: exposure_k8_rho06_v1   # Unique versioned identifier
type: parameterized_exposure          # Registered factory type
k: 8.0                               # Prior weight in possessions (k > 0)
rho: 0.60                            # Inter-season carryover decay (0 < rho <= 1.0)
mode: incremental                    # "incremental" (per-game) or "cumulative" (snapshot)
description: "V5-equivalent baseline: k=8.0, rho=0.60"
```

To add a new candidate, add a `.yaml` file to `conf/research/candidates/`. Candidate IDs must be unique across code and YAML files.

## Deferred architectural decisions

As documented in [`01-v6-ratings-lab-architecture-hardening.md`](../plans/2026-09-30/01-v6-ratings-lab-architecture-hardening.md), three architectural items are intentionally deferred:
- **Dedicated R2 bucket**: Local storage remains the active research engine until private research bucket credentials are provisioned.
- **Opponent adjustment**: The opponent adjustment layer is kept fixed to V5 logic for initial candidate comparisons; alternative opponent adjustment methods are deferred to a dedicated study.
- **Batch sweep orchestration**: The CLI operates single-candidate runs for now; multi-candidate parallel execution is deferred until large candidate sweeps begin.


## Operator sequence

From the repository root, with the separate lab variables configured, run:

```bash
uv run python scripts/research/ratings_lab.py validate
uv run python scripts/research/ratings_lab.py import-corpus
uv run python scripts/research/ratings_lab.py import-corpus --apply
uv run python scripts/research/ratings_lab.py build-measurements --corpus-key <corpus-manifest-key> --apply
uv run python scripts/research/ratings_lab.py replay --corpus-key <corpus-manifest-key> --stage-key <measurement-manifest-key> --apply
uv run python scripts/research/ratings_lab.py evaluate --corpus-key <corpus-manifest-key> --stage-key v5-common --apply
uv run python scripts/research/ratings_lab.py evaluate --corpus-key <corpus-manifest-key> --stage-key <ratings-manifest-key> --apply
uv run python scripts/research/ratings_lab.py compare --corpus-key <corpus-manifest-key> --stage-key <candidate-prediction-manifest-key> --reference-key <v5-common-prediction-manifest-key> --apply
uv run python scripts/research/ratings_lab.py explain --stage-key <ratings-manifest-key> --season 2025 --game-id <game-id> --team <team> --role offense
uv run python scripts/research/ratings_lab.py status --stage-key <manifest-key>
```

Each mutating command defaults to a read/compute dry run; `--apply` is required to write. The printed manifest key is the input to the next stage. The fixed protocol is recorded at `conf/research/ratings_lab_v1/protocol.yaml`. A changed source, code, lock, config, or candidate recipe gets a new run identity. Keep a comparison report and exact parent keys with every research conclusion. Do not use any candidate for production or betting without a separate promotion contract.

As of September 28, 2026, the separate research-bucket variables are absent in this environment. Actual signed V5 parents were read with the existing Preview credentials through a read-only adapter, and a local-output end-to-end run completed in about 43 seconds. It produced 35,744 individual observations, 35,535 cumulative snapshots, 35,740 pregame states, and 7,318 common-protocol prediction rows each for V5 and the carryover reference. The carryover reference was 0.597 margin MAE and 0.051 total MAE worse than V5 under the common bridge; this is an infrastructure reference, not a selected candidate. The local run is not the required dedicated-bucket acceptance; the implementation contract remains In Progress until that run is verified.
