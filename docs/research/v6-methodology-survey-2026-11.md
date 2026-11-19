# V6 methodology survey (November 2026)

**Status:** Research survey. Documentation only: no code, model, configuration or production change.
**Date:** 2026-11-19 (all sources accessed this date unless stated).
**Scope:** which rating system and modeling structure best serve college-football line prediction, and whether spreads and totals should be modeled separately. Model research starts after the 2026-12-13 final close; this page only prepares the ground.

## Reconciliation with audit steps 4C and 4D (added 2026-11-19)

This survey's first draft treated two questions as untested that the [baseline audit](../plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md) had already answered on 2026-11-15. They are reconciled throughout:

- **Step 4C (totals head):** no shrinkage (alpha 1 to 1000) or linear feature form (one combined feature, or offense and defense sums) lifts the total (best gain 0.02 against a declared 0.20); predictions correlate +0.13 to +0.18 with actual totals and beat a constant by only 0.07 to 0.09 MAE. The flat total is a **signal limit** of the V5 PPP ratings, not an over-shrinking or cancellation defect. Earlier wording in this survey that blamed a bridge "specification or scaling problem" is withdrawn.
- **Step 4D (venue flag):** setting the stored neutral-site flag in the margin bridge overshoots the neutral bias (-1.50 becomes +2.53 on 80 FBS-vs-FBS neutral games, 2023-2025; low power; no evidence of an effect). A neutral-site flag is therefore not recommended again as an untested gap.
- **What 4C did not test:** a pooled symmetric team-score model (`team_pts ~ own_off + opp_def + role`) and a multiplicative / log-link form. That is the only totals-head structure left, and it is drafted as a contract ([pooled team-score totals diagnostic](../plans/2026-11-19/pooled-team-score-totals-diagnostic.md), Draft). If it also shows no signal, the totals fix must move upstream to rating-state inputs.
- An existing declaration, [totals research from scoring opportunities](../modeling/offseason_totals_drive_sample.md), already builds the upstream inputs (opportunity creation, finishing, starting field position); this survey's rating-state recommendation points to it rather than duplicating it.

## How to read this survey

