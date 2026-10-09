# Data-quality checks catalog

Every registered check, why it exists and the defect it prevents. The registry in
`src/cks_picks_cfb/quality/` is the source of truth; `tests/test_quality_catalog.py` fails
CI if this table and the registry disagree (a check added, removed, or re-staged without
updating this page).

Run a stage: `make data-quality STAGE={ingest|silver|gold|publish} YEAR=2026 ENV=preview`
(read-only; writes a receipt under `artifacts/quality/`, which is git-ignored).
List the registry: `PYTHONPATH=src uv run python -m cks_picks_cfb.quality --list`.

**Severity.** `block` stops a run before it can write or commit. `warn` records a failure
in the receipt without stopping anything; new checks start at `warn` and are promoted to
`block` only after a reviewed real receipt. A check whose input was not supplied reports
`skipped`: neither passed nor failed by default. Explicit `--require-check CHECK_ID` promotes failure or missing evidence to a blocking result; unknown or wrong-stage IDs are rejected.

Contract: [pipeline data-quality gates](../plans/2026-10-04/01-pipeline-data-quality-gates.md).
Definitions and evidence: `session_logs/2026-10-04/04-data-quality-task1-library.md`.

## Ingest (Bronze and catalog)

| Check | Severity | Why it exists | Defect it prevents |
|---|---|---|---|
| `ingest.capture_completeness` | warn | Every independently expected entity, season and week needs a completed capture attempt | A silently missing pull that later reads as "no games" |
| `ingest.completed_games_have_scores` | warn | Completed games must carry both final scores | Null finals flowing into reconciliation and grading |
| `ingest.games_vs_schedule` | warn | Every scheduled game was ingested exactly once (extra FBS-involved games are reported, not failed) | Missing or duplicated games |
| `ingest.odds_unmatched_events` | warn | Odds API events that matched no scheduled game are counted | Quotes lost to a name or schedule mismatch |
| `ingest.plays_and_drives_per_completed_game` | warn | Completed games need plays above a floor and drives | Truncated play-by-play capture |
| `ingest.ppa_coverage` | warn | The provider PPA column exists and its missing count is recorded before any fill | Missing PPA silently becoming a numeric zero |
| `ingest.quote_price_presence` | warn | Captured quotes carry at least some actual prices | Defaulted -110 prices mistaken for observed prices (known issue 8) |
| `ingest.schema_contract` | warn | Records the hard `validate_frame` result per dataset in the receipt | Contract failures that leave no evidence |
| `ingest.versions_pinned` | warn | Datasets with several versions at the newest `as_of` that a season filter cannot separate need an explicit pin | The wrong venues version being picked (10 games without a city) |

## Silver and Gold inputs

| Check | Severity | Why it exists | Defect it prevents |
|---|---|---|---|
| `silver.completed_game_refresh_pinned` | warn | A completed game whose result changed between versions must cite a catalogued capture with sha, object sha, uri and time (gate 6) | An unpinned correction entering a measurement build |
| `silver.drive_numbering` | warn | Drive numbers run 1..n without gaps per game and are unique per offense | Broken drive identity feeding possession metrics |
| `silver.plays_and_drives_same_games` | warn | Plays and drives cover the same games | One table silently missing a game |
| `silver.points_identity` | warn | Drive points never exceed the final score for a team-game | Excess points (known issue 1 family) |
| `silver.ppa_missing_flag` | warn | Missing provider PPA is flagged and never stored as zero | The 155 zero-filled eligible plays (known issue 3) |
| `silver.reconciliation_compares_scores` | warn | The reconciliation actually compared team scores with certified finals (a `points` column, or stream scores recorded in `source_reconciliation.details`) | A vacuous `exact_match` (known issue 7) |
| `silver.stream_scores_match_finals` | warn | Each team's score from the play stream equals the certified final; the reconciliation records mismatches without blocking | Streams that stop short or overshoot the final (known issue 1) going unreported |
| `silver.reconciliation_recorded` | warn | The persisted reconciliation has no blocking conflict (team identity and rows; scores only if the comparison can run) | A team or row conflict going unnoticed |
| `silver.score_stream_monotone` | warn | Each team's running score never decreases in drive then play order | The non-monotonic score stream (known issue 1) |

## Gold

Gold runs require explicit version pins for all four measurement datasets. These
checks verify contracts and cross-field consistency; they do not replace independent
recomputation from source plays. They start at `warn` until a reviewed real receipt exists;
release callers promote them with `--require-check`.

