import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))
# noqa: E402
from scripts.run_experiment import compute_ats_metrics  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize edge buckets and hit rates from a predictions CSV."
    )
    parser.add_argument(
        "predictions_path",
        type=Path,
        help="Path to predictions CSV (e.g., artifacts/predictions/<exp>/<run>/2024_predictions.csv)",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Override data root (defaults to CFB_MODEL_DATA_ROOT env var).",
    )
    parser.add_argument(
        "--target-type",
        choices=["spread", "total"],
        default="spread",
        help="Which betting target to evaluate.",
    )
    parser.add_argument(
        "--edge-threshold",
        type=float,
        default=5.0,
        help="Minimum edge (points) to place a bet.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Where to write the summary JSON/MD (defaults to predictions_path parent).",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    pred_path: Path = args.predictions_path
    df = pd.read_csv(pred_path)

    required_cols = {"id", "season", "week", "prediction", "actual"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Predictions file missing required columns: {missing}")

    meta_df = df[["id", "season", "week"]].copy()
    preds = df["prediction"].values
    actuals = df["actual"].values

    metrics = compute_ats_metrics(
        meta_df,
        preds,
        actuals,
        str(args.data_root) if args.data_root else None,
        target_type=args.target_type,
        edge_threshold=args.edge_threshold,
    )

    out_dir = args.output_dir or pred_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    base_name = pred_path.stem.replace("_predictions", "")
    json_path = out_dir / f"{base_name}_edge_metrics.json"
    md_path = out_dir / f"{base_name}_edge_metrics.md"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    lines = [
        f"# Edge Metrics for {pred_path.name}",
        "",
        f"- Target: {args.target_type}",
        f"- Edge threshold: {args.edge_threshold}",
        f"- Overall hit rate: {metrics['overall_hit_rate']:.1%}",
        f"- Bets: {metrics['num_bets']} (W {metrics['num_wins']} / L {metrics['num_losses']} / P {metrics['num_pushes']})",
        "",
        "## Edge buckets",
    ]
    for bucket, stats in metrics.get("edge_buckets", {}).items():
        lines.append(
            f"- {bucket}: hit {stats['hit_rate']:.1%} "
            f"({stats['wins']}-{stats['losses']}-{stats['pushes']}, n={stats['count']})"
        )

    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote edge summary to {json_path} and {md_path}")


if __name__ == "__main__":
    main()