- **Evidence quality is mixed and stated per claim.** Six parallel web-research passes fed this page. Most agents could read abstracts and search summaries, not full papers, and several primary pages (SP+ and FEI methodology, Sagarin, Massey, PredictionTracker, KenPom) were not retrievable. Where a claim rests on that, it is tagged accordingly.
- **Source tiers:** `[PC]` primary-current (author's current published method), `[PH]` primary-historical (older writeups, papers), `[S]` secondary or inferred (blogs, press, or this survey's own reasoning and arithmetic). Self-reported ATS records are treated as unverified.
- **Policy labels** (from `AGENTS.md`, [`betting_policy.md`](../modeling/betting_policy.md) and Amendment 5 of the [offseason research protocol](../plans/2026-11-12/02-offseason-research-protocol.md)): **L1** allowed now (football-only inputs, methods, evaluation); **L2** post-freeze monitoring only (market views reported after a candidate is frozen, never an input or a selection criterion); **L3** requires a betting-policy change (owner decision).
- **Feasibility** means: can the input be obtained point-in-time for 2015-2019 and 2021-2025 from CFBD or another clean free source without lookahead leakage? `yes`, `partial` (with years), or `no`. CFBD's documentation is largely silent on whether stored historical values are revised, so `yes`/`partial` verdicts rest on coverage and payload fields checked in a live read-only audit on 2026-11-19 (Section 6); no endpoint exposes an as-of timestamp, so provenance is not proven.
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
| 1 | **Run the narrow pooled symmetric team-score + multiplicative totals diagnostic** (drafted, not approved; waits for 2026-12-13 and an owner go-ahead). It tests only what step 4C did not: a team-score structure and a log-link form on existing rating states. | Flat totals | Unknown; the strongest prior is that step 4C's null result (correlation +0.13 to +0.18) is a signal limit, so a null here is the likelier outcome. Value is in closing the structure question cheaply. | L1 | yes (existing rating states; no new input) |
| 2 | **If recommendation 1 is null, move the totals fix upstream to rating-state inputs**: scoring-opportunity creation, finishing, starting field position (already declared in the drive-sample document), special teams, turnover/havoc, and weather. SP+, FEI and FPI carry these as separate units; the closed V6 lab did not. | Flat totals; general margin MAE | Plausible but unproven: no verified public system publishes a total, so there is no published proof that these inputs fix a flat total. | L1 | partial (derivable from CFBD plays and drives 2001-present; finishing coverage is thin in the drive sample; see Section 6) |
| 3 | **Beyond the frozen P3**: test an unsaturated or convex margin link and a tier-conditional prior mean with heteroscedastic variance for lopsided matchups. P3 (FBS-vs-FCS indicator plus early conference-tier terms) already passes the declared conditions on selection seasons and is frozen for 2027; this recommendation covers only what P3 leaves out. | Stage-0 bias | No published CFB test found `[S]`; treat as a hypothesis. | L1 | partial (FCS play coverage in CFBD: see Section 6) |
| 4 | **Re-weight the multi-signal prior**: SP+ now gives recruiting about 1-2% (was 20-25%) and added a coaching-change factor. Keep returning production; ablate recruiting. | Stage 0-3 error | Modest; a cheap ablation of an existing design choice. | L1 | recruiting yes; returning production partial; coach change partial (head coaches only) |
| 5 | **Evaluation upgrades** (Section 5): adjusted-p-value tournament test, week-cluster sensitivity, measured sigma and design effect, and 2026 as the one-shot confirmation season. Amendment 2 (two-sided 95%, season/week blocks) is applied. | Selection bias; underpowered gates | Prevents adopting noise; see the measured power figures. | L1 | n/a |
| 6 | **Post-freeze market monitoring**: CLV against near-kickoff captures, MAE vs market, cutoff vs closing line. | None (diagnostic) | Honest benchmark after freeze. | **L2** | yes for own captures; CFBD `/lines` partial |
| 7 | Market-implied ratings, closing line as prior or target, market-blended forecasts, market-informed prioritization. | Totals and stage 0 | Likely the strongest accuracy lever (Fair and Oster 2007 found no rating system held information absent from the final line `[PH]`) but conflicts with policy. **Owner decision (2026-11-19): not in the first V6 wave.** | **L3** | partial |

Not recommended again: a neutral-site flag in the margin bridge (step 4D) and shrinkage or sum-form changes to the totals head (step 4C).

**Direct answers.**

