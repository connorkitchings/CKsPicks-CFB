# Data-First Football Forecasting Roadmap

> **Status:** Approved 2026-09-05; corrective replacement 2026-09-08; V5 package approved 2026-09-13
> **Production authority:** V4 remains unchanged
> **Research namespace:** `artifacts/research/data-first-football-v1/`

## Purpose

Improve spread and total forecasts by establishing trustworthy data, validating
football measurements, selecting simple team ratings, and evaluating frozen
forecasts prospectively. Authentic timestamped lines are comparison evidence
after football-model evaluation. Bet selection, staking, bankroll management,
and betting-policy optimization are deferred.

Preserving the working system is mandatory. The program does not modify V4
production predictions, weekly operations, publication, bundle loading, or
rollback behavior. Corrected research behavior receives new versioned
identities when a shared change could affect production.

## Current V5 checkpoint (2026-09-22)

The [current V5 status guide](../modeling/v5_status.md) is the concise authority for model completion, certified lineage, results, and remaining operational work. V5 historical model development is complete and accepted; V4 still serves the public site. The Week 4 refresh of 07/08 remains a current-input gate for Contract 09, not an unfinished modeling milestone. Code for live forecasts, shadow readiness, and prospective reporting is ready; no operational 09 apply or qualifying slate exists yet.

The [verified cutover contract](../plans/2026-09-22/04-v5-authority-simplification-and-site-cutover.md) replaces the older six-slate prelaunch sequence. A current independently verified forecast, Preview serving rehearsal, V4 rollback proof, and a separate activation decision precede site replacement. Contract 06 keeps prospective freezes and outcome reports as monitoring after launch; 2026 outcomes never refit the frozen V5 identity. The original Phase 4B retained manifest remains prohibited as a forecasting parent. Detailed dated sections below preserve research history and should not override this current checkpoint.

## Governing boundaries

- Target all games involving at least one FBS team, including FBS-FCS games.
- Develop historically on 2015-2019 and 2021-2025; exclude 2020 everywhere.
- Treat 2025 as development evidence only in this new program. Existing
  experiments retain their original evaluation contracts.
- Use future predictions frozen before kickoff as independent evidence.
- Prefer automated sources and simple, interpretable benchmarks.
- Keep recurring data subscriptions at or below $15/month total, including the
  existing reported $4 CFBD subscription. Purchases require separate approval.
- Permit recent-era feature families on declared shorter windows when coverage
  and chronological evaluation requirements pass.
- Let evidence determine timing; there is no deadline for replacing V4.

## Architecture

```text
Current production (preserved)
R2 data/artifacts -> V4 inference -> Neon serving state -> Vercel

New research (isolated)
audited data -> football measurements -> opponent adjustment
-> offense/defense team state + uncertainty -> spread/total forecast
-> prospective evaluation -> timestamped line comparison
```

Top-level responsibilities remain stable: reusable Python under
`src/cks_picks_cfb/`, production entry points under `scripts/pipeline/`, active
research entry points under `scripts/research/`, exploratory work under
`research/`, configurations under `conf/`, and current authority under `docs/`.

## Ordered phases

The [V5 roadmap and common contract](../archive/v5-contracts/2026-09-13/v5-ratings-successor-roadmap-and-contracts.md)
is the approved execution package (2026-09-13). Use **V5 ratings successor** for
the research model; **feature schema v5** is a separate V4 diagnostic.