| Check | Severity | Invariant | Defect prevented |
|---|---|---|---|
| `gold.schema_contract` | warn | All four measurement datasets satisfy their versioned schemas | Missing datasets, duplicate keys and incompatible schema versions |
| `gold.metric_semantics` | warn | Ratios, coverage, missingness and offense/defense mirrors reconcile | Zero-filled missing values and inconsistent paired measurements |
| `gold.ledger_semantics` | warn | Possessions, scoring admission and evidence satisfy shared contracts | Invalid scoring attribution and incompatible possession references |

## Publish boundary (before and after a Neon write)

| Check | Severity | Why it exists | Defect it prevents |
|---|---|---|---|
| `publish.pre.keys` | block | Game ids are present and unique in the payload | Duplicate or null primary keys |
| `publish.pre.required_fields` | block | Required payload fields are non-null | A null prediction published as a value |
| `publish.pre.value_ranges` | block | Spreads, totals, deviations, edges and leans are within plausible bounds | Impossible numbers reaching the site |
| `publish.pre.schedule_coverage` | block | The run covers every game scheduled for its week (gate 2) | A partial slate shown as complete |
| `publish.pre.best_quote` | block | Every selected line is the best available line for its side, recomputed independently | The October Away-spread line ordering defect (known issue 13) |
| `publish.pre.venue_city` | block | Every game of a published run has a venue city (gate 3) | Cards with no location |
| `publish.pre.venue_payload` | block | Every game published to `game_venues` has one row with a city | Publishing venue rows with missing cities |
| `publish.post.predictions_readback` | block | The database holds exactly the payload's prediction keys after the write | A write that silently dropped rows |
| `publish.post.selections_readback` | block | Stored selections equal the payload's (quote, side, point) | Selections that drifted between payload and database |
| `publish.post.venues_readback` | block | Stored venue rows and cities equal the payload | A venue upsert that lost a city |
| `publish.post.grades_recomputed` | block | Stored v2 grades equal a recomputation from the frozen side, point and certified score | A grade that disagrees with its frozen selection |

## Web read side

The web app guards the database rows it renders with `web/src/lib/row-guard.ts`
(contracts for team stats, ratings, prediction games and performance detail). A violation
throws `RowContractError`; pages show their existing "temporarily unavailable" state, and the
matchup page shows "Team stats are temporarily unavailable." instead of "not published".
Values are never coerced to zero.

## Repair-track enforcement

Use `--request-inventory reviewed-inventory.json` for ingest completeness. The
`cfbd_expected_requests_v1` document binds `season`, a `schedule_ref` containing
`version_id` and `content_sha`, and a nonempty `requests` list of CFBD `provider`,
`entity`, and exact `parameters`. Derive that list from the pinned schedule and
endpoint policy, independently of ingestion attempts. Attempts alone cannot prove
completeness: without an inventory the check falls back to the attempt ledger
(`inputs.request_basis = "attempt_ledger"`), which catches failed or unretried pulls but
never a request that was not attempted. An inventory is recorded as
`request_basis = "request_inventory"`. Require `ingest.capture_completeness` to block missing inventory.
The weekly generator now derives and rereads exact requests from a schedule pin.
Broader endpoint coverage and operational receipts remain open.

Gold accepts exact pins for all four measurement datasets and verifies ordinary or
partitioned lake objects before schema and semantic checks. These checks enforce
shared contracts; they do not replace independent source-to-metric recomputation.
`--upload-receipt` explicitly enables immutable R2 receipt persistence with byte
readback; default runs remain local. Other ingestion paths, Silver builder
enforcement, reviewed production blocking policy, and legacy validator
disposition remain open.

The weekly plays/game-stats command now requires `--request-inventory`. Generate
it with `scripts/data/build_expected_request_inventory.py` from the exact raw
games object (`--raw-schedule-uri raw/games/year=2026/part-0.parquet`) and the
repository's versioned canonical-week policy. This source includes FBS–FCS games;
the Week 5 Silver `games` dataset omits three such games and cannot establish the
complete ingestion request population. The generator records the raw object's
SHA-256 and R2 ingestion rereads and verifies those bytes. R2 ingestion rereads those
sources, recomputes the request population, compares planned and captured
requests, and rejects missing completed-game responses before validated promotion.
The schedule must provide completed status or both final scores. Provider
revisions and ambiguous raw play identities remain explicit repair findings.
