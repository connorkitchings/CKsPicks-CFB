from pathlib import Path

import yaml


def load_features(path):
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return set(data.get("groups", []))


def main():
    base_dir = Path("conf/features")
    home_path = base_dir / "points_for_home_pruned.yaml"
    away_path = base_dir / "points_for_away_pruned.yaml"

    home_features = load_features(home_path)
    away_features = load_features(away_path)

    union_features = sorted(list(home_features | away_features))

    output_data = {
        "name": "points_for_pruned_union",
        "recency_window": "standard",
        "groups": union_features,
    }

    output_path = base_dir / "points_for_pruned_union.yaml"
    with open(output_path, "w") as f:
        yaml.dump(output_data, f, sort_keys=False)

    print(
        f"Created union feature set with {len(union_features)} features at {output_path}"
    )
    print(f"Home features: {len(home_features)}")
    print(f"Away features: {len(away_features)}")
    print(f"Overlap: {len(home_features & away_features)}")


if __name__ == "__main__":
    main()