| Order | Contract | Status and dependency |
| --- | --- | --- |
| 00 | [Documentation alignment and methodology amendment](../archive/v5-contracts/2026-09-13/00-v5-documentation-and-methodology-alignment.md) | Implemented 2026-09-13 — documentation and authority tests aligned; no research execution. |
| 01 | [V4 feature-v5 diagnostic closure](../archive/v5-contracts/2026-09-13/01-v4-feature-v5-diagnostic-closure.md) | Implemented 2026-09-22 — pooled W1+W2 shadow spread 38.46% (35-56-1, 91 graded) < 45% → cause not confirmed; predictions value-identical to official on all 100 W0–W2 games. Report: `docs/research/2026-09-22-v4-feature-v5-diagnostic-closure.md`. |
| 02 | [Possession measurement certification](../archive/v5-contracts/2026-09-13/02-v5-possession-measurement-certification.md) | Implemented 2026-09-15 — R6 is retained historical evidence, subject to the full 10 audit. |
| 03 | [Possession rating estimation](../archive/v5-contracts/2026-09-13/03-v5-possession-rating-estimation.md) | Implemented 2026-09-17 — retained historical rating artifact, subject to the full 10 audit. |
| 04 | [Forecast bridge and fitting-window selection](../archive/v5-contracts/2026-09-13/04-v5-forecast-bridge-and-fitting-window.md) | Implemented (resolved 2026-09-21) — 04A remains implemented; 04B's verification gap closed by the 11B/11C/11D re-derivation and independent verification on the r9 line. |
| 05 | [Prospective readiness and shadow tooling](../archive/v5-contracts/2026-09-13/05-v5-prospective-readiness-and-shadow-tooling.md) | Implemented 2026-09-18 — tooling and diagnostic rehearsal only; it does not certify forecast quality or live readiness. |
| 06 | [Prospective evidence and recommendation](../plans/2026-09-13/06-v5-prospective-evidence-and-recommendation.md) | Approved; evidence tooling implemented under plan 03. Begins only after Contract 09 independently verifies live readiness, then collects six qualifying slates before a conditional Phase 7 review. |
| 10 | [Historical foundation audit](../archive/v5-contracts/2026-09-18/10-v5-historical-foundation-audit.md) | Implemented — 10A and 10B are complete. At publication, 10B recorded four open findings and `contract11_permitted: false`; all four are now closed by the accepted corrected lineage. |
| 11A | [Conditional forecast verification](../archive/v5-contracts/2026-09-19/11a-v5-conditional-forecast-verification.md) | Implemented 2026-09-19 — Preview run `conditional-v1-20260919-9265314-11a` independently reconstructed the frozen artifact, published signed evidence, passed independent re-read, and was idempotent. Its only permitted use is `conditional_historical_results_only`; it does not restore eligibility. |
| 12A | [Conditional historical scorecard](../archive/v5-contracts/2026-09-19/12a-v5-conditional-historical-scorecard.md) | Implemented 2026-09-21 — Preview run `conditional-v1-20260921-scorecard` (manifest SHA `0f4fbf33`): reported V5-only conditional results and context under `conditional_historical_results_only`. |
| 11 | [Forecast verification closure](../archive/v5-contracts/2026-09-18/11-v5-forecast-verification-closure.md) | Implemented 2026-09-21 via the 11B/11C/11D decomposition — signed verification (`4cfe5ef8...`) closes Finding 002; targeted `final_fit_existence` pass closes Finding 004. |
| 12 | [Historical results and readiness review](../archive/v5-contracts/2026-09-18/12-v5-historical-results-and-readiness-review.md) | Implemented 2026-09-21 (Amendment 2) — execution complete under [06-v5-12](../archive/v5-contracts/2026-09-21/06-v5-12-historical-results-and-readiness-review.md). Preview run `readiness-v1-20260921-scorecard` (manifest SHA `a8351fb3...`): 7,318 rows, zero exclusions. Recommendation `accepted_for_prospective_evaluation` issued in research report. **User explicitly accepted the recommendation on 2026-09-22** (report `docs/research/2026-09-21-v5-12-historical-results-and-readiness-review-report.md`; scorecard manifest `a8351fb3cabd7edbd1f78c961aa563a110b585db6c410e2b3f5973c8a2278b29`). |

Contract 01 neither blocks nor selects the ratings model. Each implementation
task names one exact contract and verifies its entry gate. Approval does not
satisfy an unmet data dependency. The historical lane is complete and accepted;
the remaining live sequence is 07 → 08 → Week 4 refresh → 09 → 06 → conditional
Phase 7 review. Historical conditional-results evidence remains preserved in its
original context and is not prospective evidence.

## Current checkpoint

**Repair v2, Phase 3 v2, the R6 possession measurements, possession ratings, and the
forecast bridge are independently certified in Preview.** The recorded September 11 apply
`phase3-v2-compact-state-20260910-r2` passed preflight, independent verification, and an
idempotent rerun under the [Phase 3 compact-state contract](../plans/2026-09-10/phase3-v2-compact-tournament-state.md).
Its selected `quality_core_epa_split` is historical reconstructed benchmark evidence, not
the definition or automatic parent of possession ratings. The R6 possession manifest
`possession-v1-measurements-20260915-18fb0aa-r6` passed preflight (910.150s), apply
(1,538.772s), independent verification (1,292.471s), and idempotent repeat under the fixed
1,800-second cap. It is the sole eligible measurement parent for Contract 03.
(Superseded 2026-09-21: `possession-v1-measurements-20260921-r9` is the
certified measurement lineage and sole eligible parent — see the 2026-09-22
checkpoint below.)

