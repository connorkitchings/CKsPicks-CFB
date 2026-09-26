#!/usr/bin/env python3
"""Project independently verified V5 rating states into Neon serving tables."""

from __future__ import annotations

import argparse
import hashlib
import json
import os

import pandas as pd
import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.live_sources import _read_frame
from cks_picks_cfb.ops.lease import assert_active_pipeline_lease
from cks_picks_cfb.ratings.possession_live_replay import (
    FROZEN_CANDIDATE,
    build_current_team_states,
)


def _read_signed(storage, uri: str) -> tuple[dict, str]:
    raw = storage.read_bytes(uri)
    payload = json.loads(raw)
    verify_signed_payload(payload, label=uri)
    return payload, hashlib.sha256(raw).hexdigest()


def load_verified_snapshots(storage, rating_uri: str) -> tuple[list[dict], str]:
    rating, rating_sha = _read_signed(storage, rating_uri)
    if (
        rating.get("state") != "frozen"
        or rating.get("selected_candidate") != FROZEN_CANDIDATE
    ):
        raise ValueError("rating replay is not the frozen V5 candidate")
    verifier_uri = f"{rating_uri.rsplit('/', 1)[0]}/verification/verifier-manifest.json"
    verifier, _ = _read_signed(storage, verifier_uri)
    if (
        verifier.get("state") != "verified"
        or verifier.get("retained_manifest_raw_sha256") != rating_sha
    ):
        raise ValueError("rating replay lacks a matching independent verifier")
    parents = rating.get("parents") or {}
    measurement, measurement_sha = _read_signed(
        storage, str(parents["measurement_manifest_uri"])
    )
    if measurement_sha != parents.get("measurement_manifest_raw_sha256"):
        raise ValueError("rating replay measurement parent changed")
    historical_rating, historical_sha = _read_signed(
        storage, str(parents["historical_rating_manifest_uri"])
    )
    if historical_sha != parents.get("historical_rating_manifest_raw_sha256"):
        raise ValueError("rating replay historical rating parent changed")
    historical_measurement_uri = str(
        (historical_rating.get("parents") or {})["measurement_manifest_uri"]
    )
    historical_measurement, historical_measurement_sha = _read_signed(
        storage, historical_measurement_uri
    )
    if historical_measurement_sha != parents.get(
        "historical_measurement_manifest_raw_sha256"
    ):
        raise ValueError("rating replay historical measurement parent changed")
    rating_outputs = rating["output_refs"]
    measurement_outputs = measurement["output_refs"]
    population = _read_frame(storage, measurement_outputs["population"], "population")
    pregame = _read_frame(storage, rating_outputs["team_states"], "team_states")
    priors_df = _read_frame(storage, rating_outputs["priors"], "priors")
    current = build_current_team_states(
        population=population,
        observations=_read_frame(
            storage, measurement_outputs["observations"], "observations"
        ),
        snapshots=_read_frame(storage, measurement_outputs["snapshots"], "snapshots"),
        terminal=_read_frame(storage, measurement_outputs["terminal"], "terminal"),
        priors=priors_df,
        historical_terminal=_read_frame(
            storage,
            historical_measurement["output_refs"]["terminal"],
            "historical terminal",
        ),
        as_of=str((measurement.get("identity") or {})["as_of"]),
        target_week=int(population.loc[population["season"].eq(2026), "week"].max())
        + 1,
    )
    run_id = str((rating.get("identity") or {})["run_id"])
    records: list[dict] = []
    p_off = priors_df[priors_df["unit_role"] == "offense"].set_index("team")
    p_def = priors_df[priors_df["unit_role"] == "defense"].set_index("team")
    common_teams = sorted(set(p_off.index) & set(p_def.index))
    preseason_cutoff = pd.Timestamp("2026-08-20T00:00:00Z").to_pydatetime()
    for team in common_teams:
        off_mean = float(p_off.loc[team, "prior_mean"])
        off_var = float(p_off.loc[team, "prior_variance"])
        def_mean = float(p_def.loc[team, "prior_mean"])
        def_var = float(p_def.loc[team, "prior_variance"])
        fallbacks = [
            p_off.loc[team, "fallback_reason"],
            p_def.loc[team, "fallback_reason"],
        ]
        fb = ";".join(sorted(set(f for f in fallbacks if f))) or None
        records.append(
            {
                "snapshot_id": f"{run_id}:pregame:{team}:preseason",
                "source_run_id": run_id,
                "source_manifest_sha256": rating_sha,
                "team": str(team),
                "season": 2026,
                "week": 0,
                "game_id": None,
                "snapshot_class": "pregame",
                "cutoff_utc": preseason_cutoff,
                "offense_rating": off_mean,
                "offense_variance": off_var,
                "defense_rating": def_mean,
                "defense_variance": def_var,
                "overall_rating": (off_mean + def_mean) / 2.0,
                "overall_variance": (off_var + def_var) / 4.0,
                "fallback_reason": fb,
            }
        )
    for classification, frame in (("pregame", pregame), ("current", current)):
        for row in frame.to_dict("records"):
            if row["candidate_id"] != FROZEN_CANDIDATE:
                raise ValueError("rating projection includes another candidate")
            game_id = int(row["game_id"]) if classification == "pregame" else None
            records.append(
                {
                    "snapshot_id": f"{run_id}:{classification}:{row['team']}:{game_id or 'current'}",
                    "source_run_id": run_id,
                    "source_manifest_sha256": rating_sha,
                    "team": str(row["team"]),
                    "season": int(row["season"]),
                    "week": int(row["week"]),
                    "game_id": game_id,
                    "snapshot_class": classification,
                    "cutoff_utc": pd.Timestamp(row["cutoff_utc"]).to_pydatetime(),
                    "offense_rating": float(row["offense_rating"]),
                    "offense_variance": float(row["offense_variance"]),
                    "defense_rating": float(row["defense_rating"]),
                    "defense_variance": float(row["defense_variance"]),
                    "overall_rating": float(row["overall_rating"]),
                    "overall_variance": float(row["overall_variance"]),
                    "fallback_reason": row.get("fallback_reason"),
                }
            )
    return records, rating_sha


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rating-manifest-uri", required=True)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    storage = get_storage(environment="preview")
    records, sha = load_verified_snapshots(storage, args.rating_manifest_uri)
    if not args.apply:
        print(json.dumps({"rows": len(records), "rating_manifest_sha256": sha}))
        return
    url_var = (
        "PREVIEW_DATABASE_URL" if args.environment == "preview" else "DATABASE_URL"
    )
    url = os.getenv(url_var)
    if not url:
        raise SystemExit(f"{url_var} is required")
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            assert_active_pipeline_lease(cur)
            cur.execute("SELECT model_id FROM v5_release_policy WHERE id = 1")
            if not cur.fetchone():
                raise ValueError("V5 release policy is absent")
            for record in records:
                cur.execute(
                    "INSERT INTO v5_rating_snapshots ("
                    "snapshot_id, source_run_id, source_manifest_sha256, team, season, week, "
                    "game_id, snapshot_class, cutoff_utc, offense_rating, offense_variance, "
                    "defense_rating, defense_variance, overall_rating, overall_variance, fallback_reason"
                    ") VALUES ("
                    "%(snapshot_id)s, %(source_run_id)s, %(source_manifest_sha256)s, %(team)s, "
                    "%(season)s, %(week)s, %(game_id)s, %(snapshot_class)s, %(cutoff_utc)s, "
                    "%(offense_rating)s, %(offense_variance)s, %(defense_rating)s, "
                    "%(defense_variance)s, %(overall_rating)s, %(overall_variance)s, %(fallback_reason)s"
                    ") ON CONFLICT (snapshot_id) DO NOTHING",
                    record,
                )
    print(json.dumps({"published_rows": len(records), "rating_manifest_sha256": sha}))


if __name__ == "__main__":
    main()
