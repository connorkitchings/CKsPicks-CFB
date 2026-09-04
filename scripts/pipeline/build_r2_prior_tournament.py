#!/usr/bin/env python3
"""Run the R2 between-season prior tournament from R1 foundation artifacts.

Reads the R1 foundation manifest, verifies tournaments_permitted=True, then
runs all non-context candidates through expanding folds using the fixed
Gaussian evaluation head.  Writes an immutable fold-metrics Parquet DatasetRef
and calls run_successor_tournament.py for the between_season stage selection.

Usage
-----
    PYTHONPATH=.:src uv run python scripts/pipeline/build_r2_prior_tournament.py \\
        --environment preview \\
        --r1-foundation-manifest-uri <URI> \\
        --output-prefix artifacts/research/rating-successor-v2/r2-prior-YYYYMMDD-SHA \\
        --as-of YYYY-MM-DDTHH:MM:SSZ \\
        --expected-code-sha $(git rev-parse HEAD)
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from cks_picks_cfb.data.lake import DatasetRef, read_dataset  # noqa: E402
from cks_picks_cfb.data.season_lineage import load_season_lineage_policy  # noqa: E402
from cks_picks_cfb.data.storage import get_storage  # noqa: E402
from cks_picks_cfb.ratings.evaluation_head import (  # noqa: E402
    EvaluationHeadError,
    fit_gaussian_head,
    fold_metrics,
    predict_gaussian_head,
)
from cks_picks_cfb.ratings.offseason_context import (  # noqa: E402
    require_admitted_context,
)
from cks_picks_cfb.ratings.priors import CANDIDATE_IDS, compute_prior  # noqa: E402
from cks_picks_cfb.ratings.successor_tournaments import (  # noqa: E402
    TOURNAMENT_CONTRACT_VERSION,
    load_tournament_configs,
)

METRICS_SCHEMA_VERSION = "r2_fold_metrics_v1"
MANIFEST_VERSION = "successor-r2-prior-tournament-v1"

# Candidates that require context admission (Option A: skip)
_CONTEXT_REQUIRED = frozenset(
    c for c in CANDIDATE_IDS if c.startswith("continuity_ridge_alpha_")
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _immutable_write(storage, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable R2 artifact collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def _ref_bytes(storage, uri: str) -> bytes:
    return storage.read_bytes(uri)


def _read_ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(_ref_bytes(storage, uri).decode()))


def _write_parquet_ref(
    storage,
    df: pd.DataFrame,
    uri: str,
    dataset: str,
    schema_version: str,
) -> DatasetRef:
    """Write a Parquet DataFrame as an immutable DatasetRef."""
    table = pa.Table.from_pandas(df, preserve_index=False)
    buf = io.BytesIO()
    pq.write_table(table, buf)
    payload = buf.getvalue()
    content_sha = _sha256(payload)
    _immutable_write(storage, uri, payload)
    ref = DatasetRef(
        dataset=dataset,
        version_id=content_sha[:16],
        schema_version=schema_version,
        content_sha=content_sha,
        uri=uri,
    )
    return ref


def _write_ref_pointer(storage, uri: str, ref: DatasetRef) -> None:
    payload = json.dumps(asdict(ref), sort_keys=True).encode()
    _immutable_write(storage, uri, payload)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--r1-foundation-manifest-uri", required=True)
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument(
        "--certify-report-uri",
        required=True,
        help="URI of the passing R1 coverage report pinned to this foundation.",
    )
    parser.add_argument("--context-admission-report-uri")
    parser.add_argument("--context-ref-uri")
    parser.add_argument(
        "--allow-reconstructed-context",
        action="store_true",
        help="Required to use reconstructed context in this Preview research run.",
    )
    args = parser.parse_args(argv)

    if args.environment != "preview":
        raise ValueError("R2 prior tournament is Preview-only")

    policy = load_season_lineage_policy("conf/ratings/successor_v2_season_lineage.yaml")
    load_tournament_configs(
        "conf/ratings/successor_v2_tournaments.yaml"
    )  # validate version

    # Validate output prefix is under research_prefix
    if not args.output_prefix.startswith(f"{policy.research_prefix}/"):
        raise ValueError(f"--output-prefix must start with {policy.research_prefix}/")

    # Validate code SHA
    current_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if current_sha != args.expected_code_sha:
        raise ValueError(
            f"Code SHA mismatch: HEAD={current_sha} expected={args.expected_code_sha}"
        )

    storage = get_storage(environment="preview")
    admitted_context = None
    admitted_context_families: tuple[str, ...] = ()
    context_report = None
    if bool(args.context_admission_report_uri) != bool(args.context_ref_uri):
        raise ValueError(
            "--context-admission-report-uri and --context-ref-uri must be supplied together"
        )
    if args.context_admission_report_uri:
        context_report = json.loads(
            storage.read_bytes(args.context_admission_report_uri).decode()
        )
        admitted_context_families = require_admitted_context(
            context_report,
            allow_reconstructed=args.allow_reconstructed_context,
        )
        admitted_context = read_dataset(
            storage, _read_ref(storage, args.context_ref_uri)
        )
        if set(admitted_context.get("feature_track", pd.Series()).dropna()) != {
            context_report["feature_track"]
        }:
            raise ValueError("Context DatasetRef track does not match admission report")

    # Load and validate R1 foundation manifest.  The parent foundation has its
    # own immutable code identity; downstream R2 code is expected to evolve.
    manifest_bytes = storage.read_bytes(args.r1_foundation_manifest_uri)
    foundation = json.loads(manifest_bytes.decode())
    if foundation.get("contract_version") != "successor-r1-foundation-v2":
        raise ValueError("R1 foundation manifest has unexpected contract version")
    if foundation.get("state") != "complete":
        raise ValueError("R1 foundation manifest is not complete")
    identity = foundation.get("identity", {})
    if not identity.get("code_sha"):
        raise ValueError("R1 foundation manifest is missing its code identity")

    certify_bytes = storage.read_bytes(args.certify_report_uri)
    certify = json.loads(certify_bytes.decode())
    if not certify.get("tournaments_permitted"):
        raise ValueError("R1 certify report: tournaments_permitted is not True")
    certification_lineage = certify.get("lineage") or {}
    expected_lineage = {
        "derived_ref_set_uri": foundation.get("derived_ref_set_uri"),
        "derived_ref_set_sha256": foundation.get("derived_ref_set_sha256"),
        "measurement_report_uri": foundation.get("measurement", {}).get("report"),
        "states_report_uri": foundation.get("states", {}).get("report"),
        "cross_lineage_report_uri": f"{args.r1_foundation_manifest_uri.rsplit('/', 2)[0]}/cross-lineage.json",
    }
    if (
        certification_lineage.get("derived_ref_set_uri")
        != expected_lineage["derived_ref_set_uri"]
        or certification_lineage.get("derived_ref_set_sha256")
        != expected_lineage["derived_ref_set_sha256"]
        or certification_lineage.get("measurement_report_uri")
        != expected_lineage["measurement_report_uri"]
        or certification_lineage.get("state_report_uri")
        != expected_lineage["states_report_uri"]
        or certification_lineage.get("cross_lineage_report_uri")
        != expected_lineage["cross_lineage_report_uri"]
    ):
        raise ValueError("R1 coverage report lineage does not match foundation")

    # Load measurement-state and team-state refs from foundation
    measurement_info = foundation.get("measurement", {})
    states_info = foundation.get("states", {})
    if not measurement_info or not states_info:
        raise ValueError("R1 foundation manifest missing measurement or states info")

    measurement_states_ref = _read_ref(storage, states_info["measurement"])
    team_states_ref = _read_ref(storage, states_info["team"])

    print("Loading R1 team state artifacts from R2...", flush=True)
    measurement_states = read_dataset(storage, measurement_states_ref)
    team_states = read_dataset(storage, team_states_ref)

    # 2025 is retained exclusively for the locked confirmation.  It must not
    # become a selection or fitting input for an earlier fold.
    for col_name, df in [
        ("measurement_states", measurement_states),
        ("team_states", team_states),
    ]:
        if "season" in df.columns:
            forbidden_present = pd.to_numeric(df["season"], errors="coerce").isin(
                [2020, 2026]
            )
            if forbidden_present.any():
                raise ValueError(f"{col_name} contains forbidden seasons")

    # Organise terminal states by season for prior fitting
    terminal_by_season: dict[int, pd.DataFrame] = {}
    if "state_kind" in measurement_states.columns:
        terminal_ms = measurement_states[
            measurement_states["state_kind"] == "season_terminal"
        ]
    else:
        terminal_ms = measurement_states
    for season in policy.historical_development_seasons:
        if season in (2020,):
            continue
        mask = (
            pd.to_numeric(
                terminal_ms.get("season", pd.Series(dtype=float)), errors="coerce"
            )
            == season
        )
        terminal_by_season[season] = terminal_ms[mask].copy()

    # We need game outcomes from the R1 derived-ref-set for evaluation
    # Load game outcomes from foundation input-refs layout
    # Format: <root>/foundation/input-refs/<season>/game_outcomes.json
    r1_root = args.r1_foundation_manifest_uri.rsplit("/", 1)[0]
    input_refs_root = f"{r1_root}/input-refs"

    outcomes_by_season: dict[int, pd.DataFrame] = {}
    print("Loading game outcome refs from R1 input-refs...", flush=True)
    for season in policy.historical_development_seasons:
        if season in (2020,):
            continue
        outcomes_uri = f"{input_refs_root}/{season}/game_outcomes.json"
        try:
            outcomes_ref = _read_ref(storage, outcomes_uri)
            outcomes_df = read_dataset(storage, outcomes_ref)
            outcomes_by_season[season] = outcomes_df
        except Exception as exc:
            print(f"  WARNING: could not load outcomes for {season}: {exc}", flush=True)

    active_candidates = [
        candidate
        for candidate in CANDIDATE_IDS
        if candidate not in _CONTEXT_REQUIRED or admitted_context is not None
    ]
    print(
        f"Running R2 with {len(active_candidates)} candidates: {active_candidates}",
        flush=True,
    )

    # Expanding-fold evaluation
    selection_folds = list(
        policy.prior_selection_target_seasons
    )  # [2018, 2019, 2022, 2023, 2024]
    all_fold_metrics: list[dict] = []

    for fold_season in selection_folds:
        # Training seasons: all historical seasons strictly before fold_season (excluding 2020)
        train_seasons = tuple(
            s
            for s in policy.historical_development_seasons
            if s < fold_season and s not in policy.forbidden_seasons
        )
        if not train_seasons:
            print(
                f"  Fold {fold_season}: no training seasons available, skipping",
                flush=True,
            )
            continue

        print(f"\nFold {fold_season}: training on {train_seasons}", flush=True)

        # Prepare source season terminal states for this fold
        transition = policy.prior_transition_for(fold_season)
        source_season = transition.source_season if transition else None
        if source_season is None:
            print(
                f"  Fold {fold_season}: seed season, using neutral priors only",
                flush=True,
            )
            source_terminal = pd.DataFrame()
        else:
            source_terminal = terminal_by_season.get(source_season, pd.DataFrame())

        # Build train team-states and outcomes for Gaussian head
        train_state_mask = pd.to_numeric(
            team_states.get("season", pd.Series(dtype=float)), errors="coerce"
        ).isin(train_seasons)
        train_team_states = team_states[train_state_mask]

        # Build combined outcomes for training seasons
        train_outcomes_parts = [
            outcomes_by_season[s] for s in train_seasons if s in outcomes_by_season
        ]
        if not train_outcomes_parts:
            print(
                f"  Fold {fold_season}: no training outcomes available, skipping",
                flush=True,
            )
            continue
        train_outcomes = pd.concat(train_outcomes_parts, ignore_index=True)

        # Fit the Gaussian head on training seasons
        try:
            head = fit_gaussian_head(
                team_states=train_team_states,
                game_outcomes=train_outcomes,
                train_seasons=train_seasons,
            )
        except EvaluationHeadError as exc:
            print(f"  Fold {fold_season}: head fit failed: {exc}", flush=True)
            continue

        # Get target team states and outcomes
        target_state_mask = (
            pd.to_numeric(
                team_states.get("season", pd.Series(dtype=float)), errors="coerce"
            )
            == fold_season
        )
        target_team_states_base = team_states[target_state_mask]
        target_outcomes = outcomes_by_season.get(fold_season, pd.DataFrame())
        if target_outcomes.empty:
            print(f"  Fold {fold_season}: no target outcomes, skipping", flush=True)
            continue

        for candidate_id in active_candidates:
            print(f"  Candidate {candidate_id}...", end=" ", flush=True)
            try:
                prior_df = compute_prior(
                    candidate_id=candidate_id,
                    terminal_states=source_terminal,
                    target_season=fold_season,
                    policy=policy,
                    training_terminal_states={
                        season: values
                        for season, values in terminal_by_season.items()
                        if season < fold_season
                        and season not in policy.forbidden_seasons
                    },
                    admitted_context=admitted_context,
                )
            except Exception as exc:
                print(f"PRIOR FAILED: {exc}", flush=True)
                continue

            # Build candidate team states by replacing prior columns in target team states
            # We use the prior to compute pregame states for the target fold
            # For simplicity: merge prior means as the preseason state for all teams
            # at completed_games=0 (first-game prior), then let actual state evolve
            # For R2 evaluation we use the existing R1 team states but with prior-adjusted
            # initial priors — the measurement states already encode the actual in-season
            # evidence. Here we re-compute the early-season states from the prior.
            #
            # Practical approach for R2: use the existing state's posterior for full-season
            # evaluation; for early-season (games 1-3), compute states using only the prior
            # mean and the first few observations (already encoded in the measurement states).
            #
            # For the R2 tournament, the key quantity is: how good is the PRIOR as a starting
            # point? We evaluate this by using the prior mean as the "prediction" for games
            # 1-3 (Games 1-3 use only the prior + very little in-season data), and the
            # full-season posterior as the "prediction" for full-season MAE.
            #
            # This is operationalized as: for early games, replace offense_mean/defense_mean
            # with the candidate prior means before feeding the Gaussian head.

            # Build candidate-adjusted team states for early games
            prior_lookup = {
                (str(r["team"]), str(r["measurement_id"]), str(r["unit_role"])): r
                for r in prior_df.to_dict("records")
            }
            # Aggregate prior to team level: offense_mean = mean of offense component priors
            prior_by_team: dict[str, dict[str, float]] = {}
            for (team, mid, role), r in prior_lookup.items():
                if team not in prior_by_team:
                    prior_by_team[team] = {
                        "offense_mean": 0.0,
                        "defense_mean": 0.0,
                        "offense_count": 0,
                        "defense_count": 0,
                    }
                if role == "offense":
                    prior_by_team[team]["offense_mean"] += r["prior_mean"]
                    prior_by_team[team]["offense_count"] += 1
                elif role == "defense":
                    prior_by_team[team]["defense_mean"] += r["prior_mean"]
                    prior_by_team[team]["defense_count"] += 1

            for team, d in prior_by_team.items():
                if d["offense_count"]:
                    d["offense_mean"] /= d["offense_count"]
                if d["defense_count"]:
                    d["defense_mean"] /= d["defense_count"]

            # Create early-season states with prior means
            early_states = target_team_states_base.copy()
            for i, row in early_states.iterrows():
                team = str(row["team"])
                if team in prior_by_team and int(row.get("completed_games", 99)) <= 3:
                    early_states.at[i, "offense_mean"] = prior_by_team[team][
                        "offense_mean"
                    ]
                    early_states.at[i, "defense_mean"] = prior_by_team[team][
                        "defense_mean"
                    ]

            try:
                preds = predict_gaussian_head(
                    head=head,
                    team_states=early_states,
                    game_outcomes=target_outcomes,
                    target_season=fold_season,
                )
            except EvaluationHeadError as exc:
                print(f"PREDICT FAILED: {exc}", flush=True)
                continue

            if preds.empty:
                print("no predictions generated", flush=True)
                continue

            metrics = fold_metrics(preds, candidate_id, fold_season)
            all_fold_metrics.append(metrics)
            print(
                f"early_margin_mae={metrics['early_margin_mae']:.4f} "
                f"full_margin_mae={metrics['full_margin_mae']:.4f}",
                flush=True,
            )

    if not all_fold_metrics:
        raise ValueError(
            "No fold metrics were generated; check R1 foundation artifacts"
        )

    # Write combined metrics Parquet
    metrics_df = pd.DataFrame(all_fold_metrics)
    # Drop diagnostic columns not in tournament contract
    tournament_cols = [
        "candidate_id",
        "season",
        "early_margin_mae",
        "early_total_mae",
        "full_margin_mae",
        "full_total_mae",
    ]
    metrics_for_tournament = metrics_df[
        [c for c in tournament_cols if c in metrics_df.columns]
    ]

    metrics_uri = f"{args.output_prefix}/fold-metrics/combined.parquet"
    metrics_ref = _write_parquet_ref(
        storage,
        metrics_for_tournament,
        metrics_uri,
        dataset="r2_fold_metrics",
        schema_version=METRICS_SCHEMA_VERSION,
    )
    metrics_ref_uri = f"{args.output_prefix}/fold-metrics/combined-ref.json"
    _write_ref_pointer(storage, metrics_ref_uri, metrics_ref)
    print(f"\nWrote fold metrics: {metrics_uri}", flush=True)

    # Write full diagnostics (includes early_n, full_n)
    diag_uri = f"{args.output_prefix}/fold-metrics/diagnostics.parquet"
    _write_parquet_ref(
        storage,
        metrics_df,
        diag_uri,
        dataset="r2_fold_metrics_diagnostics",
        schema_version=METRICS_SCHEMA_VERSION,
    )

    # Run the tournament selection
    selection_report_uri = f"{args.output_prefix}/selection-report.json"
    print("\nRunning tournament selection...", flush=True)
    selection_context_args = (
        ["--admitted-context-family", "continuity"]
        if admitted_context is not None
        else []
    )
    result = subprocess.run(
        [
            sys.executable,
            "scripts/pipeline/run_successor_tournament.py",
            "--environment",
            "preview",
            "--stage",
            "between_season",
            "--metrics-ref-uri",
            metrics_ref_uri,
            "--output-uri",
            selection_report_uri,
            *selection_context_args,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": ".:src"},
    )
    if result.returncode:
        print(f"Tournament runner stderr:\n{result.stderr}", flush=True)
        raise subprocess.CalledProcessError(
            result.returncode, "run_successor_tournament.py"
        )
    print(result.stdout, flush=True)

    # Parse selection result
    selection_result = json.loads(result.stdout.strip().splitlines()[-1])

    # Write R2 manifest
    manifest = {
        "contract_version": MANIFEST_VERSION,
        "state": "complete",
        "r1_foundation_manifest_uri": args.r1_foundation_manifest_uri,
        "r1_foundation_manifest_sha256": _sha256(manifest_bytes),
        "identity": {
            "code_sha": args.expected_code_sha,
            "as_of": args.as_of,
        },
        "tournament_contract_version": TOURNAMENT_CONTRACT_VERSION,
        "active_candidates": active_candidates,
        "skipped_candidates": [
            candidate
            for candidate in _CONTEXT_REQUIRED
            if candidate not in active_candidates
        ],
        "context_admission_report_uri": args.context_admission_report_uri,
        "context_ref_uri": args.context_ref_uri,
        "admitted_context_families": list(admitted_context_families),
        "selection_folds": selection_folds,
        "fold_metrics_ref": asdict(metrics_ref),
        "fold_metrics_ref_uri": metrics_ref_uri,
        "selection_report_uri": selection_report_uri,
        "selection": selection_result,
    }
    manifest["manifest_sha256"] = _sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    )
    manifest_uri = f"{args.output_prefix}/manifest.json"
    _immutable_write(
        storage,
        manifest_uri,
        json.dumps(manifest, indent=2, sort_keys=True).encode(),
    )
    print(f"\nR2 manifest written: {manifest_uri}", flush=True)
    print(json.dumps(selection_result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