**Contract 03 possession ratings are independently certified in Preview (2026-09-17).**
Run `possession-v1-ratings-20260917-d029526-cert` passed a zero-warning no-write preflight
(60/60 candidates ok), evidence-bound apply with the signed retained manifest published
last, independent verifier-owned reconstruction of every prior, state, bridge prediction,
and the complete selection, and an idempotent repeat. The retained manifest selects
`ppp__rho_0_60__exposure` (carryover prior + exposure updater; no challenger cleared the
advancement gates) and is the sole eligible rating parent for Contract 04.
(Superseded 2026-09-21 by `possession-v1-ratings-20260921-11d59ee-r9cert`,
same selection with no flip — see the 2026-09-22 checkpoint below.)
Historical
selection remains development evidence, not a prospective win; V4 production is unchanged.

**Forecast-verification correction (2026-09-20).** Run
`forecast-v1-20260917-4600ddd-04b` remains an immutable historical artifact with recorded
preflight, apply, and repeat evidence. Its original verifier validates manifest metadata and
reference labels but does not independently reconstruct stored computations. Implemented
Contract 11A separately reconstructed all six frozen forecast outputs and published signed,
idempotent Preview evidence under `conditional-v1-20260919-9265314-11a`. That proof permits
only `conditional_historical_results_only`: it does not restore 04/04B eligibility, close
Findings 001/003, create a through-2025 final fit, or authorize 2026 work. Contract 04/04B
therefore remains In Progress and is not an eligible forecast parent until full
Contract 11 closes every forecast finding.

**Contract 05 shadow tooling is implemented in Preview (2026-09-18).**
Rehearsal run `shadow-v1-20260918-6dc87e0-05c` passed a 431.6s preflight (readiness
`ready` on the pinned 2025 W10 historical slate, replay byte-identical to the certified
05A proof, freeze 45 paired at T-2h, score 45 paired, counter 0 qualifying, all 6
negatives disposed with expected reasons), evidence-bound apply, independent
verification of the rehearsal plus the certified 05A/05B artifacts reconstructed from
source datasets, and idempotent repeats. The signed verifier manifest and the shadow
runbook (with the Contract 06 handoff) close umbrella V5-05. Real-season readiness
for 2026 W4 is re-verified `blocked` (no 2026 measurement rows, no 2026 team states)
with the historical assessment preserved. The verifier fix for canonically sorted
partition keys (Amendment 1) changes no stored bytes or digests.

**2026-09-19: Contract 10B implemented.** Run `historical-audit-10b-20260919-full`
(code SHA `7a476648`) completed the full-corpus audit across the complete 2015–2025
development corpus (24.2M adjusted-history rows). 93 checks ran; 3 failed on
substantive data findings. Four findings published to the Preview audit prefix with
`finalized: true` and `publication_valid: true`; idempotent repeat returned
`already_applied`. All four findings are blockers with `closure_state: open`;
`contract11_permitted: false`. Findings summary: (001) Repair verifier independence —
`prohibited_until_closed`; (002) Forecast outputs not reconstructed — Contract 11 scope,
`historical_evidence_only`; (003) 81 score-ledger excess keys — `prohibited_until_closed`;
(004) No through-2025 final forecast fit (`max_training_season=2024`) —
`historical_evidence_only`. Report: `docs/research/2026-09-19-v5-10b-historical-foundation-audit-report.md`.
**2026-09-22: Contract 12 accepted; 07–09 re-reviewed; 2026 extension
authorized.** The user explicitly accepted the
`accepted_for_prospective_evaluation` recommendation on 2026-09-22, and
Contracts 07–09 were re-reviewed under
[the acceptance and re-review contract](../archive/v5-contracts/2026-09-22/01-v5-acceptance-and-07-09-rereview-2026-launch.md)
against the corrected certified lineage (r9 measurements, 11B ratings, 11C
forecast with through-2025 final fit); their historical-first deferrals are
lifted with execution authorized. Authorized sequence:
1. Contract 01 executed first (Implemented 2026-09-22 — cause not confirmed;
   value-identical predictions on all 100 W0–W2 games).
2. Weekly ops: close Week 3 (production) → `prepare-week` Week 4 (Preview;
   satisfies 07's entry gate) → publish + freeze Week 4 per runbook. (Week 4
   publish was observed in serving state 2026-09-22; confirm the close and
   prepare steps completed before 07 executes.)
