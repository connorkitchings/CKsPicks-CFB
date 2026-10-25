# V5 Live 2026 Readiness Assessment

**Date:** 2026-09-17  
**Assessor:** Sol planning task  
**Status:** 🔴 **BLOCKED** — Requires 2026 data extension  
**Verified refresh:** 2026-09-18 (V5-05C Terra, read-only re-run of the 05A readiness logic) — **verdict unchanged: BLOCKED**

---

## Verified Refresh (2026-09-18, V5-05C)

The 05A readiness logic was re-run read-only against the current exact inputs
(no writes; dry-run preflight of `scripts/research/run_v5_shadow_readiness.py`)
for the next prospective slate **2026 Week 4**, cutoff
`2026-09-18T13:43:12Z`, code SHA `276fafc…` (HEAD at run time; the
certified-parent verdicts are structural and code-independent).

### Verified per-source verdict (2026 W4)

| Source | Status | Timing | Blocked reason |
|---|---|---|---|
| candidate | available | pre_cutoff | — |
| completed_games | available | pre_cutoff | — |
| priors | available | pre_cutoff | — |
| schedule | **unavailable** | missing | no schedule rows for 2026 week 4 |
| scoring | available | pre_cutoff | — |
| team_states | **unavailable** | missing | no team states for 2026 |

**Overall: `blocked`.** This matches the certified 05A assessment
(`shadow-v1-20260917-cd07d8b-05a`, same slate 2026 W4, same two structural
blockers).

### Input inventory (exact, verified)

- Forecast candidate: `forecast-v1-20260917-4600ddd-04b` (as-of 2026-09-17, frozen, Preview)
- Rating parent: `possession-v1-ratings-20260917-d029526-cert` (as-of 2026-09-17T01:55:00Z)
- Measurement parent: `possession-v1-measurements-20260915-18fb0aa-r6` (as-of 2026-09-15T19:16:30Z)
- Repair parent: `repair-v2-20260909T1417Z`
- All certified parents cover development seasons only (2015–2019, 2021–2025); **none contains 2026 rows**.

### Blockers (verified, current)

1. **No 2026 possession measurements.** The certified R6 population contains no
   2026 season rows, so the schedule source resolves `missing` for any 2026
   slate. Requires the measurement pipeline extension (separate contract).
2. **No 2026 team states.** The certified rating parent stops at 2025, so
   `team_states` resolves `missing` for 2026. Requires the rating pipeline
   extension and updated priors for 2026 (blocked on 1).
3. **Preview environment lag** (context, not separately re-verified in this
   refresh): the 2026-09-17 finding that Preview trails production (2026 weeks
   0–1 vs 0–3) stands as recorded below; clearing blockers 1–2 requires a
   Preview data synchronization step regardless.

### Live-state note (2026-09-18)

Week 3 (`2026w3-68fe6a815bd6`) is frozen and in progress (earliest kickoff
2026-09-17 23:30Z); close is pending. Nothing in this assessment mutated any
production or Preview serving state. A verified `blocked` readiness is the
contractually complete 05C outcome: Contract 06 cannot collect eligible
prospective evidence until the blockers above clear and six qualifying
pre-frozen slates accumulate thereafter.

---

## Historical Assessment (2026-09-17, preserved)

## Executive Summary

The V5 forecast candidate (`forecast-v1-20260917-4600ddd-04b`) is **certified** for historical development (2015-2019, 2021-2025) but **not ready** for live 2026 prospective operation. The certified artifact was trained on historical data and does not include 2026 team states, ratings, or measurements.

**Key Finding:** To run V5 prospectively on 2026 games, we must extend the measurement and rating pipelines to include 2026 data, then run the forecast candidate on the updated team states. This is a non-trivial engineering task that goes beyond the scope of Contract 05's "tooling" focus.

---

## Current State

### V5 Certified Artifacts

| Artifact | Run ID | Coverage | Status |
|---|---|---|---|
| Possession Measurements | `possession-v1-measurements-20260915-18fb0aa-r6` | 2015-2019, 2021-2025 | ✅ Certified |
| Possession Ratings | `possession-v1-ratings-20260917-d029526-cert` | 2015-2019, 2021-2025 | ✅ Certified |
| Forecast Bridge | `forecast-v1-20260917-4600ddd-04b` | 2015-2019, 2021-2025 | ✅ Certified |

**All certified artifacts exclude 2026 data.**

