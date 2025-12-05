"""
Create visualizations for adjustment iteration experiment results.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# Load results
results_df = pd.read_csv(
    "artifacts/reports/metrics/adjustment_iteration_summary_v2.csv"
)

# Create figure with subplots
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle(
    "Adjustment Iteration Depth Comparison (Points-For Models, 2024 Holdout)",
    fontsize=16,
    fontweight="bold",
)

# 1. Spread RMSE vs Depth
ax1 = axes[0, 0]
ax1.plot(
    results_df["depth"],
    results_df["spread_rmse"],
    marker="o",
    linewidth=2,
    markersize=8,
    color="#2E86AB",
)
ax1.set_xlabel("Opponent-Adjustment Iteration Depth", fontsize=11)
ax1.set_ylabel("Spread RMSE", fontsize=11)
ax1.set_title("Spread Prediction Error vs. Depth", fontsize=12, fontweight="bold")
ax1.grid(True, alpha=0.3)
ax1.set_xticks(results_df["depth"])
# Annotate min
min_idx = results_df["spread_rmse"].idxmin()
ax1.annotate(
    f"Best: {results_df.loc[min_idx, 'spread_rmse']:.2f}",
    xy=(results_df.loc[min_idx, "depth"], results_df.loc[min_idx, "spread_rmse"]),
    xytext=(10, -20),
    textcoords="offset points",
    bbox=dict(boxstyle="round,pad=0.5", fc="yellow", alpha=0.7),
    arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0"),
)

# 2. Total RMSE vs Depth
ax2 = axes[0, 1]
ax2.plot(
    results_df["depth"],
    results_df["total_rmse"],
    marker="s",
    linewidth=2,
    markersize=8,
    color="#A23B72",
)
ax2.set_xlabel("Opponent-Adjustment Iteration Depth", fontsize=11)
ax2.set_ylabel("Total RMSE", fontsize=11)
ax2.set_title("Total Prediction Error vs. Depth", fontsize=12, fontweight="bold")
ax2.grid(True, alpha=0.3)
ax2.set_xticks(results_df["depth"])
# Annotate min
min_idx = results_df["total_rmse"].idxmin()
ax2.annotate(
    f"Best: {results_df.loc[min_idx, 'total_rmse']:.2f}",
    xy=(results_df.loc[min_idx, "depth"], results_df.loc[min_idx, "total_rmse"]),
    xytext=(10, -20),
    textcoords="offset points",
    bbox=dict(boxstyle="round,pad=0.5", fc="yellow", alpha=0.7),
    arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0"),
)

# 3. Calibration Bias vs Depth
ax3 = axes[1, 0]
ax3.plot(
    results_df["depth"],
    results_df["spread_bias"],
    marker="o",
    linewidth=2,
    markersize=8,
    label="Spread Bias",
    color="#2E86AB",
)
ax3.plot(
    results_df["depth"],
    results_df["total_bias"],
    marker="s",
    linewidth=2,
    markersize=8,
    label="Total Bias",
    color="#A23B72",
)
ax3.axhline(y=0, color="black", linestyle="--", alpha=0.5)
ax3.set_xlabel("Opponent-Adjustment Iteration Depth", fontsize=11)
ax3.set_ylabel("Prediction Bias (points)", fontsize=11)
ax3.set_title("Calibration Bias vs. Depth", fontsize=12, fontweight="bold")
ax3.legend(loc="best")
ax3.grid(True, alpha=0.3)
ax3.set_xticks(results_df["depth"])

# 4. Combined comparison table (text)
ax4 = axes[1, 1]
ax4.axis("off")
table_data = []
table_data.append(["Depth", "Spread", "Total", "Features"])
for _, row in results_df.iterrows():
    depth_str = f"{int(row['depth'])}"
    spread_str = f"{row['spread_rmse']:.2f}"
    total_str = f"{row['total_rmse']:.2f}"
    feat_str = f"{int(row['n_features'])}"

    # Bold best values
    if row["spread_rmse"] == results_df["spread_rmse"].min():
        spread_str = f"**{spread_str}**"
    if row["total_rmse"] == results_df["total_rmse"].min():
        total_str = f"**{total_str}**"

    table_data.append([depth_str, spread_str, total_str, feat_str])

# Create text table
table_text = "RMSE Comparison\\n\\n"
table_text += f"{'Depth':<8} {'Spread':<10} {'Total':<10} {'Features':<10}\\n"
table_text += "-" * 45 + "\\n"
for row in table_data[1:]:
    table_text += f"{row[0]:<8} {row[1]:<10} {row[2]:<10} {row[3]:<10}\\n"

ax4.text(
    0.1, 0.5, table_text, fontsize=11, family="monospace", verticalalignment="center"
)
ax4.text(0.5, 0.9, "KEY FINDINGS", fontsize=13, fontweight="bold", ha="center")

# Key findings text
findings_text = f"""
Best Spread RMSE: Depth {int(results_df.loc[results_df["spread_rmse"].idxmin(), "depth"])} ({results_df["spread_rmse"].min():.2f})
Best Total RMSE: Depth {int(results_df.loc[results_df["total_rmse"].idxmin(), "depth"])} ({results_df["total_rmse"].min():.2f})

Current Default: Depth 2
Recommendation: Depth 2 offers best balance
(minimal difference from depth 4, fewer features)
"""
ax4.text(
    0.1,
    0.05,
    findings_text,
    fontsize=10,
    verticalalignment="bottom",
    bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
)

plt.tight_layout()

# Save figure
output_path = Path("artifacts/reports/metrics/adjustment_iteration_comparison.png")
plt.savefig(output_path, dpi=300, bbox_inches="tight")
print(f"Saved visualization to {output_path}")
plt.close()

print("\\nVisualization complete!")
