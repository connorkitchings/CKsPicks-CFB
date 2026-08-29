#!/usr/bin/env python3
"""Certify complete successor-v2 R1 history directly from immutable refs."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from typing import Any, Mapping

import pandas as pd

from cks_picks_cfb.data.lake import DatasetRef, read_dataset, require_dataset
from cks_picks_cfb.data.season_lineage import load_season_lineage_policy
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.successor_history import (
    DERIVED_REF_SET_VERSION,
    REQUIRED_DATASETS,
    SeasonCoverageEvidence,
    coverage_report,
    derived_history_dataset_refs,
    expanded_history_ref_set,
)


def _immutable_write(storage, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable successor-v2 artifact collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _ref(value: Mapping[str, Any]) -> DatasetRef:
    return DatasetRef(**dict(value))


def _report(storage, uri: str, *, label: str) -> tuple[dict[str, Any], str]:
    payload = storage.read_bytes(uri)
    raw = json.loads(payload.decode())
    if not isinstance(raw, dict) or not raw.get("all_checks_passed"):
        raise ValueError(f"{label} must be an immutable passing report")
    return raw, _sha256(payload)


def _finals_reconciliation(
    measurement_report: Mapping[str, Any], policy: Any
) -> dict[int, tuple[int, int]]:
    """Extract per-season finals-exact counts from the immutable measurement report.

    The gated score-stream reconciliation metric is the Phase-1 finals-exact
    rate; the measurement report is its immutable source of truth.
    """

    try:
        reconciliation = measurement_report["observations"]["score_reconciliation"]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "Measurement report does not expose score-stream reconciliation"
        ) from exc
    if not isinstance(reconciliation, Mapping):
        raise ValueError("Measurement report score reconciliation is invalid")
    finals: dict[int, tuple[int, int]] = {}
    for season in policy.historical_development_seasons:
        entry = reconciliation.get(str(season))
        if not isinstance(entry, Mapping):
            raise ValueError(
                f"Measurement report lacks finals reconciliation for {season}"
            )
        try:
            exact = int(entry["exact_team_scores"])
            expected = int(entry["expected_team_scores"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Measurement report finals reconciliation for {season} is invalid"
            ) from exc
        if exact < 0 or expected <= 0 or exact > expected:
            raise ValueError(
                f"Measurement report finals reconciliation for {season} is invalid"
            )
        finals[season] = (exact, expected)
    return finals


def _complete_game_ids(games: pd.DataFrame, season: int) -> set[int]:
    required = {"season", "game_id", "completed", "home_team", "away_team"}
    missing = sorted(required - set(games.columns))
    if missing:
        raise ValueError(f"games ref for {season} lacks required columns: {missing}")
    scoped = games[pd.to_numeric(games["season"], errors="coerce") == season].copy()
    if scoped[["game_id", "home_team", "away_team"]].isna().any().any():
        raise ValueError(f"games ref for {season} has incomplete canonical keys")
    if scoped.duplicated(["game_id"]).any():
        raise ValueError(f"games ref for {season} has duplicate game IDs")
    completed = scoped[scoped["completed"].eq(True)]
    return set(pd.to_numeric(completed["game_id"], errors="raise").astype(int))


def _play_covered_game_ids(plays: pd.DataFrame, season: int) -> set[int]:
    required = {"season", "game_id"}
    missing = sorted(required - set(plays.columns))
    if missing:
        raise ValueError(f"plays ref for {season} lacks required columns: {missing}")
    scoped = plays[pd.to_numeric(plays["season"], errors="coerce") == season]
    return set(pd.to_numeric(scoped["game_id"].dropna(), errors="raise").astype(int))


def _reconciled_score_game_ids(observations: pd.DataFrame, season: int) -> set[int]:
    required = {"season", "game_id", "measurement_id", "coverage_status", "team"}
    missing = sorted(required - set(observations.columns))
    if missing:
        raise ValueError(
            f"measurement observations lack score-reconciliation columns: {missing}"
        )
    scoped = observations[
        (pd.to_numeric(observations["season"], errors="coerce") == season)
        & (observations["measurement_id"] == "points_per_scoring_opportunity")
        & (observations["coverage_status"] == "observed")
    ]
    counts = scoped.groupby("game_id")["team"].nunique()
    return set(pd.to_numeric(counts[counts >= 2].index, errors="raise").astype(int))


def _representative_teams(
    games: pd.DataFrame, season: int, completed: set[int]
) -> set[str]:
    scoped = games[
        (pd.to_numeric(games["season"], errors="coerce") == season)
        & pd.to_numeric(games["game_id"], errors="coerce").isin(completed)
    ]
    return {
        str(team)
        for column in ("home_team", "away_team")
        for team in scoped[column].dropna()
    }


def _terminal_teams(team_states: pd.DataFrame, season: int) -> set[str]:
    required = {"season", "state_kind", "team"}
    missing = sorted(required - set(team_states.columns))
    if missing:
        raise ValueError(f"team-state ref lacks terminal columns: {missing}")
    scoped = team_states[
        (pd.to_numeric(team_states["season"], errors="coerce") == season)
        & (team_states["state_kind"] == "season_terminal")
    ]
    return {str(team) for team in scoped["team"].dropna()}


def _stable_refs(refs: Mapping[str, DatasetRef], season: int) -> bool:
    return season != 2020 and all(
        ref.schema_version and ref.content_sha and ref.version_id and ref.uri
        for ref in refs.values()
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument(
        "--season-lineage-policy",
        default="conf/ratings/successor_v2_season_lineage.yaml",
    )
    parser.add_argument("--derived-ref-set-uri", required=True)
    parser.add_argument("--measurement-report-uri", required=True)
    parser.add_argument("--state-report-uri", required=True)
    parser.add_argument("--cross-lineage-report-uri", required=True)
    parser.add_argument("--expanded-ref-set-uri", required=True)
    parser.add_argument("--coverage-report-uri", required=True)
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise ValueError("Successor-v2 history certification is Preview-only")
    policy = load_season_lineage_policy(args.season_lineage_policy)
    outputs = (args.expanded_ref_set_uri, args.coverage_report_uri)
    if any(not uri.startswith(f"{policy.research_prefix}/") for uri in outputs):
        raise ValueError("Successor-v2 outputs must use the isolated research prefix")
    storage = get_storage(environment="preview")
    derived_bytes = storage.read_bytes(args.derived_ref_set_uri)
    derived = json.loads(derived_bytes.decode())
    if (
        derived.get("contract_version") != DERIVED_REF_SET_VERSION
        or derived.get("state") != "complete"
        or derived.get("season_lineage_policy_version") != policy.version
        or not derived.get("source_set_sha256")
    ):
        raise ValueError("Certification requires a complete R1 derived-ref set")
    refs = derived_history_dataset_refs(derived)
    measurement_report, measurement_report_sha = _report(
        storage, args.measurement_report_uri, label="measurement report"
    )
    state_report, state_report_sha = _report(
        storage, args.state_report_uri, label="state report"
    )
    cross_lineage_report, cross_lineage_report_sha = _report(
        storage, args.cross_lineage_report_uri, label="cross-lineage report"
    )
    if (
        cross_lineage_report.get("contract_version")
        != "successor-cross-lineage-audit-v2"
    ):
        raise ValueError("Certification requires the successor-v2 cross-lineage audit")
    try:
        observations_ref = _ref(measurement_report["lineage"]["observations_ref"])
        team_states_ref = _ref(state_report["lineage"]["team_state_ref"])
    except (KeyError, TypeError) as exc:
        raise ValueError("R1 reports do not expose immutable dataset lineage") from exc
    require_dataset(observations_ref, "rating_measurement_observations")
    require_dataset(team_states_ref, "rating_team_states")
    observations = read_dataset(storage, observations_ref)
    team_states = read_dataset(storage, team_states_ref)
    finals = _finals_reconciliation(measurement_report, policy)
    evidence = []
    compatibility_refs: dict[tuple[int, str], DatasetRef] = {}
    for season in policy.historical_development_seasons:
        season_refs = {
            dataset: refs[(season, dataset)] for dataset in REQUIRED_DATASETS
        }
        for dataset, ref in season_refs.items():
            require_dataset(ref, dataset)
            compatibility_refs[(season, dataset)] = ref
        games = read_dataset(storage, season_refs["games"])
        plays = read_dataset(storage, season_refs["plays"])
        completed = _complete_game_ids(games, season)
        play_covered = _play_covered_game_ids(plays, season) & completed
        score_reconciled = _reconciled_score_game_ids(observations, season) & completed
        representative = _representative_teams(games, season, completed)
        terminal = _terminal_teams(team_states, season) & representative
        evidence.append(
            SeasonCoverageEvidence(
                season=season,
                completed_game_count=len(completed),
                completed_games_with_plays=len(play_covered),
                score_reconciled_game_count=len(score_reconciled),
                representative_terminal_team_count=len(terminal),
                representative_team_count=len(representative),
                stable_schema=_stable_refs(season_refs, season),
                final_exact_team_scores=finals[season][0],
                expected_team_scores=finals[season][1],
            )
        )
    report = coverage_report(policy, evidence)
    report["lineage"] = {
        "derived_ref_set_uri": args.derived_ref_set_uri,
        "derived_ref_set_sha256": _sha256(derived_bytes),
        "measurement_report_uri": args.measurement_report_uri,
        "measurement_report_sha256": measurement_report_sha,
        "state_report_uri": args.state_report_uri,
        "state_report_sha256": state_report_sha,
        "cross_lineage_report_uri": args.cross_lineage_report_uri,
        "cross_lineage_report_sha256": cross_lineage_report_sha,
        "observations_ref": asdict(observations_ref),
        "team_states_ref": asdict(team_states_ref),
    }
    report["evidence_origin"] = "computed_from_immutable_refs_v2"
    ref_set = expanded_history_ref_set(policy, compatibility_refs)
    _immutable_write(
        storage,
        args.expanded_ref_set_uri,
        json.dumps(ref_set, indent=2, sort_keys=True).encode(),
    )
    _immutable_write(
        storage,
        args.coverage_report_uri,
        json.dumps(report, indent=2, sort_keys=True).encode(),
    )
    print(
        json.dumps(
            {
                "expanded_ref_set_uri": args.expanded_ref_set_uri,
                "expanded_ref_set_sha256": ref_set["ref_set_sha256"],
                "coverage_report_uri": args.coverage_report_uri,
                "tournaments_permitted": report["tournaments_permitted"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
