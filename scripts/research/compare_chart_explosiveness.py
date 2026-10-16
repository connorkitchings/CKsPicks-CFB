#!/usr/bin/env python3
"""Compare two descriptive explosiveness measures from a pinned Preview revision.

Read-only R2 inputs; local ignored outputs only. No model selection or serving
changes. The shared chart builder determines game eligibility; the shared
scrimmage filter determines play eligibility. Every metric keeps its own finite
observation denominator. Longest-gain sensitivity removes exactly one play per
team/side/window (including an unsuccessful longest play, if applicable).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from cks_picks_cfb.charts.roster import build_team_season_roster
from cks_picks_cfb.charts.team_game_stats import build_team_game_stats
from cks_picks_cfb.data.play_filters import scrimmage_play_mask
from cks_picks_cfb.data.storage import ReadOnlyStorage, get_storage
from cks_picks_cfb.season.inputs import read_ref
from cks_picks_cfb.season.manifest import validate_ref

CANDIDATES = ("explosive_rate", "yards_per_success")


def ratio(numerator: float, denominator: int) -> float | None:
    return float(numerator / denominator) if denominator else None


def median(values: pd.Series) -> float | None:
    observed = values.dropna()
    return float(observed.median()) if len(observed) else None


def finite(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values.where(np.isfinite(values))


def measures(plays: pd.DataFrame) -> dict:
    """Independent exposure: PPA or success missingness never drops valid yards."""
    yards = finite(plays["yards_gained"])
    success = finite(plays["success"])
    ppa = finite(plays["ppa"])
    if "ppa_missing" in plays:
        ppa = ppa.mask(plays["ppa_missing"].eq(True))
    successful_yards = yards[success.eq(1) & yards.notna()]
    yardage_n, success_n, ppa_n = (
        int(yards.count()),
        int(success.count()),
        int(ppa.count()),
    )
    explosive_n = int(yards.ge(20).sum())
    successful_yards_n = int(successful_yards.count())
    return {
        "plays": len(plays),
        "yardage_n": yardage_n,
        "explosive_n": explosive_n,
        "explosive_rate": explosive_n / yardage_n if yardage_n else None,
        "successful_yards_n": successful_yards_n,
        "successful_yards_sum": float(successful_yards.sum()),
        "yards_per_success": float(successful_yards.mean())
        if successful_yards_n
        else None,
        "success_n": success_n,
        "success_sum": float(success.sum()),
        "success_rate": float(success.mean()) if success_n else None,
        "ppa_n": ppa_n,
        "ppa_sum": float(ppa.sum()),
        "ppa_per_play": float(ppa.mean()) if ppa_n else None,
    }


def eligible_plays(
    frames: dict, *, season: int, active_week: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    roster = build_team_season_roster(frames["teams"], season)
    games = build_team_game_stats(
        byplay=frames["byplay"],
        games=frames["schedule"],
        finals=frames["finals"],
        fbs_teams=set(roster.team),
        neutral_game_ids=(),
        season=season,
        active_week=active_week,
    )
    ids = set(games.game_id)
    plays = (
        frames["byplay"]
        .loc[frames["byplay"].season.eq(season) & frames["byplay"].game_id.isin(ids)]
        .copy()
    )
    plays = plays.loc[scrimmage_play_mask(plays)].copy()
    # Use the schedule's week, not a potentially conflicting play-level week.
    weeks = games.drop_duplicates("game_id").set_index("game_id").week
    plays["week"] = plays.game_id.map(weeks)
    participants = games[["game_id", "team", "opponent"]].rename(
        columns={"team": "offense", "opponent": "defense"}
    )
    if len(plays.merge(participants, on=["game_id", "offense", "defense"])) != len(
        plays
    ):
        raise ValueError("eligible play participants differ from schedule")
    return plays.reset_index(drop=True), games, roster


def compare(
    frames: dict, *, season: int, active_week: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    plays, games, roster = eligible_plays(
        frames, season=season, active_week=active_week
    )
    rows, contexts = [], []
    for week in range(2, active_week):
        window = plays[plays.week.le(week)]
        for side, team_column in (("offense", "offense"), ("defense", "defense")):
            groups = dict(tuple(window.groupby(team_column, sort=True)))
            for team in roster.team:
                group = groups.get(team, window.iloc[:0])
                values = measures(group)
                yards = finite(group.yards_gained)
                longest = yards.idxmax() if yards.notna().any() else None
                removed = measures(
                    group.drop(index=longest) if longest is not None else group
                )
                row = {
                    "season": season,
                    "through_week": week,
                    "side": side,
                    "team": team,
                    **values,
                }
                row["games"] = int(
                    games[games.team.eq(team) & games.week.le(week)].game_id.nunique()
                )
                row["longest_gain"] = (
                    float(yards.loc[longest]) if longest is not None else None
                )
                row["longest_game_id"] = (
                    int(group.loc[longest, "game_id"]) if longest is not None else None
                )
                row["longest_week"] = (
                    int(group.loc[longest, "week"]) if longest is not None else None
                )
                row["longest_opponent"] = (
                    str(
                        group.loc[
                            longest, "defense" if side == "offense" else "offense"
                        ]
                    )
                    if longest is not None
                    else None
                )
                row["longest_success"] = (
                    finite(group.success).loc[longest] if longest is not None else None
                )
                for key in (
                    "plays",
                    "yardage_n",
                    "explosive_n",
                    "successful_yards_n",
                    "successful_yards_sum",
                    *CANDIDATES,
                ):
                    row[f"without_longest_{key}"] = removed[key]
                rows.append(row)
    for side in ("offense", "defense"):
        for (team, game_id), group in plays.groupby([side, "game_id"], sort=True):
            game = games[games.team.eq(team) & games.game_id.eq(game_id)].iloc[0]
            contexts.append(
                {
                    "season": season,
                    "side": side,
                    "team": team,
                    "game_id": int(game_id),
                    "week": int(game.week),
                    "opponent": game.opponent,
                    "points_for": int(game.points_for),
                    "points_against": int(game.points_against),
                    **measures(group),
                }
            )
    result = pd.DataFrame(rows)
    for side in ("offense", "defense"):
        mask = result.side.eq(side)
        for metric in CANDIDATES:
            for prefix in ("", "without_longest_"):
                column = prefix + metric
                result.loc[mask, column + "_rank"] = (
                    result[mask]
                    .groupby("through_week")[column]
                    .rank(method="min", ascending=side == "defense")
                )
            result.loc[mask, metric + "_rank_change_without_longest"] = (
                result.loc[mask, "without_longest_" + metric + "_rank"]
                - result.loc[mask, metric + "_rank"]
            )
            ordered = result[mask].sort_values(["team", "through_week"])
            result.loc[ordered.index, metric + "_rank_change_previous_week"] = (
                ordered.groupby("team")[metric + "_rank"].diff()
            )
    result["candidate_rank_difference"] = (
        result.explosive_rate_rank - result.yards_per_success_rank
    )
    return result, pd.DataFrame(contexts), games


def validate_direct(
    frames: dict,
    result: pd.DataFrame,
    contexts: pd.DataFrame,
    *,
    season: int,
    active_week: int,
) -> dict:
    """Independently reconcile output formulas to the pinned eligible play rows."""
    plays, _, _ = eligible_plays(frames, season=season, active_week=active_week)
    checked = 0
    for point in result.itertuples():
        group = plays[
            plays[point.side].eq(point.team) & plays.week.le(point.through_week)
        ]
        yards = pd.to_numeric(group.yards_gained, errors="coerce").to_numpy(dtype=float)
        successes = pd.to_numeric(group.success, errors="coerce").to_numpy(dtype=float)
        valid = np.isfinite(yards)
        successful = valid & (successes == 1)
        direct = {
            "plays": len(group),
            "yardage_n": int(valid.sum()),
            "explosive_n": int(((yards >= 20) & valid).sum()),
            "successful_yards_n": int(successful.sum()),
            "successful_yards_sum": float(yards[successful].sum()),
            "explosive_rate": float((yards[valid] >= 20).mean())
            if valid.any()
            else np.nan,
            "yards_per_success": float(yards[successful].mean())
            if successful.any()
            else np.nan,
        }
        for key, expected in direct.items():
            if not np.isclose(
                getattr(point, key), expected, atol=1e-12, rtol=0, equal_nan=True
            ):
                raise ValueError(
                    f"direct pinned-play formula differs: {point.team}/{point.side}/{point.through_week}/{key}"
                )
            checked += 1
        context = contexts[
            contexts.side.eq(point.side)
            & contexts.team.eq(point.team)
            & contexts.week.le(point.through_week)
        ]
        if int(context.plays.sum()) != point.plays or (
            len(group) and group.week.max() > point.through_week
        ):
            raise ValueError("cumulative window includes later games")
    off = contexts[contexts.side.eq("offense")]
    defense = contexts[contexts.side.eq("defense")].set_index(["game_id", "team"])
    columns = list(measures(plays.iloc[:0]))
    for point in off.itertuples():
        mirror = defense.loc[(point.game_id, point.opponent)]
        for key in columns:
            if not np.isclose(
                getattr(point, key), mirror[key], atol=1e-12, rtol=0, equal_nan=True
            ):
                raise ValueError("offense/defense game observations are not mirrored")
    return {
        "direct_formula_values_checked": checked,
        "mirrored_team_games_checked": len(off),
        "cumulative_windows_checked": len(result),
        "eligible_plays": len(plays),
        "missing_or_nonfinite_yards": int(finite(plays.yards_gained).isna().sum()),
        "missing_or_nonfinite_success": int(finite(plays.success).isna().sum()),
        "missing_or_nonfinite_ppa": int(
            finite(plays.ppa).mask(plays.ppa_missing.eq(True)).isna().sum()
        )
        if "ppa_missing" in plays
        else int(finite(plays.ppa).isna().sum()),
    }


def aggregate(result: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    distributions, relationships = [], []
    for (week, side), group in result.groupby(["through_week", "side"], sort=True):
        for metric in CANDIDATES:
            values = group[metric].dropna()
            sensitivity = (group["without_longest_" + metric] - group[metric]).abs()
            ranks = group[metric + "_rank_change_without_longest"].abs()
            distributions.append(
                {
                    "through_week": int(week),
                    "side": side,
                    "metric": metric,
                    "teams": len(group),
                    "observed": len(values),
                    "null": int(group[metric].isna().sum()),
                    "minimum": values.min(),
                    "p10": values.quantile(0.1),
                    "median": median(values),
                    "p90": values.quantile(0.9),
                    "maximum": values.max(),
                    "team_mean": values.mean(),
                    "pooled": (
                        ratio(group.explosive_n.sum(), int(group.yardage_n.sum()))
                        if metric == "explosive_rate"
                        else ratio(
                            group.successful_yards_sum.sum(),
                            int(group.successful_yards_n.sum()),
                        )
                    ),
                    "mean_absolute_change_without_longest": sensitivity.mean(),
                    "max_absolute_change_without_longest": sensitivity.max(),
                    "median_absolute_rank_change_without_longest": median(ranks),
                    "max_absolute_rank_change_without_longest": ranks.max(),
                    "median_absolute_rank_change_previous_week": median(
                        group[metric + "_rank_change_previous_week"].abs()
                    ),
                    "max_absolute_rank_change_previous_week": group[
                        metric + "_rank_change_previous_week"
                    ]
                    .abs()
                    .max(),
                }
            )
        for left, right in (
            ("explosive_rate", "yards_per_success"),
            *((c, ref) for c in CANDIDATES for ref in ("success_rate", "ppa_per_play")),
        ):
            paired = group[[left, right]].dropna()
            relationships.append(
                {
                    "through_week": int(week),
                    "side": side,
                    "left": left,
                    "right": right,
                    "paired_teams": len(paired),
                    "pearson": paired[left].corr(paired[right]),
                    "spearman": paired[left].corr(paired[right], method="spearman"),
                }
            )
    return pd.DataFrame(distributions), pd.DataFrame(relationships)


def plots(result: pd.DataFrame, output: Path) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    windows = sorted(result.through_week.unique())
    files = []
    for side in ("offense", "defense"):
        figure, axes = plt.subplots(
            len(windows), 2, figsize=(12, 3.2 * len(windows)), squeeze=False
        )
        for row, week in enumerate(windows):
            group = result[result.side.eq(side) & result.through_week.eq(week)]
            for col, metric in enumerate(CANDIDATES):
                ax = axes[row, col]
                scatter = ax.scatter(
                    group.success_rate * 100,
                    group[metric] * (100 if col == 0 else 1),
                    c=group.ppa_per_play,
                    cmap="viridis",
                    s=18,
                    alpha=0.8,
                )
                ax.set(
                    xlabel="Success rate (%)",
                    ylabel="20+ yard play rate (%)"
                    if col == 0
                    else "Yards per successful play",
                    title=f"{side.title()} | Through Week {week}",
                )
                ax.grid(alpha=0.18)
                figure.colorbar(scatter, ax=ax, label="PPA/play")
        figure.suptitle(
            "2026 FBS vs FBS | regulation eligible plays | descriptive reconstruction",
            fontsize=11,
        )
        figure.tight_layout(rect=(0, 0, 1, 0.98))
        name = f"{side}-paired-profiles.png"
        figure.savefig(output / name, dpi=150)
        plt.close(figure)
        files.append(name)
    figure, axes = plt.subplots(
        len(windows), 2, figsize=(12, 3.2 * len(windows)), squeeze=False
    )
    for row, week in enumerate(windows):
        for col, side in enumerate(("offense", "defense")):
            group = result[result.side.eq(side) & result.through_week.eq(week)]
            ax = axes[row, col]
            ax.scatter(
                group.explosive_rate * 100, group.yards_per_success, s=18, alpha=0.75
            )
            for label_index, point in enumerate(
                group.loc[
                    group.candidate_rank_difference.abs().nlargest(2).index
                ].itertuples()
            ):
                ax.annotate(
                    point.team,
                    (point.explosive_rate * 100, point.yards_per_success),
                    fontsize=7,
                    xytext=(4, 8 if label_index == 0 else -12),
                    textcoords="offset points",
                    arrowprops={"arrowstyle": "-", "color": "#777777", "lw": 0.5},
                )
            ax.set(
                xlabel="20+ yard play rate (%)",
                ylabel="Yards per successful play",
                title=f"{side.title()} | Through Week {week}",
            )
            ax.grid(alpha=0.18)
    figure.tight_layout()
    name = "candidate-agreement.png"
    figure.savefig(output / name, dpi=150)
    plt.close(figure)
    files.append(name)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision-manifest", type=Path, required=True)
    parser.add_argument("--active-week", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Optional local credential file; never copied or logged",
    )
    args = parser.parse_args()
    if args.env_file:
        from dotenv import load_dotenv

        load_dotenv(args.env_file, override=False)
    if (
        os.getenv("CFB_STORAGE_BACKEND") != "r2"
        or os.getenv("CFB_ARTIFACT_ENV") != "preview"
    ):
        raise ValueError(
            "requires explicit CFB_STORAGE_BACKEND=r2 and CFB_ARTIFACT_ENV=preview"
        )
    required = [
        f"CFB_R2_PREVIEW_{name}"
        for name in ("BUCKET", "ACCOUNT_ID", "ACCESS_KEY", "SECRET_KEY")
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise ValueError(
            "missing Preview credential configuration: " + ", ".join(missing)
        )
    repository = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    if not output.is_relative_to(
        repository / "artifacts" / "research" / "chart-explosiveness"
    ):
        raise ValueError(
            "output must be inside ignored artifacts/research/chart-explosiveness in this worktree"
        )
    if output.exists():
        raise ValueError("refusing to overwrite existing comparison artifacts")
    raw = args.revision_manifest.read_bytes()
    revision = json.loads(raw)
    if revision.get(
        "schema_version"
    ) != "season_revision_v1" or args.active_week != max(
        map(int, revision["pre_week_cutoffs"])
    ):
        raise ValueError("active week is not declared by revision")
    refs = {
        key: revision["inputs"][key]
        for key in ("schedule", "finals", "byplay", "teams")
    }
    for ref in refs.values():
        validate_ref(ref)
        if not ref["uri"].startswith("lake/silver/"):
            raise ValueError("comparison requires immutable pinned Silver inputs")
    reader = ReadOnlyStorage(get_storage(environment="preview"))
    # read_ref checks SHA-256 before any Parquet interpretation or calculation.
    frames = {
        key: pd.read_parquet(io.BytesIO(read_ref(reader, ref)))
        for key, ref in refs.items()
    }
    result, contexts, games = compare(
        frames, season=int(revision["season"]), active_week=args.active_week
    )
    validation = validate_direct(
        frames,
        result,
        contexts,
        season=int(revision["season"]),
        active_week=args.active_week,
    )
    distributions, relationships = aggregate(result)
    output.mkdir(parents=True)
    datasets = {
        "team-windows": result,
        "team-games": contexts,
        "eligible-games": games,
        "distributions": distributions,
        "relationships": relationships,
    }
    for name, frame in datasets.items():
        frame.to_csv(output / f"{name}.csv", index=False)
    result.to_parquet(output / "team-windows.parquet", index=False)
    images = plots(result, output)
    evidence = {
        "schema_version": "chart_explosiveness_comparison_v1",
        "environment": "preview",
        "backend": "r2",
        "revision_manifest": str(args.revision_manifest),
        "revision_sha256": hashlib.sha256(raw).hexdigest(),
        "inputs": refs,
        "season": int(revision["season"]),
        "active_week": args.active_week,
        "through_weeks": sorted(int(w) for w in result.through_week.unique()),
        "eligible_games": int(games.game_id.nunique()),
        "roster_teams": int(result.team.nunique()),
        "eligible_team_games": len(games),
        "team_windows": len(result),
        "hashes": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(output.iterdir())
            if p.is_file()
        },
        "plots": images,
        "validation": validation,
        "selection": "deferred to owner; descriptive evidence only",
    }
    (output / "evidence.json").write_text(
        json.dumps(evidence, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {
                key: evidence[key]
                for key in (
                    "environment",
                    "backend",
                    "through_weeks",
                    "eligible_games",
                    "roster_teams",
                    "team_windows",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
