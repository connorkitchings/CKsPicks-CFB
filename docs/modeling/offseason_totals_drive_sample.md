# Totals research from scoring opportunities

Operational V5 averaged 13.49 points of total MAE over the 2,998 regular-season FBS-vs-FBS games in the 2022–2025 headline population. The November audit found a gain of about 0.07 over a training-mean forecast. [Baseline audit](../plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md)

## Input definitions and lineage

The sample uses the historical byplay partitions named in the same rebuild used by the Operational V5 historical audit. The September repair manifest returned `NoSuchKey` from the configured source reader. The sample records the rebuild root, Silver summary, per-season byplay, forecast frame and postseason-exclusion hashes. The forecast frame supplies identities, nominal weeks, kickoffs and completed-game stages. The point-in-time feature loader receives only identity and timing columns. The retained frame’s validated final scores are used as a ledger quality check. The sample carries no outcomes.

| Measurement | Denominator and value |
|---|---|
| Opportunity creation | Fraction of eligible regulation drives with an eligible first-down play strictly inside the opponent's 40, following the Eckel definition |
| Finishing | Allocated eligible regulation offensive points on those drives, divided by the number of opportunities |
| Starting field position | Mean yards to goal on the first recorded play per eligible drive, using drives with known starting positions |

The research script uses the V5 historical possession ledger and eligibility filter. Garbage-time, special-teams, penalty, conversion, dead-play and overtime rows do not establish drive eligibility. An eligible drive can contain excluded plays. Excluded offensive, non-offensive and overtime points never enter finishing. Conversions attributed to an eligible offensive scoring event count toward that event's drive. Unresolved attribution makes finishing unavailable for the affected offense when that observation enters the aggregate. A game whose score ledger fails to reconcile to the validated final score for either team contributes no finishing points. Ambiguous or non-regulation drives are excluded. The underlying V5 V1 play filter retains its documented punt-return edge case.

An eligible drive that has no opportunity contributes a zero to the opportunity rate. A drive whose opportunity status cannot be determined reduces coverage and leaves creation and finishing missing in the cumulative snapshot. Zero opportunities give a missing finishing rate. Missing history and an offense that created zero opportunities therefore remain distinct. The artifact includes each denominator and source coverage count. Defensive values track opportunities and points allowed and opponents' starting position.

Closed V6 ran four four-factor measurement stages and one five-factor stage. The latter included `finish_points_per_opp`, using a broader within-40 rule and nominal seven/three-point scoring. It did not include opportunity frequency or starting field position. Those are the candidate's new inputs. Its finishing input overlaps the existing football concept, with different opportunity eligibility and attributed scoring. The implementation is in `src/cks_picks_cfb/ratings_lab/measurements.py`. [Closed V6 measurements](../plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md)

## Building and checking the sample

Run `scripts/research/prepare_totals_drive_sample.py` through the project Python environment. Set a research source and isolated local lab root using the ratings-lab configuration. Supply the audit's rebuild-root JSON, Silver summary, retained historical feature frame, postseason ID file and season membership directory from the audit. The command outputs the sample, coverage by season and completed-game stage, a drive audit, a scoring audit and input pins. It uses a research-specific `load_point_in_time_data()` because the earlier V4 loader was removed during cleanup. Each week gets the same reconstructed cutoff at its earliest scheduled kickoff. History stays within the same season and must be from an earlier nominal week and available strictly before the cutoff after a six-hour post-kickoff buffer. This is historical reconstruction and the cutoff is a proxy for issuance.

The input frame and summaries are the retained `6a-rebuild-w5-20261007-r2` artifacts. Point `TOTALS_REBUILD_ROOT` at that directory, `TOTALS_POSTSEASON_IDS` at the audit's `postseason_game_ids.json`, and `TOTALS_MEMBERSHIP_DIR` at its directory of yearly `teams_<season>.json` files.

```bash
PYTHONPATH=src:. uv run python scripts/research/prepare_totals_drive_sample.py \
  --forecast-frame "$TOTALS_REBUILD_ROOT/forecast/feature_frame.parquet" \
  --silver-summary "$TOTALS_REBUILD_ROOT/silver/summary.json" \
  --rebuild-root "$TOTALS_REBUILD_ROOT/root-manifest.json" \
  --postseason-ids "$TOTALS_POSTSEASON_IDS" \
  --membership-dir "$TOTALS_MEMBERSHIP_DIR" \
  --output-dir "$CFB_LAB_LOCAL_ROOT/output"
```