3. Execute 07: `live` timing amendment + 2026 season validation → Repair-2026
   (verifier v3) → 2026 possession measurements W0–W3. **Implemented 2026-09-22:**
   Repair-2026 `repair-2026-20260922T145500Z` (157/157/157, verified) +
   measurements `possession-v1-measurements-20260922-2026c` (manifest
   `ec96fe51…`, 8 datasets, all live, verified, `already_applied`; sole
   eligible 08 parent).
4. Execute 08: 2026 priors (zero 2026-outcome fitting) → replay W0–W3 →
   independent verification. **Implemented 2026-09-22:** replay
   `possession-v1-rating-replay-20260922-fcaa571` (276 priors, 628 rating
   states, 314 team states; verifier `56811387…`; idempotent repeat).
5. After Week 4 finals stabilize (~Sep 28), re-run 07/08 through W4 under new
   run-IDs so Week 5 forecasts use current states.
6. Execute 09: 2026 forecasts via the through-2025 final-fit bridge →
   verification → readiness `ready` on the Week 5 slate (~Thu Oct 1 first
   kickoff; a skipped Week 4 slate is expected, not a failure).
7. Contract 06 begins: freeze at T−2h before the first Week 5 kickoff
   (≥40 paired games), then weekly cadence (score +24h, refresh chain,
   readiness, freeze); six qualifying slates (W5–W10 target) before the Task 4
   recommendation. A separate Phase 7 promotion contract remains required
   before any activation.
CFBD finals lag (24–48h) may delay the W4 refresh; a late refresh degrades to
W3 states plus a recorded limitation rather than rushed finals. V4 production
is unchanged throughout.

The possession-based rating methodology is specified (2026-09-11), amended
2026-09-13. Its [original specification contract](../archive/v5-contracts/2026-09-11/possession-rating-methodology-specification.md)
remains an Implemented documentation milestone; the current
[methodology](../modeling/possession_rating_methodology.md) reflects this package.
The first forecast release is **bridge-first**: Ridge maps four role ratings and
venue indicators to margin/total, with a prior-only non-offense offset. Possession
arithmetic and other expanded forecast families are later challengers.

Compare both possession definitions across six priors and five updaters, then
compare expanding fitting history with the latest five eligible seasons on
identical 2022–2025 validation games. Preserve continuous state history and fit
all learned quantities strictly before their validation season. The published
floors/fallbacks and k values are fixed first-generation settings; there is no
2015–2019 global constant-fitting step. Ratings are mandatory; direct models and
polls remain diagnostic-only, and markets enter only after football evaluation.

Distinguish **implementation**, **data certification**, **downstream eligibility**,
and **prospective evidence**. Completing code or documentation does not certify a
measurement or qualify a future slate. Six qualifying paired slates permit review,
not automatic promotion; Phase 7 requires a separate approved contract.

**Dated operations record (2026-09-13):** Week 2 `2026w2-43b25511a100` is scored;
Week 3 `2026w3-68fe6a815bd6` was published with 57/57/56 coverage and freeze pending.
The V4 feature-v5 diagnostic closed 2026-09-22 under contract 01: cause not
confirmed (pooled W1+W2 shadow spread 38.46% < 45%), with value-identical
predictions on all 100 games refuting the mismatch hypothesis.
See the operating runbooks for current weekly actions.

## Retained and superseded evidence