### Production Database (2026)

| Metric | Value |
|---|---|
| 2026 games | 157 |
| 2026 game_results | 100 |
| Weeks with games | 0, 1, 2, 3 |
| Current week | 2026W3 (frozen) |
| Scored weeks | 0, 1, 2 |

### Preview Database (2026)

| Metric | Value |
|---|---|
| 2026 games | 51 |
| 2026 game_results | 0 |
| Weeks with games | 0, 1 |
| Current week | 2025W16 (replay) |

**Preview is lagging behind production.**

---

## What's Missing for Live 2026 V5 Operation

### 1. 2026 Possession Measurements

The certified measurement manifest covers development seasons only. For live 2026 operation, we need:

- **2026 play-by-play data** → possession measurements
- **2026 scoring events** → scoring ledger
- **2026 game outcomes** → final scores

**Status:** ❌ Not yet computed

### 2. 2026 Team States

The certified rating manifest provides team states through 2025. For live 2026 operation, we need:

- **2026 team states** updated with Week 0-3 games
- **2026 rating states** with current-season evidence

**Status:** ❌ Not yet computed

### 3. 2026 Forecast Predictions

The certified forecast bridge was trained on historical data. For live 2026 operation, we need:

- **2026 predictions** using the frozen algorithm
- **2026 team states** as inputs to the bridge

**Status:** ❌ Not yet computed

---

## Blockers

### Blocker 1: No 2026 Measurement Pipeline

The measurement pipeline (`scripts/research/run_data_first_possession_measurements.py`) was designed for historical certification. It does not currently support:

- Incremental 2026 measurement updates
- Live data ingestion from 2026 games
- Extending the certified measurement manifest

**Impact:** Cannot compute 2026 possession measurements without extending the pipeline.

### Blocker 2: No 2026 Rating Pipeline

The rating pipeline (`scripts/research/run_data_first_possession_ratings.py`) was designed for historical certification. It does not currently support:

- Incremental 2026 rating updates
- Updating team states with 2026 game evidence
- Extending the certified rating manifest

**Impact:** Cannot compute 2026 team states without extending the pipeline.

### Blocker 3: Preview Database Lag

The Preview database only has 2026 data through Week 1, while Production has through Week 3. This suggests:

- Data ingestion is not synchronized between environments
- Preview may not have the latest 2026 games/outcomes

**Impact:** Cannot run V5 on 2026 data in Preview without first synchronizing the database.

---

## What Contract 05 Can Do

Contract 05 ("Prospective Readiness and Shadow Tooling") is scoped to build **tooling** for shadow operations, not to extend the measurement/rating pipelines. Specifically:

### In Scope for Contract 05

