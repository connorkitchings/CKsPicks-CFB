# 2026 CFBD Provider and Integration Audit

**Audit date:** 2026-08-04  
**Scope:** official CFBD offerings, current REST contracts, this repository's
integration, and a no-code-change roadmap.  
**Out of scope:** provider purchases, subscription changes, GraphQL calls,
production R2/Neon writes, model changes, and dependency upgrades.

## Executive summary

CollegeFootballData has expanded from a REST-data site into a broader product
surface: a REST API, tier-gated live data, GraphQL queries and subscriptions,
an exporter, and downloadable modeler products. The live REST documentation
reports version **5.17.0** while this repository has `cfbd` **5.16.0** pinned.
The existing ingestion subset works against the current service. The upgrade
resolved the observed player-recruiting and live-play validation failures, but
aggregated recruiting still fails client-side validation on current responses;
that endpoint remains blocked from adoption.

The current Tier 2 key is adequate for the existing weekly REST path. It does
not authorize GraphQL. The most immediate operational issue is seasonal source
availability, not access: the 2026 schedule, coaches, recruiting, transfers,
and preliminary rankings are available, while rosters, talent, and returning
production are not.

## Evidence and provider surface

### Official sources

- [REST API documentation](https://api.collegefootballdata.com/) — live Swagger
  catalog, version 5.17.0, endpoint and model inventory.
- [API tiers](https://collegefootballdata.com/api-tiers) — call allowances and
  feature access; Tier 3+ is required for GraphQL.
- [GraphQL documentation](https://graphqldocs.collegefootballdata.com/) and
  [subscription guide](https://radsportsanalytics.com/blog/subscribing-to-data-events-with-the-cfbd-graphql-api/)
  — query/subscription semantics and the partial GraphQL surface.
- [REST v2 transition note](https://radsportsanalytics.com/blog/api-v2-is-now-in-general-availability/)
  — historical migration context; the post is explicit that the current REST
  documentation is authoritative.
- [CFBD homepage](https://collegefootballdata.com/) and
  [key/exporter entry point](https://collegefootballdata.com/key) — 2026
  Starter Pack, AI API Launchpad, planned Builder/Model Training products, and
  exporter positioning.
- [Terms](https://collegefootballdata.com/terms) — key ownership and use
  constraints. Do not embed a key in a public repository or client bundle.

### Access baseline

| Item | Observed result | Audit implication |
| --- | --- | --- |
| REST catalog | 5.17.0 | Evaluate generated-client compatibility before adding endpoints. |
| Installed Python client | `cfbd` 5.16.0, constrained below 5.17 | Latest published client at audit time; compatibility tests protect adopted endpoints. |
| Account | Tier 2, 30,000 monthly calls | REST and live endpoints are usable; GraphQL is not. |
| Bounded audit consumption | 50 calls; 29,933 remained | Under the 200-call audit cap. |
| GraphQL | Tier 3+ requirement | Defer; do not create polling or subscription code. |

### Products and delivery paths

| Offering | What the public site says | Fit for this repository | Decision |
| --- | --- | --- | --- |
| REST API | Historical, operational, player, advanced, ratings, and betting data | Current system of record for raw ingestion | Retain and harden. |
| GraphQL | Dynamic queries and data subscriptions | Could reduce line-update polling for a production app | Defer: Tier 2 has no access and REST is sufficient. |
| Exporter | Browser workflow for previewing queries and pulling CSVs | Useful for analyst spot checks and reproducing a request | Adopt manually; do not make it a production dependency. |
| 2026 Starter Pack / AI Launchpad | Paid notebooks, CSV-ready workflows, and training material | Potential research acceleration only | Defer purchase; evaluate contents/license before adopting. |
| Model Training / Builder products | Announced or scheduled product line | May overlap this repository's proprietary pipeline | Defer until released and compared against point-in-time requirements. |

### REST catalog disposition

This is the complete disposition of the REST API groups exposed by the live
Swagger catalog. A group can be a candidate even when none of its endpoints is
yet an approved model feature.

| REST group | Repository status | Disposition |
| --- | --- | --- |
| Games | games, game stats, schedule, scoring | Current; retain and contract-test. |
| Drives | no direct raw ingester | Candidate for aggregation validation. |
| Plays | primary raw feature input | Current; retain and contract-test. |
| Teams | teams, rosters, talent, preseason snapshot | Current; availability-gate roster/talent feeds. |
| Conferences | no persistence | Candidate static reference; do not add without a consumer. |
| Venues | raw venue ingestion | Current; retain. |
| Coaches | raw coach ingestion and preseason snapshot | Current; retain. |
| Players | usage, returning production, portal | Candidate; portal supports preseason research, returning feed is unavailable today. |
| Rankings | raw ranking ingestion | Current external-feature input; availability-gate. |
| Betting | raw sportsbook lines | Current; enforce per-game provider-line coverage. |
| Recruiting | team ranking ingestion | Current subset only; player responses parse in 5.16.0, but aggregated ratings remain blocked. |
| Ratings | SP, Elo, FPI, SRS | Candidate; require point-in-time historical evaluation. |
| Metrics | PPA, win probability, field-goal EP | Candidate; distinguish pregame from postgame fields. |
| Stats | standard and advanced team/player statistics | Candidate and independent validation source; avoid duplicate feature paths. |
| Adjusted metrics | WEPA and PAAR | Candidate; require temporal-leakage review. |
| Draft | no CFB betting-model consumer | Irrelevant for the current product; do not integrate. |
| Info | account and usage metadata | Operational; use for bounded-call monitoring only. |

## Contract probe results

All probes used direct REST calls, recorded only aggregate counts and model
field names, and did not invoke the R2-backed ingesters. Historical coverage
was sampled with 2019, 2024, and 2025 Week 1 requests; 2026 represents the
preseason/current-state check.

| API area | Result | Repository disposition |
| --- | --- | --- |
| Games and schedule | Week 1 FBS counts: 2019 85, 2024 100, 2025 96, 2026 99. Calendar, media, weather, records, advanced box, team stats, and player stats returned compatible models. | **Current/retain.** `raw/games` drives schedule, scoring, and features. |
| Plays and drives | 2025 Week 1 drives, Georgia plays, play types, stat types, and play stats returned compatible models. | **Current/retain.** `raw/plays` remains the canonical feature input; drives are a candidate for future direct validation. |
| Live data | Scoreboard returned data; the 5.16.0 upgrade parses a completed-game `live/plays` response. | **Defer polling.** Contract-compatible, but no live consumer is authorized yet. |
| Teams, venues, conferences, coaches | 2026 API response included 684 teams / 138 FBS teams, 844 venues, 106 conferences, and 138 coaches. | **Current/retain.** The ingesters correctly filter to FBS and store 138 teams and 150 schedule-used venues. |
| Rosters | 15,171 FBS players returned for 2026. | **Available.** Ingested to `raw/rosters/year=2026` on 2026-08-08. |
| Returning production | 136 teams returned for 2026. | **Available.** Capture only as part of a complete immutable preseason snapshot. |
| Talent | Valid empty collection for 2026. | **Seasonally unavailable.** Do not write an empty partition; still gates the preseason snapshot. |
| Transfers and rankings | 4,434 transfer records and one 2026 ranking week were available. | **Candidate/current support.** Preserve as an availability-checked preseason input; rankings can feed existing external features. |
| Betting | 99 Week 1 game envelopes were available. Prior R2 refresh flattened 101 sportsbook records covering only 51 games. | **Current with caveat.** An envelope is not a usable line; require per-game provider-line coverage before publish. |
| Recruiting | Team rankings returned 221 rows. The 5.16.0 upgrade parses player recruiting, but aggregated team ratings still raise `pydantic` validation errors with correct request shapes. | **Current subset only.** Keep team-ranking ingestion; block aggregated recruiting features pending an upstream-compatible client. |
| Ratings | SP (137), Elo (136), FPI (136), and SRS (266) returned 2025 records. | **Candidate.** Evaluate only with point-in-time snapshots; do not feed postgame or revised ratings into historical training. |
| Metrics and stats | Team PPA, win probability, pregame win probability, field-goal EP, team/advanced stats, and categories returned compatible models. | **Candidate.** Useful for research and validation, not automatic model inputs. |
| Adjusted metrics | Team WEPA and player passing/rushing WEPA plus kicker PAAR returned compatible models. | **Candidate.** Evaluate as independent features after temporal-leakage review. |

## Repository integration map

| Provider call | Raw/snapshot destination | Downstream use | State |
| --- | --- | --- | --- |
| `TeamsApi.get_teams` | `raw/teams` | game, roster, coach dependencies; feature persistence | Working |
| `GamesApi.get_games` | `raw/games` | schedule, scoring, feature persistence, weekly publish | Working |
| `VenuesApi.get_venues` | `raw/venues` | feature persistence | Working; requires fresh games first |
| `PlaysApi.get_plays` | `raw/plays` | team-game and adjusted feature pipeline | Working |
| `GamesApi.get_game_team_stats` | `raw/game_stats` | raw-stat validation | Working |
| `BettingApi.get_lines` | `raw/betting_lines` | pregame line comparison and publish | Working; coverage must be checked |
| `CoachesApi.get_coaches` | `raw/coaches` | preseason research | Working |
| `RecruitingApi.get_team_recruiting_rankings` | `raw/recruiting` | external features | Working |
| `RankingsApi.get_rankings` | `raw/rankings` | external features | Working when provider has a poll |
| `TeamsApi.get_roster` | `raw/rosters` | future/preseason research | Working; 15,171 players ingested 2026-08-08 |
| Returning production, portal, talent, coaches, recruiting | immutable `raw/preseason/*` snapshot | opt-in preseason candidate | Incomplete; only `talent` remains missing for a complete 2026 snapshot |

The normal weekly path calls the season games refresh and target-week lines
refresh before feature generation. It writes an artifact and Neon only through
`make publish-week`; raw data research and refreshes must use the narrower
ingestion commands.

## Data availability calendar (observed 2026-08-04, updated 2026-08-08)

| Source | State | Operating rule |
| --- | --- | --- |
| Teams, games, venues, coaches, team recruiting | Available | Refresh into R2 when needed. |
| Week 1 betting envelopes | Available | Recheck provider-line coverage before a full-slate publish. |
| Rankings | One preseason week available | Ingest only when nonempty; rerun after later polls publish. Ingested 2026-08-08 (Coaches Poll, 25 records). |
| Transfers | Available | Can be captured only as part of a complete immutable preseason snapshot. |
| Rosters | Available | Ingested 2026-08-08 (15,171 players); refresh when needed. |
| Returning production | Available | Capture only as part of a complete immutable preseason snapshot. |
| Talent | Empty | Recheck later in August; do not write empty data or snapshot. |
| Plays and game stats | Not applicable until games complete | Run only after CFBD publishes finals/completed-game data. |

## Decision-ready roadmap

| Priority | Change | Benefit | Access/cost | Risk and validation gate | Recommendation |
| --- | --- | --- | --- | --- | --- |
| P0 | Keep the provider audit, quickstart, and ingestion guide current. | Removes obsolete local-CSV, legacy-hostname, and pre-2026 instructions. | None | Documentation build and link validation. | **Adopt now** (this audit). |
| P1 | Upgrade `cfbd` to an exact release compatible with the live catalog; add response-contract fixtures for recruiting and live plays. | Resolves observed generated-model drift before new endpoint adoption. | Tier 2 unchanged | Probe current endpoints plus failed recruiting/live models before and after; no R2 write until compatibility passes. | **Adopted 2026-08-04.** Aggregated recruiting remains blocked. |
| P2 | Add an availability/coverage gate to ingestion: distinguish empty, entitlement failure, schema failure, and usable data; require per-game provider-line coverage for a publish. | Prevents empty preseason snapshots and partial-line slates from looking complete. | Tier 2 unchanged | Unit tests for all four states plus an R2 read-only coverage check. | **Adopted 2026-08-04.** |
| P3 | Evaluate drives, advanced stats, ratings, PPA/WP, and WEPA in point-in-time historical experiments. | Expands candidate features and independent validation sources. | Tier 2 unchanged | 2019/2021–2023 training only, 2024 holdout, no full-season or postgame leakage. | **Research first.** |
| P4 | Evaluate Tier 3 GraphQL and paid packs only after a documented cost/license and operational benefit review. | Could support line-update subscriptions or accelerate research. | Subscription/purchase required | Prototype in isolation; no production dependency without explicit approval. | **Defer.** |

## Documentation corrections made by this audit

- The canonical REST documentation is `api.collegefootballdata.com`; the
  project no longer presents `apinext` as the operational endpoint.
- Production ingestion uses the R2 storage backend, not local CSV partitions.
- `venues` depends on current games; teams precede rosters and coaches; games
  precede plays, lines, and game stats.
- Current FBS team count is 138 for 2026, not the 2024 count preserved in old
  material.
- A zero-row provider response is recorded as seasonal availability, not proof
  that the ingestion path succeeded.
