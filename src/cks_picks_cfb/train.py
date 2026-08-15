import json
from pathlib import Path

import hydra
import mlflow
import pandas as pd
from omegaconf import DictConfig, OmegaConf
from sklearn.preprocessing import RobustScaler, StandardScaler

from cks_picks_cfb.features.v1_pipeline import load_v1_data
from cks_picks_cfb.models.v1_baseline import V1BaselineModel
from cks_picks_cfb.utils.mlflow_tracking import (
    get_or_create_experiment,
    get_tracking_uri,
)


def train_preseason_regimes(cfg: DictConfig) -> dict:
    """Train preseason candidates through the canonical training entry point."""
    from cks_picks_cfb.data.storage import get_storage
    from cks_picks_cfb.preseason import (
        build_preseason_matchups,
        evaluate_preseason_candidate,
        save_preseason_models,
    )

    spec = cfg.experiment
    snapshots = [(int(item.year), str(item.as_of)) for item in spec.snapshots]
    if {year for year, _ in snapshots} != {2021, 2022, 2023, 2024}:
        raise ValueError("Preseason training snapshots must cover 2021-2024")
    if int(spec.holdout.year) != 2025:
        raise ValueError("The locked promotion test must be 2025")
    storage = get_storage()
    train = pd.concat(
        [
            build_preseason_matchups(
                storage, year=year, as_of=as_of, include_targets=True
            )
            for year, as_of in snapshots
        ],
        ignore_index=True,
    )
    holdout = build_preseason_matchups(
        storage,
        year=2025,
        as_of=str(spec.holdout.as_of),
        include_targets=True,
    )
    bundle, metrics = evaluate_preseason_candidate(
        train, holdout, None, alpha=float(spec.get("alpha", 10.0))
    )
    output = Path(str(spec.output))
    output.parent.mkdir(parents=True, exist_ok=True)
    save_preseason_models(bundle, output)
    mlflow.log_metrics(
        {
            key: value
            for key, value in metrics.items()
            if isinstance(value, (int, float))
        }
    )
    mlflow.log_artifact(str(output))
    print(json.dumps(metrics, indent=2, sort_keys=True))
    return metrics