1. **Source availability validation** — Check if 2026 inputs are available (they're not, yet)
2. **Frozen algorithm replay** — Prove identical forecasts from identical inputs (requires 2026 team states)
3. **Shadow freeze operations** — Implement T-2h/T-1h timing validation (requires 2026 predictions)
4. **Outcome-versioned scoring** — Score finalized games (requires 2026 predictions + outcomes)
5. **Historical rehearsal** — Run diagnostic rehearsal on historical data (can do this now)

### Out of Scope for Contract 05

1. **Extending measurement pipeline** — Not in Contract 05 scope
2. **Extending rating pipeline** — Not in Contract 05 scope
3. **Computing 2026 measurements/ratings** — Requires new engineering work
4. **Synchronizing Preview database** — Operational task, not research

---

## Recommended Path Forward

### Option A: Contract 05 with "Blocked" Readiness

**Approach:** Implement Contract 05 tooling, document that live 2026 readiness is blocked, and defer prospective evidence collection until the measurement/rating pipelines are extended.

**Pros:**
- Stays within Contract 05 scope
- Builds tooling that will be needed later
- Honest assessment of current state
- Does not block V4 production

**Cons:**
- Cannot collect prospective evidence in 2026
- Delays V5 evaluation timeline
- Requires additional engineering work outside Contract 05

**Timeline:**
- Contract 05 implementation: 1-2 weeks
- Measurement/rating pipeline extension: 2-3 weeks (separate contract)
- Prospective evidence collection: 2026 season (ongoing)

### Option B: Extend Measurement/Rating Pipelines First

**Approach:** Before Contract 05, extend the measurement and rating pipelines to support 2026 data, then run Contract 05 with live-ready tooling.

**Pros:**
- Enables prospective evidence collection in 2026
- Provides end-to-end V5 operational capability
- Validates the full pipeline on live data

**Cons:**
- Requires additional engineering work before Contract 05
- Extends timeline before prospective evidence
- May require new contracts for pipeline extension

**Timeline:**
- Pipeline extension: 2-3 weeks (new contract)
- Contract 05 implementation: 1-2 weeks
- Prospective evidence collection: 2026 season (ongoing)

### Option C: Hybrid — Contract 05 with Pipeline Extension Scope

**Approach:** Expand Contract 05 scope to include minimal pipeline extension for 2026 data, then implement shadow tooling.

**Pros:**
- Single contract covers end-to-end readiness
- Enables prospective evidence collection
- Keeps related work together

**Cons:**
- Expands Contract 05 scope significantly
- May exceed original contract intent
- Requires careful scope management

**Timeline:**
- Contract 05 (expanded): 3-4 weeks
- Prospective evidence collection: 2026 season (ongoing)

---

## Recommendation

**Recommend Option A: Contract 05 with "Blocked" Readiness**

**Rationale:**
1. **Stays within scope** — Contract 05 is explicitly scoped to tooling, not pipeline extension
2. **Honest assessment** — Documents that live 2026 readiness is blocked, which is the truth
3. **Does not block production** — V4 continues operating normally
4. **Builds foundation** — Contract 05 tooling will be needed regardless of when pipeline extension happens
5. **Separates concerns** — Pipeline extension is a distinct engineering task that deserves its own contract

**Next Steps:**
1. Implement Contract 05 tooling (shadow freeze, scoring, ledger, rehearsal)
2. Document "blocked" readiness with specific blockers
3. Create a separate contract for measurement/rating pipeline extension (if/when approved)
4. Once pipelines are extended, re-run Contract 05 readiness check
5. Begin prospective evidence collection

---

## Detailed Blocker Analysis

### Blocker 1: Measurement Pipeline Extension

**Current State:**
- Measurement pipeline is designed for historical certification
- Certified manifest covers 2015-2019, 2021-2025
- No support for incremental 2026 updates

**Required Work:**
1. Design incremental measurement update protocol
2. Implement 2026 data ingestion from play-by-play
3. Extend measurement manifest to include 2026
4. Verify 2026 measurements against historical baseline
5. Document timing and cutoff requirements

**Estimated Effort:** 2-3 weeks

**Dependencies:**
- 2026 play-by-play data availability (✅ exists in production)
- 2026 game outcomes (✅ exists for weeks 0-2)
- Measurement pipeline code (✅ exists, needs extension)

### Blocker 2: Rating Pipeline Extension

**Current State:**
- Rating pipeline is designed for historical certification
- Certified manifest covers 2015-2019, 2021-2025
- No support for incremental 2026 updates

**Required Work:**
1. Design incremental rating update protocol
2. Implement 2026 team state updates
3. Extend rating manifest to include 2026
4. Verify 2026 ratings against historical baseline
5. Document timing and cutoff requirements

**Estimated Effort:** 2-3 weeks

**Dependencies:**
- 2026 measurements (❌ blocked by Blocker 1)
- Rating pipeline code (✅ exists, needs extension)
- Certified rating manifest (✅ exists, needs extension)

### Blocker 3: Preview Database Synchronization

**Current State:**
- Preview has 2026 data through Week 1
- Production has 2026 data through Week 3
- Databases are not synchronized

**Required Work:**
1. Ingest 2026 Weeks 2-3 into Preview
2. Verify data consistency between environments
3. Document synchronization protocol

**Estimated Effort:** 1-2 days

**Dependencies:**
- 2026 game data (✅ exists in production)
- Preview database access (✅ exists)
- Data ingestion scripts (✅ exist)

---

## Conclusion

The V5 forecast candidate is **certified** but **not live-ready** for 2026 prospective operation. The blockers are real and require engineering work outside the scope of Contract 05.

**Recommendation:** Implement Contract 05 with "blocked" readiness, document the blockers clearly, and defer prospective evidence collection until the measurement/rating pipelines are extended in a separate contract.

This approach:
- Stays within Contract 05 scope
- Builds necessary tooling
- Provides honest assessment
- Does not block V4 production
- Sets up future prospective evaluation

**Status:** 🔴 **BLOCKED** — Requires measurement/rating pipeline extension before live 2026 operation.
