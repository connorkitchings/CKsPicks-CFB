# Historical Data Inventory (2012–2026)

This document is the canonical inventory of college football data captured from the CFBD API into the Cloudflare R2 Bronze lake (`lake/bronze/provider=cfbd/...` and `raw/...`) and registered in the Neon Postgres `catalog.source_captures` metadata catalog.

---

## 1. Storage Architecture & Lineage Rules

- **Source of Truth:** Cloudflare R2 bucket configured via `CFB_STORAGE_BACKEND='r2'` (production: `cks-picks-cfb-preview` / `cks-picks-cfb`).
- **Metadata Catalog:** Neon Serverless Postgres (`catalog.source_captures`), tracking content SHA-256 hashes, record counts, partition keys, and registration timestamps.
- **Dual-Write Architecture:** Every raw entity write saves both the queryable entity partition (`raw/{entity}/year={YYYY}/...`) and the immutable Bronze capture (`lake/bronze/provider=cfbd/entity={entity}/...`).
- **Forbidden Lineage Rule:** Season **2020** is strictly forbidden and globally excluded from all training, ratings, features, and schedules per core repository guardrails.

---

## 2. Ingested Data Inventory

All data below is captured in R2 Parquet format and registered in `catalog.source_captures`.
The table is the queryable compatibility projection, which can exclude malformed
provider rows during normalization. Bronze capture counts are the immutable
lineage authority.

### Summary by Season

| Season | Teams | Coaches | Rosters | Ret. Prod. | Venues | Recruiting | Rankings (Polls) | FBS Games | Betting Lines |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2026 (Live)** | 136 | 134 | 16,842 | 134 | 148 | 235 | 50 | 892 | 344 |
| **2025** | 136 | 161 | 15,599 | 134 | 148 | 232 | 2,052 | 888 | 2,299 |
| **2024** | 134 | 152 | 16,221 | 133 | 151 | 194 | 2,028 | 874 | 1,678 |
| **2023** | 133 | 143 | 15,918 | 131 | 150 | 177 | 1,902 | 868 | 2,446 |
| **2022** | 131 | 146 | 15,548 | 130 | 144 | 184 | 1,950 | 854 | 3,184 |
| **2021** | 130 | 152 | 15,129 | 128 | 148 | 191 | 1,400 | 849 | 2,869 |
| **2020** | *Excluded* | *Excluded* | *Excluded* | *Excluded* | *Excluded* | *Excluded* | *Excluded* | *Excluded* | *Excluded* |
| **2019** | 130 | 134 | 15,558 | 130 | 144 | 223 | 1,704 | 848 | 3,071 |
| **2018** | 130 | 139 | 14,511 | 130 | 148 | 229 | 1,600 | 845 | 2,887 |
| **2017** | 130 | 139 | 14,757 | 128 | 144 | 233 | 1,600 | 834 | 2,289 |
| **2016** | 128 | 134 | 14,714 | 128 | 148 | 238 | 1,603 | 832 | 2,225 |
| **2015** | 128 | 132 | 15,010 | 128 | 151 | 231 | 1,577 | 829 | 2,198 |
| **2014** | — | — | — | — | — | 231 | — | — | — |
| **2013** | — | — | — | — | — | 210 | — | — | — |
| **2012** | — | — | — | — | — | 183 | — | — | — |
| **Total** | **1,446** | **1,566** | **169,807** | **1,434** | **1,624** | **2,987** | **17,466** | **9,360** | **25,490** |


---

## 3. Entity Details & Primary Consumers

### Pregame Evidence Families (`PREGAME_FAMILIES`)
The four foundational pregame evidence families approved for data-first forecasting are now 100% complete across all 10 historical seasons (2015–2019, 2021–2025):

1. **Games (`raw/games/year={YYYY}/part-0.parquet`)**:
   - Covers regular season schedules, home/away scores, neutral site flags, conference classifications, and venue associations.
   - Total: 8,468 historical games (9,360 including 2026).
2. **Returning Production (`raw/returning_production/year={YYYY}/part-0.parquet`)**:
   - Ingested via `ReturningProductionIngester`. Contains total, offensive, and defensive PPA returning percentages and usage returning metrics.
   - Bronze total: 1,300 historical team-seasons (1,434 including 2026).
