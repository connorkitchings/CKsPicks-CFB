"""Pure builder for ``team_game_metrics_v1`` (Window 2 Step 5B).

Turns plays, possessions, the admitted scoring ledger and certified finals into one row per
(game, team, role, metric) under the registry definitions and null semantics in
``cks_picks_cfb.metrics.contracts``. No storage, no I/O, no imputation:

- A play with no provider PPA withholds the EPA metrics whose population contains it, and
  only those; independent measurements (possession points, success, scoring) stay usable.
  Missing pass PPA does not invalidate a complete rush PPA, and vice versa.
- An ``unresolved`` scoring marker withholds that team-game's point metrics.
- Defense rows mirror the opponent's offensive measurement and provenance.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from cks_picks_cfb.data.play_filters import scrimmage_play_mask
from cks_picks_cfb.data.team_stats import _conversions
from cks_picks_cfb.metrics import registry as reg
from cks_picks_cfb.metrics.contracts import canonical_json_text

ADMITTED = (
    "baseline_unchanged",
    "corroborated",
    "reverted_unverified",
    "reverted_contradicted",
)
POINT_METRICS = (
    "offensive_possession_points",
    "ppp",
    "non_offense_points",
    "pts_per_scoring_opp",
)
EPA_POPULATIONS = ("eligible_epa", "epa_pass", "epa_rush", "early_down_epa")
GAME_COLUMNS = (
    "season",
    "week",
    "game_id",
    "season_type",
    "home_team",
    "away_team",
    "kickoff_utc",
    "home_points",
    "away_points",
    "home_fbs",
    "away_fbs",
)


class BuilderInputError(ValueError):
    """A required input column is absent; the builder never substitutes a default."""


def _require(frame: pd.DataFrame, columns: tuple[str, ...], label: str) -> None:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise BuilderInputError(f"{label} missing columns: {missing}")


def _num(value: Any) -> float | None:
    if (
        value is None
        or (isinstance(value, float) and np.isnan(value))
        or value is pd.NA
    ):
        return None
    return float(value)


def _row(
    meta: Mapping[str, Any],
    metric: str,
    *,
    num,
    den,
    eligible,
    observed,
    status="observed",
    reason=None,
    flags=(),
    versions: str,
    timing: str,
) -> dict[str, Any]:
    definition = reg.BY_NAME[metric]
    ratio = definition.kind == "ratio"
    value = None
    if status == "observed" and num is not None and den is not None:
        value = float(num) if not ratio else (float(num) / float(den) if den else None)
    return {
        **meta,
        "metric": metric,
        "definition_version": definition.definition_version,
        "population_id": definition.population_id,
        "numerator": num,
        "denominator": den,
        "value": value,
        "eligible_count": eligible,
        "observed_count": observed,
        "coverage_unit": definition.coverage_unit,
        "coverage_status": status,
        "missing_reason": reason,
        "quality_flags": canonical_json_text(sorted(set(flags))),
        "timing_class": timing,
        "source_versions": versions,
    }


def _count_row(meta, metric, count, *, versions, timing, **extra):
    return _row(
        meta,
        metric,
        num=float(count),
        den=1.0,
        eligible=int(count),
        observed=int(count),
        versions=versions,
        timing=timing,
        **extra,
    )


def _ratio_row(
    meta, metric, num, den, *, eligible, observed, versions, timing, **extra
):
    return _row(
        meta,
        metric,
        num=num,
        den=den,
        eligible=eligible,
        observed=observed,
        versions=versions,
        timing=timing,
        **extra,
    )


def _ppa_metric(
    meta,
    metric,
    plays: pd.DataFrame,
    denominator_plays: int,
    *,
    versions,
    timing,
    flags,
):
    """EPA-family numerator over ``plays``; missing when any PPA in the population is missing."""
    missing = int(plays["ppa_missing"].sum())
    total = len(plays)
    if missing:
        return _ratio_row(
            meta,
            metric,
            None,
            float(denominator_plays),
            eligible=total,
            observed=total - missing,
            status="missing",
            reason="ppa_incomplete",
            flags=[*flags, "ppa_incomplete"],
            versions=versions,
            timing=timing,
        )
    ppa = pd.to_numeric(plays["ppa"], errors="coerce")
    return _ratio_row(
        meta,
        metric,
        float(ppa.sum()),
        float(denominator_plays),
        eligible=total,
        observed=total,
        flags=flags,
        versions=versions,
        timing=timing,
    )


def build_team_game_metrics(
    *,
    plays: pd.DataFrame,
    possessions: pd.DataFrame,
    ledger: pd.DataFrame,
    games: pd.DataFrame,
    source_versions: Mapping[str, str],
    timing_class: str,
    coverage: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """One row per (game, team, role, metric) for every game in ``games``."""
    _require(games, GAME_COLUMNS, "games")
    if games.duplicated(["season", "game_id"]).any():
        raise BuilderInputError("duplicate games")
    # Coverage is supplied by verified source/reconciliation parents, never inferred
    # from the existence or absence of scoring rows.
    coverage_by = {}
    if coverage is not None:
        _require(
            coverage,
            (
                "season",
                "game_id",
                "team",
                "plays_complete",
                "possessions_complete",
                "scoring_complete",
            ),
            "coverage",
        )
        if coverage.duplicated(["season", "game_id", "team"]).any():
            raise BuilderInputError("duplicate coverage keys")
        if not source_versions.get("coverage"):
            raise BuilderInputError("coverage must have a pinned source version")
        for row in coverage.itertuples(index=False):
            flags = (row.plays_complete, row.possessions_complete, row.scoring_complete)
            if any(not isinstance(v, (bool, np.bool_)) for v in flags):
                raise BuilderInputError("coverage flags must be explicit booleans")
            coverage_by[(int(row.season), int(row.game_id), row.team)] = flags
    _require(
        plays,
        (
            "season",
            "game_id",
            "offense",
            "ppa",
            "success",
            "yards_gained",
            "down",
            "turnover",
            "dropback",
            "rush_attempt",
        ),
        "plays",
    )
    _require(
        possessions,
        (
            "game_id",
            "offense",
            "possession_id",
            "possession_eligible",
            "period_class",
            "quality_reason",
            "scoring_opportunity",
            "start_yards_to_goal",
        ),
        "possessions",
    )
    _require(
        ledger,
        (
            "game_id",
            "team",
            "score_increment",
            "scoring_category",
            "admission",
            "associated_possession_id",
        ),
        "ledger",
    )
    versions = canonical_json_text(dict(sorted(source_versions.items())))
    plays = plays[scrimmage_play_mask(plays)].copy()
    plays["ppa_missing"] = (
        plays["ppa_missing"].fillna(False).astype(bool)
        if "ppa_missing" in plays.columns
        else plays["ppa"].isna()
    ) | plays["ppa"].isna()
    drives = possessions[
        possessions["possession_eligible"].astype(bool)
        & possessions["quality_reason"].isna()
        & (possessions["period_class"] == "regulation")
    ]
    if not ledger["admission"].isin(ADMITTED).all():
        raise BuilderInputError(
            "unknown or candidate admission in final scoring ledger"
        )
    admitted = ledger
    drive_key = "drive_id" if "drive_id" in possessions.columns else "drive_number"
    for label, frame, keys in (
        ("possessions", possessions, ["season", "game_id", drive_key, "offense"]),
        ("ledger", ledger, ["season", "game_id", "source_event_id", "team"]),
    ):
        _require(frame, tuple(keys), label)
        if frame.duplicated(keys).any():
            raise BuilderInputError(f"duplicate {label} keys")
    unresolved = {
        (int(r.season), int(r.game_id), r.team)
        for r in ledger.itertuples()
        if r.scoring_category == "unresolved"
    }
    plays_by = {k: g for k, g in plays.groupby(["season", "game_id", "offense"])}
    drives_by = {k: g for k, g in drives.groupby(["season", "game_id", "offense"])}
    points_by = {k: g for k, g in admitted.groupby(["season", "game_id", "team"])}

    offense_rows: list[dict[str, Any]] = []
    for game in games.itertuples(index=False):
        for team, opponent, side, points, opp_fbs in (
            (
                game.home_team,
                game.away_team,
                "home",
                game.home_points,
                bool(game.away_fbs),
            ),
            (
                game.away_team,
                game.home_team,
                "away",
                game.away_points,
                bool(game.home_fbs),
            ),
        ):
            key = (int(game.season), int(game.game_id), team)
            first_row = len(offense_rows)
            play_complete, possession_complete, scoring_complete = coverage_by.get(
                key, (False, False, False)
            )
            meta = {
                "season": int(game.season),
                "week": int(game.week),
                "game_id": int(game.game_id),
                "team": team,
                "opponent": opponent,
                "season_type": game.season_type,
                "role": "offense",
                "side": side,
                "opponent_fbs": opp_fbs,
                "kickoff_utc": game.kickoff_utc,
            }
            kw = {"versions": versions, "timing": timing_class}
            p = plays_by.get(key, plays.iloc[0:0])
            d = drives_by.get(key, drives.iloc[0:0])
            n_plays, n_drives = len(p), len(d)
            ledger_rows = points_by.get(key, admitted.iloc[0:0])
            held = key in unresolved
            q = ledger_rows[
                ledger_rows["scoring_category"] == "eligible_regulation_offense"
            ]["score_increment"].sum()
            non = ledger_rows[
                ledger_rows["scoring_category"] == "regulation_non_offense"
            ]["score_increment"].sum()
            opp_ids = set(d.loc[d["scoring_opportunity"].eq(True), "possession_id"])
            q_on_o = ledger_rows[
                (ledger_rows["scoring_category"] == "eligible_regulation_offense")
                & ledger_rows["associated_possession_id"].isin(opp_ids)
            ]["score_increment"].sum()
            hold = {
                "status": "missing",
                "reason": "unresolved_scoring_stream",
                "flags": ["unresolved_scoring_stream"],
            }

            offense_rows.append(
                _count_row(meta, "eligible_possessions", n_drives, **kw)
            )
            if held:
                offense_rows.append(
                    _row(
                        meta,
                        "offensive_possession_points",
                        num=None,
                        den=1.0,
                        eligible=None,
                        observed=None,
                        status="missing",
                        reason=hold["reason"],
                        flags=hold["flags"],
                        **kw,
                    )
                )
                offense_rows.append(
                    _row(
                        meta,
                        "ppp",
                        num=None,
                        den=float(n_drives),
                        eligible=n_drives,
                        observed=None,
                        status="missing",
                        reason=hold["reason"],
                        flags=hold["flags"],
                        **kw,
                    )
                )
                offense_rows.append(
                    _row(
                        meta,
                        "non_offense_points",
                        num=None,
                        den=1.0,
                        eligible=None,
                        observed=None,
                        status="missing",
                        reason=hold["reason"],
                        flags=hold["flags"],
                        **kw,
                    )
                )
                offense_rows.append(
                    _row(
                        meta,
                        "pts_per_scoring_opp",
                        num=None,
                        den=float(len(opp_ids)),
                        eligible=len(opp_ids),
                        observed=None,
                        status="missing",
                        reason=hold["reason"],
                        flags=hold["flags"],
                        **kw,
                    )
                )
            else:
                offense_rows.append(
                    _row(
                        meta,
                        "offensive_possession_points",
                        num=float(q),
                        den=1.0,
                        eligible=n_drives,
                        observed=n_drives,
                        **kw,
                    )
                )
                offense_rows.append(
                    _ratio_row(
                        meta,
                        "ppp",
                        float(q),
                        float(n_drives),
                        eligible=n_drives,
                        observed=n_drives,
                        **kw,
                    )
                )
                offense_rows.append(
                    _row(
                        meta,
                        "non_offense_points",
                        num=float(non),
                        den=1.0,
                        eligible=None,
                        observed=None,
                        **kw,
                    )
                )
                offense_rows.append(
                    _ratio_row(
                        meta,
                        "pts_per_scoring_opp",
                        float(q_on_o),
                        float(len(opp_ids)),
                        eligible=len(opp_ids),
                        observed=len(opp_ids),
                        **kw,
                    )
                )
            offense_rows.append(
                _count_row(meta, "eligible_scrimmage_plays", n_plays, **kw)
            )
            offense_rows.append(
                _ratio_row(
                    meta,
                    "plays_per_possession",
                    float(n_plays),
                    float(n_drives),
                    eligible=n_drives,
                    observed=n_drives,
                    **kw,
                )
            )

            flags: list[str] = []
            dropback = (
                pd.to_numeric(p["dropback"], errors="coerce").eq(1)
                if "dropback" in p
                else pd.Series(False, index=p.index)
            )
            rush = (
                pd.to_numeric(p["rush_attempt"], errors="coerce").eq(1)
                if "rush_attempt" in p
                else pd.Series(False, index=p.index)
            )
            down = pd.to_numeric(p["down"], errors="coerce")
            populations = {
                "eligible_epa": (p, 1),
                "epa_pass": (p[dropback], int(dropback.sum())),
                "epa_rush": (p[rush & ~dropback], int((rush & ~dropback).sum())),
                "early_down_epa": (p[down.isin([1, 2])], int(down.isin([1, 2]).sum())),
            }
            epa_total = _ppa_metric(meta, "eligible_epa", p, 1, flags=flags, **kw)
            offense_rows.append(epa_total)
            offense_rows.append(
                _ratio_row(
                    meta,
                    "epa_per_possession",
                    None
                    if epa_total["coverage_status"] == "missing"
                    else epa_total["numerator"],
                    float(n_drives),
                    eligible=n_drives,
                    observed=None
                    if epa_total["coverage_status"] == "missing"
                    else n_drives,
                    status=epa_total["coverage_status"],
                    reason=epa_total["missing_reason"],
                    flags=["ppa_incomplete"]
                    if epa_total["coverage_status"] == "missing"
                    else [],
                    **kw,
                )
            )
            for metric in ("ppa_per_play", "epa_per_play"):
                offense_rows.append(
                    _ppa_metric(meta, metric, p, n_plays, flags=flags, **kw)
                )
            for metric in ("epa_pass", "epa_rush", "early_down_epa"):
                subset, denominator = populations[metric]
                offense_rows.append(
                    _ppa_metric(meta, metric, subset, denominator, flags=flags, **kw)
                )

            def ratio(metric, flag, available, population=None):
                population = (
                    pd.Series(True, index=p.index) if population is None else population
                )
                complete = bool(available[population].all())
                clean = flag[available & population]
                offense_rows.append(
                    _ratio_row(
                        meta,
                        metric,
                        float(clean.sum()) if complete else None,
                        float(population.sum()),
                        eligible=int(population.sum()),
                        observed=int(len(clean)),
                        status="observed" if complete else "missing",
                        reason=None if complete else "required_play_value_missing",
                        flags=[] if complete else ["required_play_value_missing"],
                        **kw,
                    )
                )

            success = pd.to_numeric(p["success"], errors="coerce")
            yards = pd.to_numeric(p["yards_gained"], errors="coerce")
            turnover = pd.to_numeric(p["turnover"], errors="coerce")
            conversion = (
                _conversions(p, down, yards) if len(p) else pd.Series(dtype=float)
            )
            ratio("success_rate", success.eq(1).astype(float), success.notna())
            ratio("explosive_rate", (yards >= 20).astype(float), yards.notna())
            ratio(
                "conv_rate_3rd_4th",
                conversion.astype(float).fillna(0.0),
                conversion.notna(),
                down.isin([3, 4]),
            )
            ratio("turnover_rate", turnover.eq(1).astype(float), turnover.notna())
            start = pd.to_numeric(d["start_yards_to_goal"], errors="coerce")
            offense_rows.append(
                _ratio_row(
                    meta,
                    "scoring_opp_rate",
                    float(len(opp_ids)),
                    float(n_drives),
                    eligible=n_drives,
                    observed=n_drives,
                    **kw,
                )
            )
            offense_rows.append(
                _ratio_row(
                    meta,
                    "avg_start_field_pos",
                    float((100 - start).sum()),
                    float(start.notna().sum()),
                    eligible=n_drives,
                    observed=int(start.notna().sum()),
                    **kw,
                )
            )
            if _num(points) is None:
                offense_rows.append(
                    _row(
                        meta,
                        "points_scored",
                        num=None,
                        den=1.0,
                        eligible=1,
                        observed=0,
                        status="missing",
                        reason="no_certified_final",
                        flags=["no_certified_final"],
                        **kw,
                    )
                )
            else:
                offense_rows.append(_count_row(meta, "points_scored", points, **kw))

            for row in offense_rows[first_row:]:
                metric = row["metric"]
                reason = None
                unknown_denominator = False
                if metric != "points_scored" and not play_complete:
                    reason, unknown_denominator = "source_plays_incomplete", True
                elif (
                    metric
                    in {
                        "eligible_possessions",
                        "ppp",
                        "plays_per_possession",
                        "epa_per_possession",
                        "scoring_opp_rate",
                        "pts_per_scoring_opp",
                        "avg_start_field_pos",
                    }
                    and not possession_complete
                ):
                    reason, unknown_denominator = "source_possessions_incomplete", True
                elif metric in POINT_METRICS and not scoring_complete:
                    reason = "scoring_coverage_unverified"
                elif (
                    metric in {"scoring_opp_rate", "pts_per_scoring_opp"}
                    and d.scoring_opportunity.isna().any()
                ):
                    reason = "scoring_opportunity_unknown"
                    unknown_denominator = metric == "pts_per_scoring_opp"
                elif metric == "avg_start_field_pos" and start.isna().any():
                    reason = "start_field_position_unknown"
                    row["denominator"] = float(n_drives)
                elif metric in {"epa_pass", "epa_rush"} and (
                    p.dropback.isna().any()
                    or (metric == "epa_rush" and p.rush_attempt.isna().any())
                ):
                    reason, unknown_denominator = "play_classification_unknown", True
                elif (
                    metric in {"early_down_epa", "conv_rate_3rd_4th"}
                    and down.isna().any()
                ):
                    reason, unknown_denominator = "down_unknown", True
                if reason:
                    row.update(
                        numerator=None,
                        value=None,
                        coverage_status="missing",
                        missing_reason=reason,
                        quality_flags=canonical_json_text([reason]),
                    )
                    if unknown_denominator:
                        row["denominator"] = (
                            1.0
                            if reg.BY_NAME[metric].kind in {"sum", "count"}
                            else None
                        )
                        row["eligible_count"] = None
                        row["observed_count"] = None
    offense = pd.DataFrame(offense_rows)
    # Defense rows mirror the opponent's offensive measurement and provenance.
    defense = offense.copy()
    defense["role"] = "defense"
    defense["team"], defense["opponent"] = (
        offense["opponent"].values,
        offense["team"].values,
    )
    defense["side"] = np.where(offense["side"] == "home", "away", "home")
    fbs = {
        (int(r.season), int(r.game_id), r.home_team): bool(r.home_fbs)
        for r in games.itertuples()
    }
    fbs |= {
        (int(r.season), int(r.game_id), r.away_team): bool(r.away_fbs)
        for r in games.itertuples()
    }
    defense["opponent_fbs"] = [
        fbs[(int(s), int(g), t)]
        for s, g, t in zip(defense["season"], defense["game_id"], defense["opponent"])
    ]
    return pd.concat([offense, defense], ignore_index=True)


def aggregate_through_week(metrics: pd.DataFrame, *, as_of_week: int) -> pd.DataFrame:
    """Season aggregate from game rows: ratios use summed numerators and denominators.

    A game with a missing numerator withholds the aggregate (the coverage and the reason are
    kept); an independent metric is unaffected by another metric's missing games.
    """
    rows = []
    included = metrics[metrics["week"] < as_of_week]
    for (season, team, role, metric), group in included.groupby(
        ["season", "team", "role", "metric"]
    ):
        definition = reg.BY_NAME[metric]
        missing = group[group["coverage_status"] == "missing"]
        status, reason = (
            ("missing", "ppa_incomplete" if definition.requires_ppa else "withheld")
            if len(missing)
            else ("observed", None)
        )
        if len(missing):
            reasons = sorted({r for r in missing["missing_reason"].dropna()})
            reason = reasons[0] if reasons else reason
        num, den = (
            group["numerator"].sum(min_count=1),
            group["denominator"].sum(min_count=1),
        )
        ratio = definition.kind == "ratio"
        value = None
        if status == "observed" and not pd.isna(num):
            value = (
                float(num) if not ratio else (float(num) / float(den) if den else None)
            )
        rows.append(
            {
                "season": int(season),
                "team": team,
                "role": role,
                "metric": metric,
                "games": int(len(group)),
                "games_missing": int(len(missing)),
                "numerator": None if status == "missing" else _num(num),
                "denominator": _num(den),
                "value": value,
                "coverage_status": status,
                "missing_reason": reason,
                "as_of_week": as_of_week,
            }
        )
    return pd.DataFrame(rows)
