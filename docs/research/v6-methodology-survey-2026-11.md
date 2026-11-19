# V6 methodology survey (November 2026)

**Status:** Research survey. Documentation only: no code, model, configuration or production change.
**Date:** 2026-11-19 (all sources accessed this date unless stated).
**Scope:** which rating system and modeling structure best serve college-football line prediction, and whether spreads and totals should be modeled separately. Model research starts after the 2026-12-13 final close; this page only prepares the ground.

## How to read this survey

- **Evidence quality is mixed and stated per claim.** Six parallel web-research passes fed this page. Most agents could read abstracts and search summaries, not full papers, and several primary pages (SP+ and FEI methodology, Sagarin, Massey, PredictionTracker, KenPom) were not retrievable. Where a claim rests on that, it is tagged accordingly.
- **Source tiers:** `[PC]` primary-current (author's current published method), `[PH]` primary-historical (older writeups, papers), `[S]` secondary or inferred (blogs, press, or this survey's own reasoning and arithmetic). Self-reported ATS records are treated as unverified.
- **Policy labels** (from `AGENTS.md`, [`betting_policy.md`](../modeling/betting_policy.md) and Amendment 5 of the [offseason research protocol](../plans/2026-11-12/02-offseason-research-protocol.md)): **L1** allowed now (football-only inputs, methods, evaluation); **L2** post-freeze monitoring only (market views reported after a candidate is frozen, never an input or a selection criterion); **L3** requires a betting-policy change (owner decision).
- **Feasibility** means: can the input be obtained point-in-time for 2015-2019 and 2021-2025 from CFBD or another clean free source without lookahead leakage? `yes`, `partial` (with years), or `no`. CFBD's documentation is largely silent on whether stored historical values are revised, so most `yes`/`partial` verdicts are **unverified until a live API check** (listed under Open questions).
- **Baseline.** All V5 figures are Operational V5 from the [baseline audit](../plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md): regular-season games, 3,483 games per target, 2022-2025, bias = actual minus prediction. Historical-V5 diagnostics are not used.

## Executive summary

**Operational V5 gaps this survey addresses**

