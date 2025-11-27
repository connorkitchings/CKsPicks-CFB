"""
Generates a summary report from the walk-forward validation results.
"""

import glob
import sys
from pathlib import Path

import hydra
import numpy as np
import pandas as pd
from omegaconf import DictConfig

sys.path.append(str(Path(__file__).resolve().parents[2]))
# noqa: E402

def analyze_betting_performance(
    preds_df: pd.DataFrame, games_df: pd.DataFrame, betting_df: pd.DataFrame
):
    """
    Analyzes betting performance and returns a dictionary of results.
    """
    # Merge Games and Betting
    betting_agg = (
        betting_df.groupby("game_id")[["spread", "over_under"]].mean().reset_index()
    )
    games_betting = games_df.merge(
        betting_agg, left_on="id", right_on="game_id", how="left"
    )

    # Merge with Predictions
    merged = preds_df.merge(
        games_betting, on="id", how="inner", suffixes=("", "_actual_data")
    )
    print(f"Merged shape: {merged.shape}")

    # Calculate outcomes
    merged["score_diff"] = merged["home_points"] - merged["away_points"]
    merged["total_score"] = merged["home_points"] + merged["away_points"]

    results = {"spread": [], "total": []}
    thresholds = [0.0, 2.5, 5.0, 7.5]

    for th in thresholds:
        # Spread
        valid_spreads = merged.dropna(
            subset=["spread", "spread_pred_points_for_ensemble", "score_diff"]
        )
        valid_spreads["pred_cover_margin"] = (
            valid_spreads["spread_pred_points_for_ensemble"] + valid_spreads["spread"]
        )
        bets = valid_spreads[np.abs(valid_spreads["pred_cover_margin"]) > th].copy()

        if not bets.empty:
            bets["bet_side"] = np.where(bets["pred_cover_margin"] > 0, "Home", "Away")
            bets["actual_cover_margin"] = bets["score_diff"] + bets["spread"]
            conditions = [
                (bets["bet_side"] == "Home") & (bets["actual_cover_margin"] > 0),
                (bets["bet_side"] == "Away") & (bets["actual_cover_margin"] < 0),
                (bets["actual_cover_margin"] == 0),
            ]
            choices = [1, 1, 0]  # Win, Win, Push
            bets["result"] = np.select(conditions, choices, default=-1)
            decisive_bets = bets[bets["result"] != 0]
            wins = len(decisive_bets[decisive_bets["result"] == 1])
            losses = len(decisive_bets[decisive_bets["result"] == -1])
            total_bets = wins + losses
            if total_bets > 0:
                win_rate = wins / total_bets
                units = (wins * 0.909) - (losses * 1.0)
                roi = (units / total_bets) * 100 if total_bets > 0 else 0
                results["spread"].append(
                    {
                        "threshold": th,
                        "wins": wins,
                        "losses": losses,
                        "pushes": len(bets) - total_bets,
                        "win_rate": win_rate,
                        "units": units,
                        "roi": roi,
                        "volume": len(bets),
                    }
                )

        # Total
        valid_totals = merged.dropna(
            subset=["over_under", "total_pred_points_for_ensemble", "total_score"]
        )
        valid_totals["total_edge"] = (
            valid_totals["total_pred_points_for_ensemble"] - valid_totals["over_under"]
        )
        bets = valid_totals[np.abs(valid_totals["total_edge"]) > th].copy()

        if not bets.empty:
            bets["bet_side"] = np.where(bets["total_edge"] > 0, "Over", "Under")
            bets["total_diff"] = bets["total_score"] - bets["over_under"]
            conditions = [
                (bets["bet_side"] == "Over") & (bets["total_diff"] > 0),
                (bets["bet_side"] == "Under") & (bets["total_diff"] < 0),
                (bets["total_diff"] == 0),
            ]
            choices = [1, 1, 0]
            bets["result"] = np.select(conditions, choices, default=-1)
            decisive_bets = bets[bets["result"] != 0]
            wins = len(decisive_bets[decisive_bets["result"] == 1])
            losses = len(decisive_bets[decisive_bets["result"] == -1])
            total_bets = wins + losses
            if total_bets > 0:
                win_rate = wins / total_bets
                units = (wins * 0.909) - (losses * 1.0)
                roi = (units / total_bets) * 100 if total_bets > 0 else 0
                results["total"].append(
                    {
                        "threshold": th,
                        "wins": wins,
                        "losses": losses,
                        "pushes": len(bets) - total_bets,
                        "win_rate": win_rate,
                        "units": units,
                        "roi": roi,
                        "volume": len(bets),
                    }
                )
    return results


def generate_markdown_report(results: dict, years: list) -> str:
    """Generates a markdown report from the analysis results."""
    report = f"""# Walk-Forward Validation Report ({min(years)}-{max(years)})

"""

    for bet_type in ["spread", "total"]:
        report += f"""## {bet_type.capitalize()} Betting Performance

"""
        if not results[bet_type]:
            report += """No bets placed.

"""
            continue
        df = pd.DataFrame(results[bet_type])
        df["win_rate"] = df["win_rate"].map("{:.1%}".format)
        df["units"] = df["units"].map("{:.2f}".format)
        df["roi"] = df["roi"].map("{:.2f}%".format)
        df.rename(
            columns={
                "threshold": "Edge Threshold",
                "wins": "Wins",
                "losses": "Losses",
                "pushes": "Pushes",
                "win_rate": "Win Rate",
                "units": "Units",
                "roi": "ROI",
                "volume": "Volume",
            },
            inplace=True,
        )
        report += df.to_markdown(index=False)
        report += "\n\n"

    return report


@hydra.main(config_path="../../conf", config_name="config")
def main(cfg: DictConfig):
    """
    Main function to load data, run analysis, and generate report.
    """
    years = cfg.walk_forward.years
    data_dir = cfg.paths.data_dir
    artifacts_dir = cfg.paths.artifacts_dir

    # Load Predictions
    pred_files = []
    for year in years:
        path = (
            Path(artifacts_dir)
            / "validation"
            / "walk_forward"
            / f"{year}_predictions.csv"
        )
        if path.exists():
            pred_files.append(pd.read_csv(path))
    if not pred_files:
        print("No prediction files found. Exiting.")
        return
    preds_df = pd.concat(pred_files, ignore_index=True)

    # Load Games and Betting Lines
    games_list = []
    betting_list = []
    for year in years:
        games_path = Path(data_dir) / "raw" / "games" / f"year={year}"
        betting_path = Path(data_dir) / "raw" / "betting_lines" / f"year={year}"
        if games_path.exists():
            games_files = glob.glob(str(games_path / "**" / "data.csv"), recursive=True)
            games_list.extend([pd.read_csv(f) for f in games_files])
        if betting_path.exists():
            betting_files = glob.glob(
                str(betting_path / "**" / "data.csv"), recursive=True
            )
            betting_list.extend([pd.read_csv(f) for f in betting_files])

    if not games_list or not betting_list:
        print("No games or betting lines found. Exiting.")
        return

    games_df = pd.concat(games_list, ignore_index=True)
    betting_df = pd.concat(betting_list, ignore_index=True)

    # Run analysis
    results = analyze_betting_performance(preds_df, games_df, betting_df)

    # Generate and save report
    report = generate_markdown_report(results, years)
    report_path = Path(artifacts_dir) / "reports" / "walk_forward_summary.md"
    report_path.parent.mkdir(exist_ok=True, parents=True)
    with open(report_path, "w") as f:
        f.write(report)

    print(f"Report saved to {report_path}")
    print(report)


if __name__ == "__main__":
    main()