- *What rating system best serves line prediction?* The evidence does not crown a single system. The public systems that publish margins (SP+, FPI) rate offense, defense and special teams as separate **points-scale** units, so a rating difference is already a margin. V5's PPP ratings need a learned bridge, and that bridge is where totals flatten. The most defensible lesson is structural (points-scale units plus a team-score formulation), not "adopt SP+'s five factors".
- *Spreads and totals: separate or joint?* No source found compares the two on totals accuracy in any sport, and V5's own step 4C found that the flat total is a signal limit of the ratings, not a bridge defect. The literature-backed joint team-score structure is therefore a cheap, narrow diagnostic (recommendation 1), not a presumed fix; the more likely lever is upstream inputs (recommendation 2). Spreads and totals can stay separately fitted heads on shared rating states until that diagnostic says otherwise.
- *Is there a market fix for stage 0?* Only at policy label L3, which the owner has ruled out for the first V6 wave. Football-only options (recommendations 3 and 4) are available now.

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
- **Home-field and neutral site.** (Reconciled with step 4D: the stored neutral-site flag did not reduce V5's neutral bias and overshot it on 80 FBS-vs-FBS neutral games, so this is not an open fix.) College football home advantage is heterogeneous (about 6 points, larger for non-BCS teams after controls, Wang-Johnston-Jones 2011; per-team parameters, Gajewski 2006; a decline reported by Benz-Bliss-Lopez 2024) `[PH]`/`[PC]`. The standard form is a per-game venue term (home +1, neutral 0, away -1) with optional shrunken team deviations. V5's constant `home_host=1.0` with the edge in the intercept is the structural cause of the -2.69 regular-season neutral-site margin bias, but step 4D shows that merely setting the flag does not repair it; the team labelled home in a neutral game has no consistent edge, so any future treatment needs a different design (for example team-level deviations) and more than 126 neutral games.

**Stage-0 handling summary.** The best-supported football-only levers are a tier-conditional prior mean, an explicit FCS tier, and an unsaturated or convex margin link; per-stage intercepts (B1s) fix the mean but worsen balanced games, as the audit found. The in-season stage 1-3 updating problem (moves of 8-10 points without MAE gain) is consistent with a process-noise setting that is too loose for sparse data; no published guidance transfers.

## 3. Spreads and totals

**Recommendation: keep margin and total as separately fitted heads on shared rating states for now; test the one totals structure step 4C did not (pooled symmetric team-score, multiplicative form) as a narrow diagnostic; and expect the real totals lever to be upstream inputs.** Confidence is low-to-medium: no source found compares joint and separate models on totals accuracy in any sport.

What V5's own audit already settled (step 4C, run 2026-11-15):

- V5's total is a linear function of four ratings (home/away offense and defense) with small fitted coefficients (0.5-1.75 points per rating SD vs 7-11 for margin), and offense and defense ratings correlate +0.42 to +0.51. The tempting reading, that this is a bridge specification or scaling defect, was **tested and not supported**: ridge strength from 1 to 1000 changes totals by under 0.02 MAE, and collapsing the four terms into one combined feature or into offense and defense sums changes nothing outside noise. The predictions' correlation with actual totals is +0.13 (selection seasons) to +0.18 (2022-2025), and they beat a training-mean total by only 0.09 and 0.07 MAE. The flat total is a **signal limit** of the PPP ratings.
- Step 3 found possession volume is not the missing input, so pace should be a secondary term, not the lead.
- One observation from 4C that was not tested: the slope of actual on predicted total is 1.6-1.8, so predictions are under-dispersed even for the little signal they carry. A rescaling was not in the declared list and is not claimed here.

What the literature adds (all non-CFB, mostly inferential):

- NFL (1978+, a team's points regressed on own offense and opposing defense ratings): coefficients about 0.95 and 0.93, R² 0.27; offense about 58% and defense about 42% of explained variance `[PH]` (blog analysis). Season-long ratings explain only about a quarter of single-game team scoring, so a realistic predicted-total SD stays far below the 16.90 actual. The earlier survey draft's "roughly 4-7" figure is weakly grounded `[S]` and should not be read as a target.
- KenPom-style tempo-free systems compute each team's score as possessions times a multiplicative offense-times-opponent-defense efficiency `[PH]`, non-CFB, formula inferred (page not retrievable). The multiplicative form gives interaction in the total that a linear four-term bridge lacks, but it cannot create signal the ratings do not contain.
- Soccer's bivariate Poisson adds a covariance term for dependence the ratings do not explain; empirical home-away correlation is low `[PH]`, non-CFB.
- Weather: wind is the most consistently supported effect in NFL studies (a student regression -0.26 points per mph; heat, wind and rain reduce scoring `[PH]`); betting-site rules of thumb (2.5-3.5 points at 15-20 mph) are unverified `[S]`; no CFB effect sizes were found, and cold appears to be over-priced by the market.

**What remains to test (recommendation 1; drafted, not approved).** The [pooled team-score totals diagnostic](../plans/2026-11-19/pooled-team-score-totals-diagnostic.md) fits `team_pts ~ own_off + opp_def + role` pooled over both teams (additive, and a multiplicative log-link form), sums the two predicted scores, and scores the result against the baseline on the 4C population and bar. It does not repeat 4C's shrinkage or sum-form candidates and does not re-test a venue flag (4D). If it also yields no signal, the totals fix must move upstream to rating-state inputs: the scoring-opportunity inputs already declared in [`offseason_totals_drive_sample.md`](../modeling/offseason_totals_drive_sample.md), special teams, turnover/havoc, and weather. The unexplained observation that home offense moves V5's total about 3x as much as away offense is not addressed by 4C and should be checked inside that diagnostic as a role-coefficient comparison.

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
- **Interval level.** Decided: two-sided 95% (a one-sided 2.5% test). The multiplicity adjustment matters more than 90 vs 95.
- **Report the finalist, not the best of K.** The interval for the single frozen finalist; the best-of-K estimate is upward biased.
- **Consistency guard.** Require the gain to carry the same sign in at least 3 of 4 seasons.

**Gap versus the current protocol: closed 2026-11-19.** The code returned 90% intervals while the adoption thresholds named 95%. The owner standardized on a **two-sided 95% paired bootstrap interval with season/week block resampling as primary** (Amendment 2, applied: `paired_comparison` takes `confidence_level`, default 0.95; recorded in the protocol and `protocol.yaml`). It is distinct from the models' 90% prediction intervals. The block resampling captures same-week dependence and omits same-team dependence across weeks and seasons (measured below). Consequence for scripts: `scripts/research/run_v6_tournament.py` gates on the interval's lower bound, which is now the 2.5th rather than the 5th percentile, so that gate is stricter than before.

**Power with assumed sigma (survey arithmetic, `[S]`; superseded below by measured sigma).** n = ((z_alpha + z_power) x sigma / delta)^2 with delta = 0.2 MAE, power 80%, independent games, normal approximation; sigma is the SD of the per-game absolute-error difference.

| sigma | n needed, two-sided 5% | n needed, one-sided 5% | MDE at n=3,483 | Power at 0.2, n=3,483 | MDE at n=870 | Power at 0.2, n=870 |
|---|---|---|---|---|---|---|
| 4 | 3,140 | 2,473 | 0.19 | about 84% | 0.38 | about 31% |
| 5 | 4,906 | 3,865 | 0.24 | about 66% | 0.48 | about 22% |
| 6 | 7,064 | 5,565 | 0.29 | about 50% | 0.57 | about 16% |

Consequences: at sigma 5-6 a 0.2 gain is underpowered even on all 3,483 games; one 870-game season cannot detect it at any of these sigmas; a design effect of 1.5 raises the minimum detectable effect by about 22%; with K = 20 candidates the Bonferroni minimum detectable effect at sigma 5 is about 0.33 (max-statistic methods land lower, plausibly 0.28-0.30). The stage 0-3 subset (886 games) has a minimum detectable effect near 0.47 at sigma 5, so the protocol's 0.2 stage 0-3 gain threshold is mostly a decision rule on point estimates, not a test.

Empirical sigma can be backed out of the existing audit: the 90% intervals for B1 (0.05 to 0.36), B1s (0.33 to 0.76) and B2 (-0.01 to 0.31) on the 886 stage 0-3 games imply per-game SDs of roughly 2.8-3.9 points under game-level iid (half-width = 1.645 x sigma / sqrt(886)). Small perturbations of V5 have small sigma; a structurally different V6 will have larger sigma and need more data. Measure it per candidate rather than assume.

**Measured sigma and design effect (2026-11-19, read-only, local audit outputs).** Per-game differences d = Operational V5 absolute error minus candidate absolute error, over the 3,483 regular-season games per target (2,998 FBS-vs-FBS), season-week block bootstrap (5,000 replicates, seed 20260928). Only candidates with per-game outputs on disk are covered; step 4B/4C/4D candidates (B1s, B3, P1-P4, totals forms, venue) are stored as aggregates and could not be reconstructed offline. Detection size uses two-sided 95% and 80% power.

| Comparison to Operational V5 | Target | sigma (pooled) | Block design effect | n needed for a 0.2 gain | Minimum detectable effect at 3,483 |
|---|---|---|---|---|---|
| Near-identical variants (repaired arm, single-cumulative, game-adjusted at cutoff) | margin | 1.35-1.38 | 1.2-1.25 | 450-465 | 0.07 |
| Same, totals | total | 1.13-1.18 | 1.1 | 275-300 | 0.056-0.059 |
| Game-adjusted first-boundary variant | margin | 4.06 | 0.93 | 3,008 | 0.186 |
| Historical V5, preseason-prior-only, snapshot-stream replica | margin | 8.3-8.6 | 1.45-1.56 | 19,600-22,600 | 0.48-0.51 |
| Same class, totals | total | 1.5-2.0 | 1.06-1.31 | 600-830 | 0.08-0.10 |

- **The assumed sigma of 4-6 holds for only one measured candidate** (the first-boundary margin variant, 4.06 pooled, 4.7 at stage 0-3). Variants that stay close to V5 have sigma about 1.1-1.4 and a 0.2 gain is easily detected. Structurally different margin models have sigma about 8.3-8.8, and a 0.2 margin gain is **not** detectable on this sample (needs about 20,000 games; minimum detectable effect 0.48-0.56). The earlier back-calculation from the audit's step 4B intervals (sigma about 2.8-3.9 on 886 stage 0-3 games) sits between the two classes. **Power therefore depends on how far a candidate moves predictions from V5; measure sigma per candidate.**
- **Totals comparisons are well powered** even for structurally different models (sigma about 1.5-2.0, minimum detectable effect about 0.1): V5's flat totals mean any candidate's totals differ little from V5's.
- **Season-week design effects are modest and mixed**: mostly 0.9-1.6 (one tiny-sigma outlier at 2.7), below 1.0 for several stage 0-3 margin comparisons. A blanket inflation factor of 2 would be too conservative for margin.
- **Team clustering matters more for totals**: home-team design effects on totals are about 1.4-1.9 and away-team about 1.2-1.4, above the block figure on the same comparisons (margin team design effects about 0.8-1.2; these are analytic cluster-robust estimates, not bootstrapped). Because the primary interval resamples season-week blocks only, **total-MAE gates should report a team-clustered sensitivity interval** next to the game-level one already declared in Amendment 2. This is a suggested addition, not part of the applied amendment.
- Scripts and the full table: scratchpad `sigma/sigma.py` and `sigma/sigma_results.csv` (session scratch, not committed).


## 6. CFB-specific inputs and point-in-time feasibility

Coverage years and tiers come from CFBD documentation `[PC]` (page last verified by CFBD 2026-09-03). On 2026-11-19 a read-only live audit (91 calls, Tier 2 key, 30,000 calls per month, API version 5.34.0) checked coverage and payload fields for 2015-2019 and 2021-2025. **Findings are payload evidence only: no endpoint exposes an as-of, version or capture timestamp, so none of them can prove a value was frozen at the time.** Verified items are marked below; provenance questions that a payload cannot answer remain open and can only be settled by re-pulling the same year later and comparing, or by asking CFBD.

| Input | Source | 2015-19 | 2021-25 | Verified 2026-11-19 | Verdict |
|---|---|---|---|---|---|
| Returning production | `/player/returning` | covered (128-130 teams per year) | covered (128-134) | One row per team per year, no timestamp or version field. The `conference` label for year Y is the prior-year conference (USC shows Pac-12 for 2022-2024 and Big Ten for 2025), which mildly supports a prior-season, preseason-style construction. Teams in their first FBS year already have rows. Provenance not proven. | partial (leaning yes; provenance unproven) |
| Transfer portal | `/player/portal` | **empty** (0 rows 2015, 2017, 2019, 2020) | 1,770 (2021) to 4,499 (2025) rows, each with a `transferDate` | Dates support an as-of cutoff filter (only 3 rows on or after Aug 25 of the season, all in 2022). `eligibility` is a mutable status (TBD, Withdrawn) and would leak if used as of entry time; destination is often null (about 40% in 2021, 16% in 2025). Some minimum dates fall oddly early. | no for 2015-19; partial 2021-25 (use entry date only) |
| Roster continuity | `/roster` | archive-like (player-id overlap 0-3% across 4+ years) | archive-like | Not a latest snapshot, but no snapshot date; the class-year field is unreliable (2015 stores the season value; Alabama 2025 has 91 of 127 players as class 1). | partial (identity continuity usable; class and age not) |
| Recruiting composites | `/recruiting/*`, `/talent` | yes (docs: 2000-present) | yes | Not re-checked live (documentation only). | yes (unverified live) |
| Head-coach changes | `/coaches` | yes | yes | Not re-checked live; coach SP+ and SRS fields are end-of-season outcomes: exclude. | yes (head coaches) |
| Coordinator changes | not in CFBD | no | no | n/a | no |
| QB changes and injuries | none in CFBD | no | no | Ex-post starter is leakage; no free timestamped source found. | no |
| Opt-outs | not documented | no | no | n/a | no |
| FCS opponents | `/games`, `/plays`, `/drives` | present | present | 15 sampled FBS-vs-FCS games (3 per year in 2015, 2018, 2021, 2023, 2025): FCS-side plays 67-108 per game, drives within 1-2 of the FBS side, PPA non-null on 117-168 plays per game. FBS-vs-FCS games per year: 105-126. Sample only; completeness across all games unproven. | partial to yes (sampled) |
| Garbage time | CFBD rule (margin over 38 in Q2, 28 in Q3, 22 in Q4) | yes | yes | Deterministic from play state; SP+ definition not found. | yes |
| EPA | CFBD PPA vs cfbfastR `create_epa()` | partial | partial | A single fixed model across history is likely fitted with later data (mild leakage); training data not stated. | partial |
| Weather | `/games/weather` | non-null in every row, every year | same (Tier 2 allows it) | **No forecast-versus-observed indicator and no issue time.** Fractional temperatures and wind (about 62-89% of rows) look gridded or reanalysis-derived. `weatherCondition` is sparse before 2018 (14 of 863 rows in 2015). Treated as observed-style data: leakage risk as a pregame input. | no as a pregame input unless a forecast vintage is captured; see the forecast-capture pilot in the [two-week preparation plan](../plans/2026-11-19/model-head-start.md) |
| Betting lines | `/lines` | covered (consensus, numberfire, teamrankings, Caesars, Bovada by year) | covered (William Hill, Bovada, DraftKings, ESPN Bet) | No capture-time field; `spreadOpen` is 0 for every provider in 2015-2019; the provider set changes by era; moneylines only for recent Bovada, DraftKings and ESPN Bet rows. Policy-restricted as a model input in any case. | partial (monitoring only; L2) |

Inputs scoring **no** (listed, not recommended): coordinator changes, QB changes and injuries, opt-outs, 2015-2019 portal data, and weather as a pregame input from `/games/weather`. The training range for any portal feature starts in 2021, so a fit using it cannot satisfy the selection-season rule (at least three earlier training seasons) before 2024 unless earlier seasons are imputed, which would be a design decision.

## 7. Gap map

| Operational V5 gap | Candidate methods | Policy | Point-in-time feasibility | `ratings_lab` host | Relation to tested or frozen candidates |
|---|---|---|---|---|---|
| Flat totals (SD 1.57 vs 16.90; correlation +0.164) | Step 4C: shrinkage and sum forms **tested, no gain** (signal limit). Remaining: pooled symmetric team-score and multiplicative form (drafted diagnostic); then upstream rating-state inputs (opportunity creation, finishing, field position, special teams, turnover/havoc) and wind | L1 | yes for the diagnostic (rating states); inputs partial; weather partial | `total_bias.py` for the diagnostic; `measurements.py` for new inputs | 4C covered shrinkage and F1/F2; step 3 ruled out possession volume; P1-P4, B1s and B3 are margin-side; the drive-sample declaration covers the upstream inputs |
| Stage 0 (bias +7.51, MAE 16.17) | Tier-conditional prior mean; FCS tier; unsaturated or convex margin link; heteroscedastic variance | L1 | partial | `priors.py`, `error_slices.py` | Overlaps frozen 2027 candidate P3 (FBS-vs-FCS indicator plus early conference tier) and scored B3; B1s fixed the mean but worsened balanced games |
| Stage 1-3 updating (8-10 point moves, no MAE gain) | Fitted process noise; variance inflation early in the season | L1 | yes | `kalman.py`, `updaters.py` | Not directly tested |
| Neutral site (margin -2.69, total -5.02) | Step 4D: stored flag **tested, overshoots** (-1.50 to +2.53 on 80 FBS-vs-FBS neutral games; low power). Not re-recommended; any future design needs team-level deviations and more neutral games | L1 | yes (`game_venues`; flag 2021-2025 only locally) | feature frame and bridge | Covered by 4D; the totals side (-5.02) is untested but small-sample (126 games) |
| Missing units (special teams, field position, finishing drives, turnover/havoc) | Add units to the rating state | L1 | partial | `measurements.py`, `adjusted_game.py` | Closed V6 lab did not include them |
| Prior composition | Ablate recruiting; keep returning production; add coach-change flag | L1 | partial | `priors.py` | Extends the closed lab's multi-signal prior |
| Selection and power | SPA or Romano-Wolf; week-cluster bootstrap; fresh-season confirmation; measure sigma and design effect | L1 | n/a | `evaluation.py` (`paired_comparison`: 90% vs 95% gap) | Complements the protocol's finalist rule and ledger |
| Market gap (benchmark) | CLV, MAE vs market, cutoff vs closing | L2 | own captures | outside `ratings_lab/` | Only after a candidate is frozen (Amendment 5) |
| Accuracy ceiling | Market-implied priors, blends | L3 | partial | n/a | Requires policy change |

## 8. Open questions and owner decisions

**Owner decisions recorded 2026-11-19**

1. **Betting policy (L3): stay strictly L1 (football-only) for the first V6 wave.** `docs/modeling/betting_policy.md` is unchanged. Revisit L3 only after a clean football-only V6 reaches its ceiling and is benchmarked through L2 post-freeze monitoring.
2. **Interval level (Amendment 2): two-sided 95% paired bootstrap interval, season/week block resampling as primary**, distinct from the models' 90% prediction intervals. Applied the same day (see Section 5).
3. **Confirmation season: 2026 is the one-shot fresh confirmation holdout** for newly frozen V6 finalists, scored once after the 2026-12-13 final close and holdout export. The already-exposed margin candidates (B1s, B3, P1-P4) are excluded from that role because their 2026 weeks 0-6 were scored on 2026-11-15.
4. **Totals diagnostic contract: draft only.** No model candidate runs before 2026-12-13. The draft is [`pooled-team-score-totals-diagnostic.md`](../plans/2026-11-19/pooled-team-score-totals-diagnostic.md), scoped to what steps 4C and 4D did not test.
5. **Live CFBD point-in-time audit: approved and run read-only** (Section 6).

**Still open**

- Approve or amend the draft thresholds in the totals diagnostic contract and give the go-ahead after 2026-12-13.
- Add a team-clustered sensitivity interval for total-MAE gates (Section 5)?
- Amendment 1 (comparator) remains unapplied.
- Evidence gaps not closed by this survey: SP+ and FEI methodology pages, Sagarin, Massey, KenPom and Barttorvik formulas, PredictionTracker's independent MAE, full texts of Glickman 2001, Fair and Oster 2007 and Levitt 2004, vig-removal and spread-to-probability conversions, and JP+ methods (unverified).

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