| Gap | Operational V5 figure |
|---|---|
| Flat totals | Predicted total SD 1.57 (range 50.1-62.3) vs 16.90 actual; correlation with outcome +0.164; total MAE 13.3709, bias -1.36 |
| Stage 0 (before a team's first game) | Margin bias +7.51, MAE 16.17; lopsided P4-host games under-predicted by 12-13 |
| Neutral site | Margin bias -2.69 (126 regular-season games); total bias -5.02 |
| Margin baseline | MAE 13.7151, bias +0.19 |

**Ranked recommendations.** Rank is by expected effect on a named gap weighted by confidence in the evidence. None has been tested; each is a hypothesis for a pre-registered contract after 2026-12-13.

| # | Recommendation | Named gap | Expected effect | Policy | Point-in-time feasibility |
|---|---|---|---|---|---|
| 1 | **Fit a joint team-score model for totals**: predict each team's points from its own offense and the opponent's defense (additive on a points scale, or multiplicative), then total = sum and margin = difference from the same parameters. First step is a cheap diagnostic on existing rating states (compare predicted-total SD and correlation with the current bridge). | Flat totals | Largest of any option on the totals gap, because no cancellation occurs between a team's offense and the opponent's defense. Magnitude unknown; a predicted-total SD of roughly 4-7 is plausible but weakly grounded `[S]`. | L1 | yes (existing rating states; no new input) |
| 2 | **Explicit per-game venue term** (home +1, neutral 0) instead of home edge absorbed in the intercept. | Neutral-site bias (margin -2.69, total -5.02) | Removes a structural error on about 3.6% of games; small pooled effect, large on the affected slice. Already listed in the backlog. | L1 | yes (`game_venues` stored) |
| 3 | **Tier-conditional prior mean and heteroscedastic, unsaturated margin link** for lopsided matchups (FBS-vs-FCS indicator, early conference tier). Overlaps the frozen 2027 candidate P3 and the scored B3. | Stage-0 bias | Targets the P4-vs-FCS/G5 under-prediction directly. No published CFB test found `[S]`; treat as a hypothesis. | L1 | partial (FCS play coverage in CFBD unverified; tier labels available) |
| 4 | **Add special-teams, field-position, finishing-drive and turnover/havoc units to the rating state.** SP+, FEI and FPI all carry them; the closed V6 lab did not. | Totals variance; general margin MAE | Plausible secondary gain; none of the public systems has been shown to publish a totals forecast, so this is not a proven totals fix. | L1 | partial (derivable from CFBD plays and drives 2001-present; PPA revision risk) |
| 5 | **Re-weight the multi-signal prior**: SP+ now gives recruiting about 1-2% (was 20-25%) and added a coaching-change factor. Keep returning production; test dropping or shrinking recruiting. | Stage 0-3 error | Modest; tests an existing design choice with a cheap ablation. | L1 | recruiting yes; returning production partial (2014-present, "preseason" label unverified); coach change partial (head coaches only) |
| 6 | **Evaluation upgrades** (Section 7): adjusted-p-value tournament test, week-cluster bootstrap, resolve 90% vs 95%, and treat 2026 as the confirmation season. | Selection bias; underpowered gates | Prevents adopting noise. See power table: a 0.2 MAE gain is only borderline detectable even on all 3,483 games. | L1 | n/a |
| 7 | **Weather (wind) as a totals input.** | Total bias | Small; non-CFB evidence only. | L1 if forecast-time values are used | partial (CFBD weather 2001-present, Tier 1 paid, forecast-vs-observed undocumented: leakage risk) |
| 8 | **Post-freeze market monitoring**: CLV against near-kickoff captures, MAE vs market, cutoff vs closing line. | None (diagnostic) | Honest benchmark after freeze. | **L2** | yes for captured lines (own captures); CFBD `/lines` partial |
| 9 | Market-implied ratings, closing line as prior or target, market-blended forecasts, market-informed prioritization. | Totals and stage-0 | Likely the strongest accuracy lever (Fair and Oster 2007 found no rating system carried information absent from the final line `[PH]`) but conflicts with current policy. | **L3** | partial |

**Direct answers.**

- *What rating system best serves line prediction?* The evidence does not crown a single system. The public systems that publish margins (SP+, FPI) rate offense, defense and special teams as separate **points-scale** units, so a rating difference is already a margin. V5's PPP ratings need a learned bridge, and that bridge is where totals flatten. The most defensible lesson is structural (points-scale units plus a team-score formulation), not "adopt SP+'s five factors".
- *Spreads and totals: separate or joint?* A joint team-score model is better supported than two separate bridges, but the evidence is inferential: no source found compares the two on totals accuracy in any sport (Section 5). Recommendation 1 is therefore framed as a diagnostic first.
- *Is there a market fix for stage 0?* Only at policy label L3. Football-only options (recommendations 3 and 5) are available now.

## Glossary

Terms not already in [`measurement_catalog.md`](../modeling/measurement_catalog.md) or [`possession_rating_methodology.md`](../modeling/possession_rating_methodology.md).

- **CLV (closing-line value):** the price a bet obtained relative to the closing price for the same side; beating the close is the industry quality metric. Pinnacle's definition `[PC]`.
- **IsoPPP:** isolated points per play: average value of a team's successful plays only, an explosiveness measure used by SP+.
- **Havoc:** rate of tackles for loss, forced fumbles, interceptions and pass breakups relative to plays.
- **Key numbers:** final margins that occur unusually often (3 and 7 in football), which make half-point moves around them more valuable.
- **RAPM:** regularized adjusted plus-minus: ridge regression of outcomes on player or team indicators to isolate each one's contribution.
- **Market-maker (sharp-origin) book:** a book that takes sharp action at low limits and lets bettors move its price (Pinnacle's stated model), as opposed to a retail book that copies the market.
- **SPA / Reality Check:** tests of whether the best of many candidate models beats a benchmark after correcting for having tried many.
- **Design effect:** inflation of variance from dependence between games (shared teams, shared weeks); effective n = n / design effect.

## 1. Public rating systems and the closed V6 lab

Coverage caveat: SP+ and FEI formulas, Sagarin, Massey and PredictionTracker pages were not retrievable; JP+ returned no methodology (see also [`decisions/2026-11-17-jpplus-site-review.md`](../decisions/2026-11-17-jpplus-site-review.md)); no independent MAE/ATS comparison was established.

| System | Unit | Inputs | Opponent adjustment | Priors / decay | Update | Publishes a total? | Tier |
|---|---|---|---|---|---|---|---|
| SP+ (Connelly, ESPN) | Adjusted points per game vs average; offense, defense, special teams | Success rate, IsoPPP, field position, finishing drives, turnovers; tempo-adjusted | Per factor, then weighted; weights not found | 2026 preseason: prior SP+, returning production (largest), multi-year history, recruiting about 1-2% (was 20-25%), new coaching-change factor; preseason weight fades weekly (schedule not found) | Weekly | Not found | `[PC]` 2026 ESPN articles; factor list `[S]` |
| FEI (Fremeau, bcftoys) | Scoring advantage per non-garbage possession | Possession/drive efficiency; offense, defense, special teams; starting field position | Opponent-adjusted; formula not on the page | Preseason FEI exists; weights not found | Weekly | Not found | `[PC]` glossary; rest `[S]` |
| ESPN FPI | Expected points per game vs average FBS team, per unit (offense, defense, special teams) | Play-level EPA; blowout effects capped | Per-game EPA adjusted for opposing unit and site; Bayesian regression per unit | Prior performance, returning starters (QB about 3.3 points per game), minor recruiting, coach tenure; weight declines, never zero | After every game, retroactive re-adjustment | No (margin, win probability, season simulations) | `[PC]` article (date unclear); weights proprietary |
| Sagarin | Points; composite of three components | Scores | Not found | Not found | Not found | No | `[S]` |
| Massey / Massey-Peabody | Points; four-stat weighted variant | Scores; rush, pass, scoring and success rate in the variant | Least-squares style, unverified | Not found | Not found | Not found | `[S]` |
| CFBD Elo and SRS | Elo points; SRS points | Result, rating gap, margin, home context | SRS schedule-adjusted | Not public | Per game | No | `[PC]` (CFBD states formulas are proprietary) |
| JP+ | Unknown | Unknown | Unknown | Unknown | Unknown | Unknown | Unverified |

**Diff against the closed V6 lab** ([`ratings-lab-v1.md`](ratings-lab-v1.md), [`v6-ratings-architecture-design.md`](v6-ratings-architecture-design.md); `RETAINED_AS_BENCHMARK`).

| Dimension | Closed V6 lab | Public systems | Reading |
|---|---|---|---|
| Special teams | none | separate unit in SP+, FPI, FEI | Candidate gap (recommendation 4) |
| Field position | none | SP+ factor; FEI tracks it | Candidate gap |
| Finishing drives | none | SP+ factor | Candidate gap |
| Turnovers / havoc | none in the 4-factor state | SP+ factor and a luck adjustment `[PC]` | Candidate gap |
| EPA vs success rate / IsoPPP | success rate and explosiveness per rush/pass | FPI: EPA; SP+: success rate and IsoPPP | Not a clear differentiator |
| Unit | efficiency factors | points per game (SP+, FPI); points per possession (FEI) | Points-scale units remove the learned bridge |
| Bridge | alpha-10 Ridge from ratings to margin and total | Rating difference is a margin by construction (`[S]`: no statement found that SP+ or FPI use a learned bridge) | Possible structural advantage; unverified |
| Update | exposure-weighted 1D Kalman plus re-anchoring | FPI: Bayesian regression with retroactive update (closest analogue); SP+ and FEI: weekly refit | The lab's updating idea is not obviously inferior |
| Recruiting prior | included | SP+ now about 1-2% | Likely low value; ablate |
| Totals | flat | none of the verifiable systems publishes a total | A flat total is not evidence that a public system solves it |

Two verifiable facts matter most: SP+ and FEI are still published in 2026 `[PC]`, and no verified public system publishes a total, so there is no published benchmark for predicted-total spread to copy.

## 2. Rating architectures for line prediction

Evidence is mostly NFL, soccer and other sports; abstracts and snippets, not full texts. **No source tested these on sparse early-season college-football graphs or FBS-vs-FCS mismatches.** Stage-0 judgments below are `[S]` hypotheses.

- **Ridge / RAPM-style regression.** A prior or penalty is structurally required on sparse graphs because maximum likelihood gives undefeated teams infinite ratings `[PH]`. Shrinkage targets the prior mean, so lopsided games are compressed by construction; the choice of target (a tier mean rather than a global mean) probably matters more than the penalty strength. This is consistent with the observed under-prediction of P4-vs-FCS/G5 margins. Cross-validating the penalty on full seasons mainly reflects mid-season graph density, not weeks 0-3.
- **State-space / Kalman (Glickman-Stern).** Season-to-season mean reversion plus weekly drift is the principled early-season treatment `[PH]`; Glickman (2001) adds stochastic variances for sudden strength changes, relevant to roster turnover `[PH]`. Out-of-sample evidence is thin (a 110-game NFL test, self-reported). Koopmeiners (2012) found NFL autocorrelation has changed over time, so process noise should be fitted, not borrowed `[PH]`. A filter does not by itself fix nonlinearity at the mismatch tails, which is why the closed lab's Kalman did not remove stage-0 bias.
- **Score models (Poisson, bivariate Poisson, Skellam, hierarchical Bayes).** Evidence is soccer only (Karlis-Ntzoufras 2003, Baio-Blangiardo 2010 `[PH]`); football scoring is not low-count Poisson, so transfer is a stretch. Their useful property is heteroscedasticity (variance rising with expected total), which a Gaussian margin model lacks. No NFL or college evidence of gain over margin-only models found.
- **Margin-of-victory caps.** Motivated by discouraging run-up scores, not by validated accuracy; the one direct college test found (a blog) said capping hurt prediction `[S]`. FiveThirtyEight-style Elo uses `ln(|margin|+1)` damped by the rating gap, NFL only `[PC]`. Caps on the training signal may reduce leverage of FCS blowouts, but an unsaturated predicted-margin link is needed so mismatch spreads are not compressed.
- **Home-field and neutral site.** College football home advantage is heterogeneous (about 6 points, larger for non-BCS teams after controls, Wang-Johnston-Jones 2011; per-team parameters, Gajewski 2006; a decline reported by Benz-Bliss-Lopez 2024) `[PH]`/`[PC]`. The standard form is a per-game venue term (home +1, neutral 0, away -1) with optional shrunken team deviations. V5's constant `home_host=1.0` with the edge in the intercept is the structural gap behind the -2.69 neutral-site margin bias.

**Stage-0 handling summary.** The best-supported football-only levers are a tier-conditional prior mean, an explicit FCS tier, and an unsaturated or convex margin link; per-stage intercepts (B1s) fix the mean but worsen balanced games, as the audit found. The in-season stage 1-3 updating problem (moves of 8-10 points without MAE gain) is consistent with a process-noise setting that is too loose for sparse data; no published guidance transfers.

## 3. Spreads and totals

**Recommendation: prefer a joint team-score model; do not build a second independent linear bridge.** Confidence is low-to-medium because the evidence is indirect.

Grounding in the cancellation finding:

- V5's total is a linear function of four ratings (home/away offense and defense) with small fitted coefficients (0.5-1.75 points per rating SD vs 7-11 for margin), and offense and defense ratings correlate +0.42 to +0.51. In a margin, offense and defense add with the same sign for a team and cancel across teams in the way margin wants; in a total, a team's offense and the opponent's defense should reinforce, so the weak coefficients indicate a bridge specification or scaling problem, not an absence of signal. This is the survey's inference.
- NFL evidence (1978+, a team's points regressed on own offense and opposing defense ratings): coefficients about 0.95 and 0.93, R² 0.27, offense about 58% and defense about 42% of explained variance `[PH]`, blog analysis. Ratings on a points scale carry about one point per rating point on each side; season-long ratings explain only about a quarter of single-game team scoring. So a realistic predicted-total SD is well below the 16.90 actual, but far above 1.57. A figure of roughly 4-7 is plausible `[S]`, weakly grounded.
- KenPom-style tempo-free systems compute each team's score as possessions times a multiplicative offense-times-opponent-defense efficiency; total variance then comes from both efficiency and tempo `[PH]`, non-CFB, formula inferred (page not retrievable).
- Step 3 of the baseline audit found possession volume is not the missing input, so pace should be a secondary term, not the lead.
- Soccer's bivariate Poisson adds a covariance term for dependence the ratings do not explain; empirical home-away correlation is low `[PH]`, non-CFB. No source compared two-equation and linear-total models on totals accuracy.

**What to test (recommendation 1).** (a) On existing rating states, fit points_home and points_away each from own offense and opponent defense, sum them, and compare predicted-total SD and correlation to the current bridge. (b) Check that the unexplained home-offense-moves-the-total-3x-away-offense asymmetry is not a home-field encoding or collinearity artifact. (c) Only then consider a multiplicative form or pace term. A separate regression of the total on the same four ratings, without heavy shrinkage, is the control. Weather: wind is the most consistently supported effect in NFL studies (a student regression -0.26 points per mph; heat, wind and rain reduce scoring `[PH]`); betting-site rules of thumb (2.5-3.5 points at 15-20 mph) are unverified `[S]`; no CFB effect sizes were found, and cold appears to be over-priced by the market.

## 4. Sportsbook and market practice (by policy label)

Everything here is context for post-freeze monitoring and for the L3 decision. Confidence is low-to-medium; many items are single secondary sources, and several requested items (Gandar, Sauer and Humphreys CFB work; vig-removal methods; market reaction to injuries and weather) were not sourced and are marked unverified.

| Item | Finding | Label | Tier |
|---|---|---|---|
| Opener origin | Circa Sports posts the first weekly CFB number; other books open near numbers that attract action | context; using openers as inputs is L3 | `[S]` press |
| Power rating plus trader adjustment | Implied; no primary description of the formula or home-field constant found | context | `[S]` |
| Sharp-origin books | Pinnacle opens at reduced limits and relies on sharp action to move price; says beating the close indicates long-term +EV; says closing prices stay partly anchored to openers | context; choosing a benchmark close is L2 | `[PC]` (self-interested) |
| Closing-line efficiency | Fair and Oster (2007, college football): no rating system, including the optimal combination, held information absent from the final point spread (abstract only) | context; reinforces L2-only comparison | `[PH]` |
| Levitt (2004, NFL) | The spread is a price set to balance action, not the bookmaker's forecast; few bettors beat it | context | `[PH]` |
| Totals market | Overs were overbet in 2005 data; a 2003-2015 study found neither blanket over nor under profitable | context | `[PH]` |
| Line error magnitude | FiveThirtyEight: betting-line MAE 12.96 in 2020, the highest since 2002; roughly 12-13 is a usual level (inferred) | L2 benchmark | `[S]` snippet |
| Margin SD around the line | About 15.8 in one blogger's 4,000-game opening-line sample; other sources say 13-16 | L1 as a calibration check on own margin errors; applying to market prices is L2 | `[S]` |
| CLV | Price relative to the close; the industry quality metric; peer-reviewed evidence tying CLV to profit not found | L2 | `[PC]`, `[S]` |
| CLV pitfalls | Use a sharp no-vig close; report a timestamped near-kickoff capture separately from the true close; small samples mislead | L2 | `[S]` |
| Key numbers | 3 (about 9.7% of margins), 7 (about 7.3%), then 10 and 14; sources conflict (one claims 15% for 3), unverified | L1 using own historical margins | `[S]` |
| Lines depend on prior ATS results | Sinkey-Logan (11,000 CFB games 1985-2003, working paper) and a 2020 study; any ATS-history feature is market-derived | L3 as an input; L2 as a post-freeze check | `[PH]` |
| Market-implied ratings | Methods exist (implied SRS from spreads, home value about 3; win-total-plus-spread ratings) | L3 to use; L2 to read | `[S]` |
| Vig removal and spread-to-probability conversion | Not researched; standard methods need verification | L1 for own-model calibration; L2 on market prices | none |

Context for the record: a 49.7% spread and 46.8% total record through Week 11 sit below the roughly 52.4% break-even at -110, which is consistent with an efficient market after vig. That statement is about the market, not a claim about V6.

**L3 options documented for an owner decision** (not recommended by this survey): market-implied ratings as priors, closing line as a target or prior, market-blended forecasts, and using steam or line movement to prioritize research. The literature suggests the market would help accuracy, which is precisely why the owner, not this survey, decides.

## 5. Evaluation decisions beyond the protocol

Only the first search pass retrieved sources for this track (Hansen 2005, Harvey-Leybourne-Newbold 1997, Dwork et al. 2015); other methods are cited from the agent's knowledge and tagged `[S]`. Verify before citing externally.

- **Multiplicity.** For roughly 10-30 candidates against one incumbent on paired loss differentials, Hansen's SPA test (studentized, data-dependent null; more power and less sensitivity to poor candidates than White's Reality Check) is the better default `[PH]`; Romano-Wolf stepdown if the goal is to name which candidates beat V5 with familywise control `[S]`. The Model Confidence Set answers a different question (indistinguishable best set), and the Deflated Sharpe Ratio and Probability of Backtest Overfitting target trading Sharpe ratios; borrow only the idea of deflating for the number of trials `[S]`. The protocol's finalist rule and scoring-run ledger already supply the trial count.
- **Holdout reuse.** Thresholdout (Dwork et al. 2015 `[PC]`) needs a fresh uncontaminated holdout. 2022-2025 is already examined, so the practical design is one-shot access to a fresh season (2026) for the single frozen finalist. Treat any 2022-2025 result as exploratory.
- **Bootstrap unit.** Baseline: game-level iid. Robustness: resample whole season-weeks (about 58 clusters) or use a stationary bootstrap with 1-2 week blocks; adopt the wider interval for the gate. Two-way (team and week) clustering is not clean in a bootstrap. The design effect is probably 1.0-1.5 because two highly correlated models share most team-level error, but this is unmeasured: estimate it by comparing game-iid and week-cluster standard errors on the existing outputs.
- **Common random numbers.** Use the same resample indices across candidates so cross-candidate dependence survives into the max-statistic.
- **Interval level.** A "candidate beats V5" gate is one-sided. A two-sided 90% interval is a one-sided 5% test; a two-sided 95% interval is one-sided 2.5%. State which the protocol means. The multiplicity adjustment matters more than 90 vs 95.
- **Report the finalist, not the best of K.** The interval for the single frozen finalist; the best-of-K estimate is upward biased.
- **Consistency guard.** Require the gain to carry the same sign in at least 3 of 4 seasons.

**Gap versus the current protocol.** `ratings_lab/evaluation.py` `paired_comparison` returns 90% intervals (it takes the 5th and 95th percentiles of the bootstrap); the protocol's adoption thresholds use 95% (Amendment 2 not applied). Either the code or the protocol wording must change before the first scoring run. Under the one-sided reading above the code's 90% interval is a 5% gate, which may be what was intended; that is an owner decision (Open questions).

**Power (survey arithmetic, `[S]`).** n = ((z_alpha + z_power) x sigma / delta)^2 with delta = 0.2 MAE, power 80%, independent games, normal approximation; sigma is the SD of the per-game absolute-error difference.

| sigma | n needed, two-sided 5% | n needed, one-sided 5% | MDE at n=3,483 | Power at 0.2, n=3,483 | MDE at n=870 | Power at 0.2, n=870 |
|---|---|---|---|---|---|---|
| 4 | 3,140 | 2,473 | 0.19 | about 84% | 0.38 | about 31% |
| 5 | 4,906 | 3,865 | 0.24 | about 66% | 0.48 | about 22% |
| 6 | 7,064 | 5,565 | 0.29 | about 50% | 0.57 | about 16% |

Consequences: at sigma 5-6 a 0.2 gain is underpowered even on all 3,483 games; one 870-game season cannot detect it at any of these sigmas; a design effect of 1.5 raises the minimum detectable effect by about 22%; with K = 20 candidates the Bonferroni minimum detectable effect at sigma 5 is about 0.33 (max-statistic methods land lower, plausibly 0.28-0.30). The stage 0-3 subset (886 games) has a minimum detectable effect near 0.47 at sigma 5, so the protocol's 0.2 stage 0-3 gain threshold is mostly a decision rule on point estimates, not a test.

Empirical sigma can be backed out of the existing audit: the 90% intervals for B1 (0.05 to 0.36), B1s (0.33 to 0.76) and B2 (-0.01 to 0.31) on the 886 stage 0-3 games imply per-game SDs of roughly 2.8-3.9 points under game-level iid (half-width = 1.645 x sigma / sqrt(886)). Small perturbations of V5 have small sigma; a structurally different V6 will have larger sigma and need more data. Measure it per candidate rather than assume.

## 6. CFB-specific inputs and point-in-time feasibility

Coverage years and tiers are `[PC]` CFBD documentation (page last verified 2026-09-03). **Revision and backfill semantics are undocumented, so every verdict for 2015-2019 and 2021-2025 is provisional until verified against the live API.** API tiers: free 1,000 calls per month; Tier 1 ($1) 5,000, adds weather and opponent-adjusted metrics; higher tiers to 500,000 calls.

| Input | Source | 2015-19 | 2021-25 | Leakage risk | Verdict |
|---|---|---|---|---|---|
| Returning production | CFBD `/player/returning` (2014-present, "forward-looking preseason dataset") | yes (unverified) | yes (unverified) | Unknown whether computed from then-current rosters or recomputed later | partial (leaning yes; verify) |
| Transfer portal / roster continuity | `/player/portal` (2021-present); `/roster` (2004-present, completeness varies) | no | partial | `/roster` is probably a latest snapshot, not an as-of archive; portal entry dates unconfirmed | no for 2015-19; partial 2021-25 |
| Recruiting composites | `/recruiting/*`, `/talent` (2000-present) | yes | yes | Low; whether ratings are as of signing or a later refresh unknown | yes |
| Head-coach changes | `/coaches` (1886-present) | yes | yes | Coach SP+ and SRS fields are end-of-season outcomes: exclude | yes (head coaches) |
| Coordinator changes | not documented in CFBD | no | no | n/a | no |
| QB changes and injuries | none in CFBD; post-hoc inference from stats is leakage | no | no | Ex-post starter is leakage; no free timestamped source found | no |
| Opt-outs | not documented | no | no | n/a | no |
| FCS opponents | `/games` and `/plays` accept an FCS classification; play coverage "varies by game and source" | partial | partial | Depth unverified; sample an FCS game | partial (unverified) |
| Garbage time | CFBD rule: margin over 38 in Q2, 28 in Q3, 22 in Q4 (can exit if the margin narrows); SP+ definition not found | yes | yes | Low (deterministic from play state) | yes |
| EPA | CFBD PPA (2001-present, one consistent model across history) vs cfbfastR `create_epa()` | partial | partial | The fixed model was likely fitted with later data: mild leakage; training data not stated | partial |
| Weather | `/games/weather` (2001-present, not every game; Tier 1) | partial | partial | Forecast vs observed undocumented | partial |
| Betting lines | `/lines` (2013-present) | partial | partial | Capture time and provider coverage undocumented; policy-restricted as an input | partial (L1-restricted) |

Inputs scoring **no** (listed, not recommended): coordinator changes, QB changes and injuries, opt-outs, and 2015-2019 portal data. Note that the protocol's training range must account for the portal gap if a portal feature is tested.

## 7. Gap map

| Operational V5 gap | Candidate methods | Policy | Point-in-time feasibility | `ratings_lab` host | Relation to tested or frozen candidates |
|---|---|---|---|---|---|
| Flat totals (SD 1.57 vs 16.90; correlation +0.164) | Joint team-score model; multiplicative bridge; pace as secondary term; wind | L1 | yes (rating states); weather partial | `total_bias.py` for the diagnostic; a new bridge module for the model | Not covered by B1s, B3 or P1-P4 (those are margin-side early-season terms); step 3 ruled out possession volume |
| Stage 0 (bias +7.51, MAE 16.17) | Tier-conditional prior mean; FCS tier; unsaturated or convex margin link; heteroscedastic variance | L1 | partial | `priors.py`, `error_slices.py` | Overlaps frozen 2027 candidate P3 (FBS-vs-FCS indicator plus early conference tier) and scored B3; B1s fixed the mean but worsened balanced games |
| Stage 1-3 updating (8-10 point moves, no MAE gain) | Fitted process noise; variance inflation early in the season | L1 | yes | `kalman.py`, `updaters.py` | Not directly tested |
| Neutral site (margin -2.69, total -5.02) | Per-game venue term; optional shrunken team HFA | L1 | yes (`game_venues`) | feature frame and bridge (not a rating module) | Already a backlog item; not yet scored as a candidate |
| Missing units (special teams, field position, finishing drives, turnover/havoc) | Add units to the rating state | L1 | partial | `measurements.py`, `adjusted_game.py` | Closed V6 lab did not include them |
| Prior composition | Ablate recruiting; keep returning production; add coach-change flag | L1 | partial | `priors.py` | Extends the closed lab's multi-signal prior |
| Selection and power | SPA or Romano-Wolf; week-cluster bootstrap; fresh-season confirmation; measure sigma and design effect | L1 | n/a | `evaluation.py` (`paired_comparison`: 90% vs 95% gap) | Complements the protocol's finalist rule and ledger |
| Market gap (benchmark) | CLV, MAE vs market, cutoff vs closing | L2 | own captures | outside `ratings_lab/` | Only after a candidate is frozen (Amendment 5) |
| Accuracy ceiling | Market-implied priors, blends | L3 | partial | n/a | Requires policy change |

## 8. Open questions and owner decisions

**Owner decisions**

1. **L3 policy change:** whether any market-derived element (market-implied ratings, closing line as prior or target, blending) should be evaluated at all. This survey documents trade-offs and does not recommend adoption.
2. **Interval level:** treat the adoption gate as one-sided 5% (so the code's 90% interval already matches) or two-sided 95% (change the code to 95% and apply Amendment 2).
3. **Confirmation season:** whether 2026 is designated the one-shot fresh holdout for the frozen finalist, given that 2022-2025 are exposed.
4. **Totals diagnostic:** whether to pre-register the recommendation 1 diagnostic as the first post-2026-12-13 contract.

**Evidence gaps to close before relying on this survey**

- Live CFBD checks: whether `/player/returning` 2014-2019 is preseason-as-of or recomputed; whether `/roster` is a snapshot; FCS play-by-play depth by year; weather forecast vs observed; `/lines` capture timing.
- Fetch primary methodology pages the agents could not reach: Connelly's SP+ method (weights, preseason fade schedule, margin-to-spread conversion), FEI, Sagarin, Massey, KenPom and Barttorvik formulas, and PredictionTracker's college-football page for independent MAE.
- Full-text reads of Glickman 2001, Fair and Oster 2007, Levitt 2004 and the 29-system college metamodel; verification of the vig-removal and spread-to-probability conversions.
- Measure the actual per-game SD of paired absolute-error differences and the design effect from existing outputs (drives every power figure).
- JP+ methods remain unverified.

## Sources

Access date 2026-11-19 for all, except the CFBD data-availability page (last verified by CFBD 2026-09-03). Tier tags as defined above. Items marked "snippet" were read through search summaries, not the full text.

**Rating systems**
- ESPN, 2026 college football SP+ rankings (138 FBS teams), https://www.espn.com/college-football/story/_/id/48306284/2026-college-football-sp+-rankings-138-fbs-teams `[PC]`
- ESPN, 2025 preseason SP+ rankings, https://www.espn.com/college-football/story/_/id/45966848/college-football-2025-preseason-sp+-rankings `[PC]`
- ESPN Stats and Info, an inside look at college FPI, https://www.espn.com/blog/statsinfo/post/_/id/122612/an-inside-look-at-college-fpi `[PC]`, date unclear; ESPN FPI page, https://www.espn.com/college-football/fpi `[PC]`
- bcftoys (FEI), https://www.bcftoys.com and https://www.bcftoys.com/glossary `[PC]`
- CFBD methodology overview, https://api.collegefootballdata.com/methodology-overview.md `[PC]`
- Football Outsiders SP+ overall 2018 and Sagarin college page (search summaries) `[S]`; thepowerrank guide to CFB rankings (2014-era) `[S]`

**Architectures**
- Glickman and Stern 1998; Glickman 2001, https://informahealthcare.com/doi/abs/10.1080/02664760120059219 (abstract) `[PH]`
- Koopmeiners 2012 (JQAS), https://www.degruyterbrill.com/document/doi/10.1515/1559-0410.1422/html `[PH]`
- Karlis and Ntzoufras 2003; Baio and Blangiardo 2010, https://econpapers.repec.org/RePEc:taf:japsta:v:37:y:2010:i:2:p:253-264 `[PH]`, soccer
- Lopez, Matthews and Baumer, https://arxiv.org/pdf/1701.05976 `[PH]`
- Wang, Johnston and Jones 2011, https://econpapers.repec.org/RePEc:bpj:jqsprt:v:7:y:2011:i:3:n:23 ; Gajewski 2006, https://www.degruyterbrill.com/document/doi/10.2202/1559-0410.1009/html ; Benz, Bliss and Lopez 2024, https://arxiv.org/pdf/2401.16392 `[PH]`/`[PC]`
- FiveThirtyEight NFL methodology (Elo margin multiplier), https://fivethirtyeight.com/methodology/how-our-nfl-predictions-work (snippet) `[PC]`
- MOV-cap blog tests and practitioner pages: netprophetblog (2011), talismanred.com, davidgolding.com, TeamRankings preseason explainer `[S]`

**Totals**
- Neil Paine, relative impact of offense vs defense on scoring (Football Perspective, 2013), https://www.footballperspective.com/another-note-on-the-relative-impact-of-offense-vs-defense-on-scoring/ `[PH]`
- KenPom glossary and help pages, https://kenpom.com/blog/ratings-glossary/ (snippet; fetch returned 403) `[PH]`
- NFL state-dependent Poisson scoring paper, https://informs-sim.org/wsc24papers/con253.pdf (not read in full) `[PH]`
- Stanford Stats 50 NFL weather project, https://web.stanford.edu/class/stats50/projects16/Houghton-BerryParkPierce-paper.pdf `[PH]`; weather rules of thumb at deucescracked.com and sharpfootballanalysis.com `[S]`
- sticktothemodel.com odds history (13,499 FBS closing lines, 2013-2026), https://sticktothemodel.com/cfb-betting/odds-history `[PC]`, not used as a model input

**Market**
- Pinnacle educational pages on CLV, limits, efficiency and public betting percentages, https://www.pinnacle.com/betting-resources/en/educational/what-is-closing-line-value-clv-in-sports-betting `[PC]`, self-interested
- Levitt 2004, https://www.nber.org/papers/w9422 `[PH]` (abstract)
- Fair and Oster 2007, via https://benny.aeaweb.org/conference/2010/retrieve.php?pdfid=406 `[PH]` (abstract; identification via search summary)
- Sinkey and Logan working paper; Applied Economics Letters 2020, https://informahealthcare.com/doi/abs/10.1080/13504851.2020.1795063 ; European Economic Review 2013 (via Springer link) `[PH]`
- Paul and Weinbach (2005), https://econpapers.repec.org/RePEc:spr:jecfin:v:29:y:2005:i:3:p:409-415 `[PH]`
- FiveThirtyEight, losing money betting on college football, https://fivethirtyeight.com/features/losing-money-betting-on-college-football-this-year-youre-not-alone (snippet) `[S]`
- drgreenandwhite.blogspot.com, spread vs margin study (2017) `[S]`; Circa and DRF press on weekly lines `[S]`; Football Perspective implied SRS and CFBNumbers market ratings `[S]`

**Evaluation**
- Hansen 2005 (JBES 23(4):365-380), https://scilit.com/publications/3acb201045eb64ffec5aeeb2043454cc `[PH]`
- Harvey, Leybourne and Newbold 1997 (secondary summary), https://nottingham-repository.worktribe.com/OutputFile/892033 `[PH]`
- Dwork et al., generalization in adaptive data analysis and holdout reuse, https://arxiv.org/pdf/1506.02629 `[PC]`
- White 2000, Romano and Wolf 2005, Hansen-Lunde-Nason 2011, Politis and Romano 1994, Diebold and Mariano 1995, Bailey and Lopez de Prado 2014: cited from memory, not fetched `[S]`

**Data**
- CFBD data availability, https://apinext.collegefootballdata.com/data-availability (and `.md` mirror), page last verified 2026-09-03 `[PC]`
- CFBD API tiers, https://collegefootballdata.com/api-tiers ; metrics and definitions, https://api.collegefootballdata.com/metrics-and-definitions.md ; PPA, https://api.collegefootballdata.com/ppa ; usage and access `[PC]`
- cfbfastR `create_epa`, `cfbd_coaches` reference pages; cfb.js client `[S]`