3. **Recruiting Rankings (`raw/recruiting/year={YYYY}/part-0.parquet`)**:
   - Ingested via `RecruitingIngester`. Contains 247Sports Composite points and national ranks.
   - Ingested for **2012 through 2025** so that 2015 has a complete 4-year rolling window (`recruiting_4yr`, `recruiting_current`, `recruiting_trend`).
   - Total: 2,752 historical ranking records (2,987 including 2026).
4. **Head Coaches (`raw/coaches/year={YYYY}/part-0.parquet`)**:
   - Ingested via `CoachesIngester`. Contains head coach tenures, hire dates, and season records.
   - Total: 1,432 historical coach-seasons (1,566 including 2026).

### Supplementary Matchup & Edge Entities
- **Betting Lines (`raw/betting_lines/year={YYYY}/week={W}/part-0.parquet`)**:
  - Ingested via `BettingLinesIngester`. Covers consensus and major sportsbook (Bovada, DraftKings, ESPN Bet, etc.) spreads, totals, and moneyline quotes.
  - Used strictly post-model as a reconstructed diagnostic reference. It is not
    authentic closing-line or CLV evidence.
  - Bronze total: 26,844 historical quotes. The compatibility projection has
    25,146 historical rows after normalization; every exclusion is subject to
    the Phase 2e ledger.
- **Venues (`raw/venues/year={YYYY}/part-0.parquet`)**:
  - Ingested via `VenuesIngester`, filtered against the active games index for each season.
  - Contains stadium capacity, elevation, grass vs. turf, dome flag, coordinates, and timezone.
  - Total: 1,476 historical venue records (1,624 including 2026).
- **Rankings (`raw/rankings/year={YYYY}/part-0.parquet`)**:
  - Ingested via `RankingsIngester`. Weekly national polling data from AP Top 25 and Coaches Poll (ranks, first-place votes, poll points).
  - Total: 17,416 historical ranking entries (17,466 including 2026).
- **Rosters (`raw/rosters/year={YYYY}/part-0.parquet`)**:
  - Ingested via `RostersIngester`. Contains player names, jersey numbers, positions, heights, weights, and home towns.
  - Total: 152,965 historical player records (169,807 including 2026).
- **Teams (`raw/teams/year={YYYY}/part-0.parquet`)**:
  - Ingested via `TeamsIngester`. Canonical FBS school metadata, mascot names, abbreviations, and conferences.
  - Total: 1,310 historical team records (1,446 including 2026).

### In-Game Performance & Aggregated Metrics
- **Plays & Play-by-Play (`raw/plays/`)**:
  - Phase 2c has sealed checksum-verified Preview play and derived-measurement
    evidence for every permitted development season: 2015–2019 and 2021–2025.
    Its exact 80-ref handoff, rather than this compatibility inventory, governs
    Phase 3 research eligibility.

---

## 4. What Data Is Redundant, Missing, or Excluded

### 1. Independent Reconciliation Evidence
- **Game Stats / Box Scores (`raw/game_stats`)**:
  - Play-by-play remains the measurement source, while box scores provide
    independent source-reconciliation evidence in the Phase 2c/2d contract.
    Neither is silently substituted for the other.

### 2. External Third-Party Ratings (Offline Ingestion Required)
- **SP+, FPI, and SRS ratings**:
  - CFBD historically discontinued open SP+/FPI API endpoints due to licensing restrictions.
  - These require offline CSV ingestion via `src/cks_picks_cfb/data/external_ratings.py` if used as benchmark baselines.

### 3. Intentionally Excluded / Rejected Sources
- **2020 Season**:
  - Excluded by architecture design across all tables to avoid distorted COVID-year sample sizes.
- **Transfer Portal (`transfers`)**:
  - The NCAA transfer portal only began operating reliably around 2021. To prevent breaking the 2015–2019 chronology with non-existent data, player transfer volume is intentionally omitted from the core rating lineage.
- **247 Team Talent Composite (`talent`)**:
  - Omitted because CFBD talent rankings only started around 2015–2016 and overlap heavily with the 4-year rolling recruiting composite (`recruiting_4yr`), which spans back to 2012 cleanly.
