#!/usr/bin/env python3
"""Analysis CLI consolidating metrics, hit rates, and threshold sweeps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

import pandas as pd
import typer

app = typer.Typer(help="Analysis utilities for scored bets.")


def _load_scored(path: Path) -> pd.DataFrame:
    if path.is_dir():
        csv_files = sorted(path.glob("*.csv"))
        if not csv_files:
            raise typer.BadParameter(f"No CSV files found under {path}")
        frames = [pd.read_csv(csv) for csv in csv_files]
        return pd.concat(frames, ignore_index=True)
    if path.suffix.lower() == ".csv" and path.is_file():
        return pd.read_csv(path)
    # Allow passing a year directory path (e.g., reports/2024)
    if path.is_file():
        return pd.read_csv(path)
    raise typer.BadParameter(f"Unsupported scored data path: {path}")


@app.command()
def summary(
    scored: Path = typer.Argument(..., help="Path to scored CSV or directory."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Optional path to write the summary JSON."
    ),
) -> None:
    """Aggregate overall hit rate and units for spread and totals."""
    df = _load_scored(scored)
    summary = {}
    for bet_col, result_col in [
        ("Spread Bet", "Spread Bet Result"),
        ("Total Bet", "Total Bet Result"),
    ]:
        if bet_col not in df or result_col not in df:
            continue
        placed = df[df[bet_col].str.lower().isin(["home", "away", "over", "under"])]
        wins = (placed[result_col].str.lower() == "win").sum()
        losses = (placed[result_col].str.lower() == "loss").sum()
        summary[bet_col] = {
            "wins": int(wins),
            "losses": int(losses),
            "hit_rate": wins / max(1, (wins + losses)),
            "total_bets": int(wins + losses),
        }
    typer.echo(json.dumps(summary, indent=2, default=float))
    if output:
        output.write_text(json.dumps(summary, indent=2, default=float))


def _segment(df: pd.DataFrame, column: str) -> dict:
    grouped = (
        df[df[column].notna()]
        .groupby(column)[["Spread Bet Result", "Total Bet Result"]]
        .agg(
            spread_wins=("Spread Bet Result", lambda s: (s.str.lower() == "win").sum()),
            spread_losses=(
                "Spread Bet Result",
                lambda s: (s.str.lower() == "loss").sum(),
            ),
            total_wins=("Total Bet Result", lambda s: (s.str.lower() == "win").sum()),
            total_losses=(
                "Total Bet Result",
                lambda s: (s.str.lower() == "loss").sum(),
            ),
        )
    )
    grouped["spread_hit_rate"] = grouped["spread_wins"] / grouped[
        ["spread_wins", "spread_losses"]
    ].sum(axis=1).replace(0, pd.NA)
    grouped["total_hit_rate"] = grouped["total_wins"] / grouped[
        ["total_wins", "total_losses"]
    ].sum(axis=1).replace(0, pd.NA)
    return grouped.fillna(0).to_dict(orient="index")


@app.command()
def segments(
    scored: Path = typer.Argument(..., help="Path to scored CSV or directory."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Optional JSON output path."
    ),
) -> None:
    """Analyze hit rates by week and favorite/underdog segments."""
    df = _load_scored(scored)
    if "Week" not in df.columns:
        raise typer.BadParameter("Scored data must contain a 'Week' column.")
    favorite_flag = df.get("Favorite Bet")
    if favorite_flag is None and "Favorite" in df.columns:
        favorite_flag = df["Favorite"]
    if favorite_flag is not None:
        df["favorite_flag"] = favorite_flag
    summary = {
        "by_week": _segment(df, "Week"),
    }
    if "favorite_flag" in df:
        summary["favorite_vs_underdog"] = _segment(df, "favorite_flag")
    typer.echo(json.dumps(summary, indent=2, default=float))
    if output:
        output.write_text(json.dumps(summary, indent=2, default=float))


@app.command()
def threshold(
    scored: Path = typer.Argument(..., help="Path to scored CSV or directory."),
    thresholds: List[float] = typer.Option(
        [4.0, 5.0, 6.0], "--threshold", "-t", help="Edge thresholds to evaluate."
    ),
    bet_type: str = typer.Option(
        "spread", "--bet-type", "-b", help="Bet type to evaluate (spread or total)."
    ),
) -> None:
    """Sweep edge thresholds using scored season data."""
    bet_type = bet_type.lower()
    if bet_type not in {"spread", "total"}:
        raise typer.BadParameter("bet_type must be 'spread' or 'total'.")
    df = _load_scored(scored)
    edge_col = "edge_spread" if bet_type == "spread" else "edge_total"
    result_col = "Spread Bet Result" if bet_type == "spread" else "Total Bet Result"
    bet_col = "Spread Bet" if bet_type == "spread" else "Total Bet"
    if edge_col not in df or result_col not in df:
        raise typer.BadParameter(f"Columns {edge_col} and {result_col} required.")
    results = []
    for thresh in thresholds:
        subset = df[
            (df[bet_col].str.lower().isin(["home", "away", "over", "under"]))
            & (df[edge_col] >= thresh)
        ]
        wins = (subset[result_col].str.lower() == "win").sum()
        losses = (subset[result_col].str.lower() == "loss").sum()
        results.append(
            {
                "threshold": thresh,
                "wins": int(wins),
                "losses": int(losses),
                "hit_rate": wins / max(1, wins + losses),
                "bets": int(wins + losses),
            }
        )
    typer.echo(json.dumps(results, indent=2, default=float))


def _normalize_week_column(df: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    if "Week" in df.columns:
        return df, "Week"
    if "week" in df.columns:
        return df, "week"
    raise typer.BadParameter("Scored data must contain a week column (Week or week).")


def _result_to_bool(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map({"win": 1, "loss": 0, "push": 0})
        .fillna(0)
        .astype(int)
    )


def _summaries(
    df: pd.DataFrame, result_col: str, week_col: str
) -> Tuple[pd.DataFrame, dict]:
    placed = df[df[result_col].notna()].copy()
    if placed[result_col].dtype.kind in {"i", "u", "f"}:
        placed["win"] = (
            pd.to_numeric(placed[result_col], errors="coerce").fillna(0).clip(0, 1)
        )
    else:
        placed["win"] = _result_to_bool(placed[result_col])
    weekly = (
        placed.groupby(week_col)["win"]
        .agg(wins="sum", bets="count")
        .assign(hit_rate=lambda x: x["wins"] / x["bets"])
        .reset_index()
        .sort_values(week_col)
    )
    overall = {
        "wins": int(placed["win"].sum()),
        "bets": int(len(placed)),
        "hit_rate": float(placed["win"].mean()) if len(placed) else float("nan"),
    }
    return weekly, overall


@app.command()
def split(
    scored: Path = typer.Argument(..., help="Path to scored CSV or directory."),
    output_dir: Path = typer.Option(
        None, "--output-dir", "-o", help="Directory to write split CSVs and summaries."
    ),
    prefix: str = typer.Option(
        "season",
        "--prefix",
        help="Base name for generated files (defaults to 'season').",
    ),
) -> None:
    """Split scored bets into spread/total CSVs and emit weekly/overall summaries."""
    df = _load_scored(scored)
    df, week_col = _normalize_week_column(df)

    spread_mask = (
        df.get("Spread Bet") if "Spread Bet" in df.columns else df.get("bet_spread")
    )
    total_mask = (
        df.get("Total Bet") if "Total Bet" in df.columns else df.get("bet_total")
    )
    if spread_mask is None or total_mask is None:
        raise typer.BadParameter(
            "Scored data must include spread and total bet columns."
        )

    spread_rows = df[spread_mask.astype(str).str.lower().isin(["home", "away"])].copy()
    total_rows = df[total_mask.astype(str).str.lower().isin(["over", "under"])].copy()

    spread_result_col = (
        "Spread Bet Result"
        if "Spread Bet Result" in df.columns
        else "pick_win"
        if "pick_win" in df.columns
        else None
    )
    total_result_col = (
        "Total Bet Result"
        if "Total Bet Result" in df.columns
        else "total_pick_win"
        if "total_pick_win" in df.columns
        else None
    )
    if spread_result_col is None or total_result_col is None:
        raise typer.BadParameter(
            "Scored data missing result columns for spread/total bets."
        )

    spread_weekly, spread_overall = _summaries(spread_rows, spread_result_col, week_col)
    total_weekly, total_overall = _summaries(total_rows, total_result_col, week_col)

    output = {
        "spread_weekly": spread_weekly.to_dict(orient="records"),
        "spread_overall": spread_overall,
        "total_weekly": total_weekly.to_dict(orient="records"),
        "total_overall": total_overall,
    }
    typer.echo(json.dumps(output, indent=2, default=float))

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        spread_rows.to_csv(output_dir / f"{prefix}_spread_bets.csv", index=False)
        total_rows.to_csv(output_dir / f"{prefix}_total_bets.csv", index=False)
        spread_weekly.to_csv(
            output_dir / f"{prefix}_spread_weekly_summary.csv", index=False
        )
        total_weekly.to_csv(
            output_dir / f"{prefix}_total_weekly_summary.csv", index=False
        )
        (output_dir / f"{prefix}_summary.json").write_text(
            json.dumps(output, indent=2, default=float)
        )


@app.command()
def confidence(
    scored: Path = typer.Argument(..., help="Path to scored CSV or directory."),
    bet_type: str = typer.Option("spread", "--bet-type", "-b", help="spread or total"),
    edge_threshold: float = typer.Option(
        6.0, "--edge-threshold", help="Minimum edge to include in the sweep."
    ),
    std_dev_thresholds: List[float] = typer.Option(
        [1.0, 1.5, 2.0, 2.5, 3.0],
        "--std-dev",
        help="Standard deviation thresholds to evaluate.",
    ),
) -> None:
    """Sweep prediction standard deviation thresholds while holding edge fixed."""
    bet_type = bet_type.lower()
    if bet_type not in {"spread", "total"}:
        raise typer.BadParameter("bet_type must be 'spread' or 'total'.")
    cfg = {
        "spread": (
            "edge_spread",
            "predicted_spread_std_dev",
            "Spread Bet Result",
            "Spread Bet",
        ),
        "total": (
            "edge_total",
            "predicted_total_std_dev",
            "Total Bet Result",
            "Total Bet",
        ),
    }[bet_type]
    df = _load_scored(scored)
    if cfg[0] not in df or cfg[1] not in df or cfg[2] not in df:
        raise typer.BadParameter("Required columns missing from scored data.")
    subset = df[
        (df[cfg[3]].astype(str).str.lower().isin(["home", "away", "over", "under"]))
        & (pd.to_numeric(df[cfg[0]], errors="coerce") >= edge_threshold)
    ].copy()
    subset[cfg[1]] = pd.to_numeric(subset[cfg[1]], errors="coerce")
    subset["win"] = _result_to_bool(subset[cfg[2]])
    rows = []
    for threshold in std_dev_thresholds:
        mask = subset[cfg[1]] <= threshold
        picks = int(mask.sum())
        wins = int(subset.loc[mask, "win"].sum())
        rows.append(
            {
                "threshold": threshold,
                "picks": picks,
                "wins": wins,
                "hit_rate": wins / picks if picks else float("nan"),
            }
        )
    typer.echo(json.dumps(rows, indent=2, default=float))


if __name__ == "__main__":
    app()