def train_early_season_tournament(cfg: DictConfig) -> dict:
    """Generate strict temporal candidate predictions from one Gold dataset."""
    from cks_picks_cfb.data.lake import DatasetRef, read_dataset
    from cks_picks_cfb.data.storage import get_storage
    from cks_picks_cfb.models.regime_training import (
        generate_temporal_candidate_predictions,
    )
    from cks_picks_cfb.models.training_policy import policy_from_mapping

    spec = cfg.experiment
    storage = get_storage()
    if spec.get("feature_dataset_ref"):
        ref = DatasetRef(
            **OmegaConf.to_container(spec.feature_dataset_ref, resolve=True)
        )
    elif spec.get("feature_dataset_ref_uri"):
        raw_ref = json.loads(
            storage.read_bytes(str(spec.feature_dataset_ref_uri)).decode("utf-8")
        )
        ref = DatasetRef(**raw_ref)
    else:
        raise ValueError(
            "week0 regime training requires an immutable Gold feature_dataset_ref "
            "or feature_dataset_ref_uri"
        )
    frame = read_dataset(storage, ref)
    policy_path = Path(str(spec.training_policy))
    if not policy_path.is_absolute():
        policy_path = Path(hydra.utils.get_original_cwd()) / policy_path
    policy_raw = OmegaConf.to_container(OmegaConf.load(policy_path), resolve=True)
    policy = policy_from_mapping(policy_raw)
    predictions, weights = generate_temporal_candidate_predictions(
        frame,
        policy=policy,
        prior_features=list(spec.prior_features),
        current_features=list(spec.current_features),
        baseline_columns=OmegaConf.to_container(spec.baseline_columns, resolve=True),
        market_line_columns=OmegaConf.to_container(
            spec.market_line_columns, resolve=True
        ),
        random_seed=int(cfg.get("random_seed", 42)),
    )
    output = Path(str(spec.output))
    output.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(output, index=False)
    weights_path = output.with_suffix(".weights.json")
    weights_path.write_text(json.dumps(weights, indent=2, sort_keys=True))
    mlflow.log_artifact(str(output))
    mlflow.log_artifact(str(weights_path))
    result = {
        "rows": len(predictions),
        "feature_dataset_version": ref.version_id,
        "selection_years": [2022, 2023, 2024],
        "locked_test_year": 2025,
        "blend_weights": weights,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def load_and_prepare_data(cfg: DictConfig, max_workers: int = 3):
    """Load and concatenate data for configured years with parallel loading."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Extract features list if available
    features = None
    if "features" in cfg:
        if "groups" in cfg.features:
            features = list(cfg.features.groups)
        elif "features" in cfg.features:
            features = list(cfg.features.features)

    # Check for recency features
    use_recency = False
    if "features" in cfg and "params" in cfg.features:
        if cfg.features.params.get("type") == "recency":
            use_recency = True
            alpha = cfg.features.params.get("alpha", 0.5)

    def load_year(year):
        """Helper to load data for a single year."""
        if use_recency:
            from cks_picks_cfb.features.v2_recency import load_v2_recency_data

            df = load_v2_recency_data(year, alpha=alpha)
        else:
            df = load_v1_data(year, features=features)
        return year, df

    # Load Training Data in parallel
    print(
        f"Loading training data for years {cfg.training.train_years} (parallel={max_workers} workers)..."
    )
    train_dfs = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_year = {
            executor.submit(load_year, year): year for year in cfg.training.train_years
        }
        for future in as_completed(future_to_year):
            year, df = future.result()
            if df is not None:
                print(f"  ✓ Loaded {year}: {len(df)} rows")
                train_dfs.append((year, df))
            else:
                print(f"  ✗ Failed to load {year}")

    if not train_dfs:
        raise ValueError(f"No training data found for years {cfg.training.train_years}")

    # Sort by year to maintain order
    train_dfs.sort(key=lambda x: x[0])
    train_df = pd.concat([df for _, df in train_dfs], ignore_index=True)
    print(f"Training data loaded: {len(train_df)} total rows")

    # Load Test Data
    print(f"Loading test data for {cfg.training.test_year}...")
    _, test_df = load_year(cfg.training.test_year)

    if test_df is None:
        raise ValueError(f"No test data found for year {cfg.training.test_year}")
    print(f"Test data loaded: {len(test_df)} rows")

    return train_df, test_df


def get_model(cfg: DictConfig, feature_override=None):
    """Factory to get model based on config type."""
    # Use override if provided, else config
    features = feature_override
    if features is None and "features" in cfg and "features" in cfg.features:
        features = list(cfg.features.features)

    if cfg.model.type == "linear_regression":
        # Pass params from config
        params = cfg.model.get("params", {})
        # Convert DictConfig to dict for unpacking
        params = OmegaConf.to_container(params, resolve=True)
        return V1BaselineModel(features=features, target=cfg.model.target, **params)
    elif cfg.model.type == "catboost":
        from cks_picks_cfb.models.v2_catboost import V2CatBoostModel

        params = cfg.model.get("params", {})
        params = OmegaConf.to_container(params, resolve=True)
        return V2CatBoostModel(features=features, target=cfg.model.target, **params)
    elif cfg.model.type == "xgboost":
        from cks_picks_cfb.models.v2_xgboost import V2XGBoostModel

        params = cfg.model.get("params", {})
        params = OmegaConf.to_container(params, resolve=True)
        # remove early_stopping_rounds from init params if passed, as it's usually for fit
        if "early_stopping_rounds" in params:
            del params["early_stopping_rounds"]
        return V2XGBoostModel(features=features, target=cfg.model.target, **params)
    elif cfg.model.type == "ensemble":
        from cks_picks_cfb.models.v2_ensemble import V2EnsembleModel

        params = cfg.model.get("params", {})
        params = OmegaConf.to_container(params, resolve=True)
        return V2EnsembleModel(features=features, **params)
    elif cfg.model.type == "stacking":
        from cks_picks_cfb.models.v2_stacking import V2StackingModel

        params = cfg.model.get("params", {})
        params = OmegaConf.to_container(params, resolve=True)
        return V2StackingModel(features=features, **params)
    elif cfg.model.type == "catboost_classifier":
        from cks_picks_cfb.models.v2_classifier import V2ClassifierModel

        params = cfg.model.get("params", {})
        params = OmegaConf.to_container(params, resolve=True)
        return V2ClassifierModel(features=features, target=cfg.model.target, **params)
    else:
        raise ValueError(f"Unknown model type: {cfg.model.type}")


@hydra.main(config_path="../../conf", config_name="config", version_base="1.2")
def main(cfg: DictConfig):
    # Setup MLflow
    mlflow.set_tracking_uri(get_tracking_uri())

    # Handle experiment name safely
    exp_name = "Default"
    if "experiment" in cfg and cfg.experiment is not None:
        exp_name = cfg.experiment.get("name", "Default")

    experiment_id = get_or_create_experiment(exp_name)

    with mlflow.start_run(experiment_id=experiment_id, run_name=cfg.model.name):
        # Log Config
        mlflow.log_params(OmegaConf.to_container(cfg, resolve=True))

        if cfg.get("experiment") and cfg.experiment.get("workflow") == "preseason":
            train_preseason_regimes(cfg)
            return
        if (
            cfg.get("experiment")
            and cfg.experiment.get("workflow") == "early_season_tournament"
        ):
            train_early_season_tournament(cfg)
            return

        # Load Data
        print("Loading Data...")
        train_df, test_df = load_and_prepare_data(cfg)
        print(f"Train size: {len(train_df)}, Test size: {len(test_df)}")

        # Feature Selection & Interaction Generation
        from cks_picks_cfb.features.selector import select_features

        # Note: select_features modifies df in-place to add interactions,
        # then returns the selected subset. We want the side-effect (interactions added to df)
        # and the list of selected columns.
        train_features = select_features(train_df, cfg)
        _ = select_features(test_df, cfg)  # Apply same transforms to test (side-effect)

        final_features = list(train_features.columns)
        print(f"Selected {len(final_features)} features (including interactions).")

        # Optional preprocessing (e.g., standardization)
        if cfg.get("preprocessing"):
            pre = cfg.preprocessing
            if pre.get("standardize", False):
                scaler = StandardScaler()
                print(
                    "Applying feature standardization (fit on train, transform train/test)..."
                )
                train_df.loc[:, final_features] = scaler.fit_transform(
                    train_df[final_features]
                )
                test_df.loc[:, final_features] = scaler.transform(
                    test_df[final_features]
                )

            # Optional robust scaling for pass YPP matchup features only
            if pre.get("robust_pass_ypp", False):
                pass_cols = [
                    "home_adj_off_pass_ypp",
                    "home_adj_def_pass_ypp",
                    "away_adj_off_pass_ypp",
                    "away_adj_def_pass_ypp",
                ]
                missing = [c for c in pass_cols if c not in train_df.columns]
                if missing:
                    print(f"Skipping robust_pass_ypp; missing columns: {missing[:4]}")
                else:
                    r_scaler = RobustScaler()
                    print("Applying RobustScaler to pass YPP matchup features...")
                    train_df.loc[:, pass_cols] = r_scaler.fit_transform(
                        train_df[pass_cols]
                    )
                    test_df.loc[:, pass_cols] = r_scaler.transform(test_df[pass_cols])

        # Initialize Model
        model = get_model(cfg, feature_override=final_features)

        # Train
        print("Training...")
        model.fit(train_df)

        # Evaluate
        print("Evaluating...")
        metrics = model.evaluate(test_df)

        # Log Metrics
        mlflow.log_metrics(metrics)
        print(f"Metrics: {metrics}")

        # Save Model (Local & MLflow)
        # For now, just local save if model supports it
        if hasattr(model, "save"):
            from cks_picks_cfb.config import get_repo_root

            # Determine extension
            ext = ".joblib"
            if cfg.model.type == "xgboost":
                ext = ".json"
            elif cfg.model.type in ("catboost", "catboost_classifier"):
                ext = ".cbm"

            # Use absolute path relative to repo root
            model_dir = get_repo_root() / "models"
            model_dir.mkdir(parents=True, exist_ok=True)
            model_path = model_dir / f"{cfg.model.name}_{cfg.model.target}{ext}"
            model.save(model_path)

            # wrapper might append extension, check for it
            if not model_path.exists():
                if Path(f"{model_path}.json").exists():
                    model_path = Path(f"{model_path}.json")

            if model_path.exists():
                mlflow.log_artifact(str(model_path))
            else:
                print(f"Warning: Could not find saved model at {model_path}")


if __name__ == "__main__":
    main()
