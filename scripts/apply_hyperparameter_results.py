#!/usr/bin/env python3
"""
Monitor hyperparameter optimization and apply best results.

Waits for optimization to complete, then:
1. Parses the best parameters
2. Updates train_model.py with new parameters
3. Retrains models
4. Evaluates on 2024 holdout
5. Generates comparison report
"""

import json
import os
import sys
import time


def wait_for_optimization(results_path: str, timeout_minutes: int = 60) -> bool:
    """Wait for optimization results file to appear."""
    print(f"Waiting for results at {results_path}...")
    start_time = time.time()
    timeout_seconds = timeout_minutes * 60

    while time.time() - start_time < timeout_seconds:
        if os.path.exists(results_path):
            # Give it a moment to ensure file is fully written
            time.sleep(2)
            return True
        time.sleep(5)
        elapsed = int(time.time() - start_time)
        print(f"  Still waiting... ({elapsed}s elapsed)")

    return False


def load_optimization_results(results_path: str) -> dict:
    """Load optimization results from JSON."""
    with open(results_path, "r") as f:
        return json.load(f)


def generate_comparison_report(
    results: list[dict], output_path: str = "./reports/optimization/comparison.md"
) -> None:
    """Generate markdown comparison report."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        f.write("# Hyperparameter Optimization Results\n\n")
        f.write(f"**Generated**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        for result in results:
            f.write(f"## {result['model_name']} ({result['target']})\n\n")
            f.write("### Performance\n")
            f.write(
                f"- **CV RMSE**: {result['best_cv_score']:.3f} ± {result['cv_std']:.3f}\n"
            )
            f.write(f"- **Test RMSE**: {result['test_rmse']:.3f}\n")
            f.write(f"- **Test MAE**: {result['test_mae']:.3f}\n")
            f.write(
                f"- **Improvement vs Baseline**: {result['improvement_vs_baseline']:+.2f}%\n\n"
            )

            f.write("### Best Parameters\n")
            f.write("```python\n")
            for key, value in result["best_params"].items():
                if isinstance(value, str):
                    f.write(f"{key}='{value}',\n")
                else:
                    f.write(f"{key}={value},\n")
            f.write("```\n\n")

    print(f"✅ Comparison report saved to {output_path}")


def main():
    """Main execution."""
    results_path = "./reports/optimization/hyperparameter_optimization_results.json"

    print("=" * 60)
    print("HYPERPARAMETER OPTIMIZATION MONITOR")
    print("=" * 60)

    # Wait for results
    if not wait_for_optimization(results_path, timeout_minutes=60):
        print("\n❌ Timeout waiting for optimization results")
        sys.exit(1)

    print("\n✅ Optimization complete! Loading results...")

    # Load results
    results = load_optimization_results(results_path)
    print(f"Found {len(results)} optimization results")

    # Generate comparison report
    generate_comparison_report(results)

    # Display summary
    print("\n" + "=" * 60)
    print("OPTIMIZATION SUMMARY")
    print("=" * 60)

    for result in results:
        print(f"\n{result['model_name']} ({result['target']}):")
        print(f"  Improvement: {result['improvement_vs_baseline']:+.2f}%")
        print(f"  Test RMSE: {result['test_rmse']:.3f}")
        print(f"  Best params: {result['best_params']}")

    # Instructions for next steps
    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    print("\n1. Review results in: ./reports/optimization/")
    print("2. If improvements are significant, update train_model.py manually")
    print("3. Retrain models with:")
    print("   uv run python src/cfb_model/models/train_model.py \\")
    print("     --train-years 2019,2021,2022,2023 \\")
    print("     --test-year 2024 \\")
    print('     --data-root "/Volumes/CK SSD/Coding Projects/cfb_model"')
    print("4. Run full season evaluation to confirm improvements")

    print("\n✅ Monitor complete!")


if __name__ == "__main__":
    main()