## Coverage and drive checks

The run contains 8,520 regular-season forecast rows across the ten development seasons. The matchup split is 7,376 FBS-vs-FBS and 1,144 FBS-vs-FCS. The play rebuild yielded 194,657 eligible drives and 81,418 scoring events. The full score ledger matched both recorded finals in 7,981 of the 8,488 games with eligible drives. The complete per-season and stage counts for each unit and population are in `coverage.csv`.

| FBS-vs-FBS season | Games | All four units with creation | All four units with finishing | All four units with start position |
|---|---:|---:|---:|---:|
| 2022 | 734 | 646 | 147 | 681 |
| 2023 | 750 | 695 | 296 | 698 |
| 2024 | 752 | 707 | 319 | 713 |
| 2025 | 762 | 658 | 213 | 714 |
| **2022–2025** | **2,998** | **2,706** | **975** | **2,806** |

| FBS-vs-FBS stage, all development years | Games | All four units with creation | All four units with finishing | All four units with start position |
|---|---:|---:|---:|---:|
| 0 | 462 | 0 | 0 | 0 |
| 1 | 513 | 501 | 374 | 506 |
| 2 | 601 | 595 | 448 | 601 |
| 3 | 636 | 626 | 445 | 636 |
| 4 or more | 5,164 | 5,005 | 2,561 | 5,164 |

Stage 0 has no same-season history. Finishing coverage is especially sparse in 2022 and 2025. The current strict season-to-date rate becomes unavailable for a unit once its observations include an opportunity with uncertain attribution or a game that fails score reconciliation. December reporting should expose this coverage and distinguish the experiment's availability for creation and field position from its much thinner evidence for finishing. The drive and scoring audit files carry the evidence for any later proposed change to that policy.

Three 2025 teams were checked against the individual drive rows and score categories.

| Game and team | Eligible drives | Opportunities | Finishing | Mean start |
|---|---:|---:|---:|---:|
| 401752665 Alabama | 10 | 5 | 17 ÷ 5 = 3.40 | 71.00 yards to goal |
| 401752668 Long Island University | 9 | 0 | Missing, with zero opportunities | 75.78 yards to goal |
| 401752666 Arkansas | 9 | 6 | 38 ÷ 6 = 6.33 | 68.44 yards to goal |

Arkansas' eligible opportunity drives were 1, 3, 9, 11, 14 and 16, with 7, 3, 7, 7, 7 and 7 points respectively. Its seven excluded offensive points stay in the score audit. The seven eligible points from drive 5 stay out of finishing because that drive never met the opportunity rule.

The local research output contains `sample.parquet`, `coverage.csv`, `drive_audit.parquet`, `scoring_audit.parquet` and `inputs.json`. The forecast sample uses reconstructed cutoffs and contains pregame features only. The two audit files retain postgame ledger evidence and are for reconciliation.

## Predeclared comparison after December 13

For each validation season, fit only permitted earlier seasons. Use the same regular-season universe and identical games for all arms, with FBS-vs-FBS as the headline and FBS-vs-FCS reported alongside it. Exclude 2020. Keep the held-out 2026 evidence sealed pending the research protocol.

1. Constant training-mean total.
2. Operational V5 earlier-only totals with the audit's offsets.
3. The same V5 earlier-only total bridge with the three measurements for each team and unit added to its existing inputs. Scale with training-season statistics only, impute missing values with training medians and retain missingness indicators. Use existing Ridge penalty and offset handling.

Report opportunity/finishing coverage by stage, pooled and season-level MAE and bias, early-stage results, RMSE, Gaussian CRPS and interval calibration using the approved protocol. A paired test compares candidate and baseline errors on the same rows. Finalize the official comparator and paired-interval protocol amendments before scoring. Starting field position is context for distinguishing short fields from sustained drives. No second challenger is selected from these rows. If creation and field position lack enough matched historical coverage for an interpretable test, record coverage as the outcome and stop before scoring.

No candidate was fitted to produce the sample.
