# The Odds API Historical Backfill Exploration (2021–2025)

- **Status:** Estimates complete; probes pending user approval (no spend
  committed beyond the two approved 2-credit live rehearsals)
- **Contract:** `docs/plans/2026-09-03/market-line-retention.md` (Task 5, D7)
- **Policy:** research-only, budget-gated. Backfilled quotes would carry
  authentic provider snapshot timestamps and enter canonical `market_quotes`
  (never `legacy_market_references`), and can never alter a published or frozen
  artifact. 2020 is permanently excluded.

## Motivation

The 2021–2025 CFBD lines were quarantined because they lack authentic quote
timestamps (decision log 2026-08-09). The Odds API historical endpoint
(`/v4/historical/sports/americanfootball_ncaaf/odds`, 20 credits per snapshot
with regions=us × spreads+totals) returns the odds board as it stood at a
requested timestamp, so a backfill would recover genuinely timestamped lines —
the only feasible recovery path for pre-2026 market history.

## Step 1 — Per-season estimates (0 credits)

Run from a shell with `CFB_R2_*` (or local backend) credentials; the estimator
never contacts the provider:

```bash
for YEAR in 2021 2022 2023 2024 2025; do
  # Export the season's Silver games schedule (one-off; adjust ref resolution
  # to the latest validated games version for the season), then:
  PYTHONPATH=.:src uv run python scripts/data/estimate_historical_odds_backfill.py \
      --schedule /tmp/games_${YEAR}.csv
done
```

Record results below. The estimator counts one snapshot per distinct kickoff
timestamp; a denser cadence (e.g., daily through game week) multiplies cost
proportionally.

| Season | Games | Distinct kickoffs | Snapshot requests | Credits (sparse) |
| --- | --- | --- | --- | --- |
| 2021 | 732 | 267 | 267 | 5,340 |
| 2022 | 734 | 266 | 266 | 5,320 |
| 2023 | 750 | 265 | 265 | 5,300 |
| 2024 | 753 | 296 | 296 | 5,920 |
| 2025 | 762 | 305 | 305 | 6,100 |
| **Total** | **3,731** | **1,399** | **1,399** | **27,980** |

Measured 2026-09-03 against the validated Silver games corpus (per-season
filter; each season's rows drawn from the shared multi-season dataset
version). Sparse cadence = one historical snapshot per distinct kickoff
timestamp. A 2025-only backfill costs ~6,100 credits at this cadence; a
denser cadence (e.g., daily through game week) multiplies cost accordingly.
The free tier is 500 credits/month, so any "go" implies a paid plan and
should size the tier to the chosen cadence.

## Step 2 — Coverage probes (20 credits each; explicit approval required)

The Odds API's historical coverage depth for NCAAF is unverified for this
account. Before any go decision, run one probe per era in doubt (suggested:
one 2025 snapshot, one 2021 snapshot) via the historical adapter at a known
pre-kickoff timestamp. Each probe must be individually approved by the user.

A probe verifies:

1. The provider returns NCAAF data for the requested date (coverage depth).
2. `match_odds_events_to_schedule` match rate against the Silver schedule.
3. Payload quality (bookmakers, spreads/totals, prices).

| Probe | Timestamp | Credits | Coverage? | Match rate | Notes |
| --- | --- | --- | --- | --- | --- |
| 2025 era | TBD | 20 | TBD | TBD | TBD |
| 2021 era | TBD | 20 | TBD | TBD | TBD |

## Step 3 — Go/no-go

Proceed to a backfill contract only if:

- Probes confirm usable coverage for the target seasons.
- Total estimated spend fits the approved budget.
- The match rate is high enough that unmatched games remain the exception
  (logged, never guessed).

A "go" requires a new contract or an amendment to
`docs/plans/2026-09-03/market-line-retention.md` before any bulk execution;
backfilled quotes land in R2 Bronze/Silver `market_quotes` only, and Neon
population of historical quotes is a separate decision.