The [September 8 review](../plans/2026-09-08/transformation-review-and-authority-reset.md#review-evidence-and-dispositions)
retains the authoritative findings: same-game Phase 4B leakage, constant coaching,
incorrect roster continuity, and 32 omitted completed schedule games. Repair v2
and the corrected Phase 3 v2 benchmark addressed the repaired lineage/population.
The **original Phase 4B retained manifest remains prohibited as a forecasting
parent**; its apparent 11.36% margin gain is not valid pregame predictive evidence.

The September 8 Phase 4A–6 execution contracts are **Superseded** by 03–06;
only explicitly inherited mathematical sections carry forward. This does not
authorize executing old runners. September 5/7 Phase 3–6 plans and pending R3/R4
are superseded historical records. Earlier Phase 3 EPA-only and Phase 4A
`rho_0_60__exposure` selections retain reduced-population limitations. Historical
R2, direct early-game, and candidate-v1 results keep their exact audit dispositions.

## Historical predecessor identities (use subject to review dispositions)

| Phase/evidence | Immutable identity and code binding | Timing and permitted use | Activation |
| --- | --- | --- | --- |
| Phase 0 alignment | [Implemented contract](../plans/2026-09-05/00-repository-architecture-and-documentation-alignment.md) and its compatibility baseline | Repository boundary and V4-regression protection; no model input | Not applicable |
| Corrected Phase 1 audit v3 | `artifacts/research/data-first-football-v1/phase1/2026-09-06T0055Z-phase1-evidence-audit-v3/` | Preserves the exact unsupported/correction-required dispositions of historical results | Research evidence only |
| Phase 2d audit | `phase1/2026-09-06T2358Z-phase2d-recertification-v2/audit-v5.json` — SHA `0fd8a32a13ce64a261fa8a0179cdaa1de1cb93e428e362d50ad0aa9970c7761f`, code `285422026816bc933279a69e997021847b4bfb31` | Certifies core lineage, omissions, coverage, and timing for measurement construction | False |
| Phase 2d automation admission | `phase2/recertification/runs/2026-09-06T2358Z-phase2d-recertification-v2/automation-admission.json` — SHA `7a46adfaff0bcb89b86f244c586d93085557ba3119699da81824ffa4e83f5518`, code `285422026816bc933279a69e997021847b4bfb31` | Enables only the verified Preview capture workflow; it is not a model artifact | False |
| Phase 2d core handoff | `phase2/recertification/runs/2026-09-06T2358Z-phase2d-recertification-v2/eligibility-manifest.json` — SHA `cdeeea01035c9108491a42b2e29a9e6033cdd7781d1ab837df8e411b29afe760`, 70 exact refs | Historical Phase 3 parent; current use is repair input | False |
| Phase 2e auxiliary capture set | `phase2/auxiliary/2026-09-07T0016Z-phase2e-auxiliary-v1/capture-set.json` — SHA `c2ff56b084e58b5cd159f884171df05187746c0dc40b42817912866a540de650`, code `80aba46df8b5e92959024510140cbd06de6b3b3e`, 63 Bronze captures | Reconstructed-only historical evidence; captures cover recruiting, returning production, coaching, roster continuity, rankings, and market references | False |
| Phase 2e auxiliary handoff | `phase2/auxiliary/2026-09-07T0016Z-phase2e-auxiliary-v1/eligibility-manifest.json` — SHA `d06ed3968a7bb6ec7ba97212aa2063068c253f26202e810c921b044006ab13ad` | Six Preview datasets: recruiting, returning production, coaching, roster continuity, strictly lagged polls, and reconstructed market references. Historical football-context admission requires semantic recertification; markets remain post-selection diagnostics only. | False (`eligible_reconstructed_only`) |
| Phase 3 retained core | `phase3/runs/phase3-v1-20260907T1500Z/retained-core-manifest.json` — raw SHA `c8bc1ebd8a369c59cf298844dfdb2167baaa17dc72a3b29ceebd119eeacaf234`, code `6addf437e7d76f5e39f198c41acd47c4e9b2c5b4`, selected `epa_only` | Historical reduced-population Phase 4A parent; 302,702 observations, 1,210,808 adjusted measurements, 202,048 fold predictions | False |
| Phase 4A retained rating | `phase4a/runs/phase4a-v1-20260908T1500Z/retained-rating-manifest.json` — canonical manifest checksum `af9e66af67f26155ab74d1acd1947f72add7307203ae09bf1853856696e27612`, code `3547844111c90f71c85760cbf841ae11787591a8`, selected `rho_0_60__exposure` | Historical reduced-population Phase 4B parent; 101,024 fold predictions, 284,896 rating states, 142,448 team states | False |

The earlier checksum-invalid Phase 2d eligibility artifact is superseded. The
first partial Phase 2e apply is unregistered diagnostic evidence and has no
eligible downstream use. The corrected source inventory records 1,300
returning-production Bronze captures and 26,844 betting-line Bronze captures;
lower compatibility-projection counts are not source inventory totals. Game
statistics are reconciliation evidence, not a separate required play source;
the obsolete 2016–2018 play-gap claim is not current authority.

Historical R2 and direct early-game results keep their exact Phase 1
dispositions. The former R2 winner is unsupported for this program and cannot
enter Phase 4 without renewed evidence.

## Authority transition

This roadmap replaces the pending R3/R4 sequence and the unfinished research
portion of the historical-expansion roadmap. The 2026-09-05 and 2026-09-07 Phase 3–6 contracts
are superseded historical planning records. The 2026-09-13 V5 package is the
active execution path; it retains certified repair/benchmark evidence and
explicitly inherited mathematics from the September 8 corrective sequence. Completed R1/R2 work, candidate v1, and direct early-game
research remain immutable historical evidence subject to Phase 1 audit
disposition. V4 remains the production benchmark and rollback authority
throughout.
