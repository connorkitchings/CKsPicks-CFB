#!/usr/bin/env python3
"""Independently audit a V5 intended-update historical bridge artifact."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.linear_model import Ridge

from cks_picks_cfb.data.data_first_phase2d import signed_payload, verify_signed_payload
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.heads import FEATURES
from cks_picks_cfb.ratings_lab.artifacts import (
    LocalLabStore,
    R2LabStore,
    ReadOnlySource,
    ResearchStorage,
    canonical_json,
)
from cks_picks_cfb.ratings_lab.corpus import PINS, load_v5_corpus
from cks_picks_cfb.rebuild.successor_sources import (
    corrected_parents,
    historical_frames,
    rebuild_run,
)

SEASONS = (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _historical_features_from_sources(
    cache: Path | None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if cache is not None:
        return (
            pd.read_parquet(cache / "population.parquet"),
            pd.read_parquet(cache / "observations.parquet"),
            pd.read_parquet(cache / "v5_features.parquet"),
        )
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise ValueError("independent source verification requires R2")
    names = ("BUCKET", "ACCOUNT_ID", "ACCESS_KEY", "SECRET_KEY")
    config = {name: os.getenv(f"CFB_R2_PREVIEW_{name}") for name in names}
    if not all(config.values()):
        raise ValueError("Preview read credentials are incomplete")
    source = ReadOnlySource(
        R2LabStore(
            bucket=config["BUCKET"],
            account=config["ACCOUNT_ID"],
            access=config["ACCESS_KEY"],
            secret=config["SECRET_KEY"],
            endpoint=os.getenv("CFB_R2_PREVIEW_ENDPOINT"),
        )
    )
    corpus = load_v5_corpus(
        ResearchStorage(
            source, LocalLabStore(Path("/private/tmp/v5-intended-update-verifier"))
        )
    )
    return corpus.population, corpus.observations, corpus.v5_features


def _verify_states(
    states: pd.DataFrame, population: pd.DataFrame, observations: pd.DataFrame
) -> dict[str, int]:
    keys = ["season", "game_id", "team", "role"]
    if len(states) != 35740 or states.duplicated(keys).any():
        raise ValueError("historical repaired state keys changed")
    if set(states.season.astype(int)) != set(SEASONS):
        raise ValueError("historical repaired states contain a forbidden season")
    games = population.set_index(["season", "game_id"])
    ppp = observations[observations.measurement_id.eq("ppp")]
    source = {
        (int(row.season), int(row.game_id), str(row.team), str(row.unit_role)): row
        for row in ppp.itertuples(index=False)
    }
    if len(source) != len(ppp):
        raise ValueError("source PPP observations duplicate a role key")
    used = 0
    fallback = 0
    for row in states.itertuples(index=False):
        key = (int(row.season), int(row.game_id))
        if key not in games.index:
            raise ValueError("rating state lacks a source game")
        game = games.loc[key]
        if row.team not in (game.home_team, game.away_team):
            raise ValueError("rating state belongs to another game")
        cutoff = pd.Timestamp(game.kickoff_utc)
        explanation = json.loads(row.explanation)
        ids = json.loads(row.evidence_game_ids)
        contributions = explanation.get("evidence_contributions") or []
        if ids != [int(item["game_id"]) for item in contributions] or len(ids) != len(
            set(ids)
        ):
            raise ValueError("rating explanation duplicates or omits a source game")
        exposure = 0.0
        contribution_sum = 0.0
        for item in contributions:
            source_key = (
                int(row.season),
                int(item["game_id"]),
                str(row.team),
                str(row.role),
            )
            measurement = source.get(source_key)
            origin = games.loc[(int(row.season), int(item["game_id"]))]
            if (
                measurement is None
                or int(origin.week) >= int(game.week)
                or pd.Timestamp(origin.kickoff_utc) + pd.Timedelta(hours=6) > cutoff
                or pd.isna(measurement.denominator)
                or float(measurement.denominator) <= 0
            ):
                raise ValueError("rating explanation uses unavailable evidence")
            amount = float(item["exposure"])
            if abs(amount - float(measurement.denominator)) > 1e-9:
                raise ValueError(
                    "source-game exposure differs from certified measurement"
                )
            exposure += amount
            contribution_sum += float(item["contribution"])
            used += 1
        if abs(exposure - float(row.usable_exposure)) > 1e-9:
            raise ValueError("rating state exposure does not equal source-game sum")
        if "fcs_fallback" in explanation:
            fallback += 1
            continue
        variance = 1 / (1 / float(row.prior_variance) + exposure / 8)
        prior_component = variance * float(row.prior_mean) / float(row.prior_variance)
        if (
            abs(float(row.variance) - variance) > 1e-9
            or abs(float(row.mean) - prior_component - contribution_sum) > 1e-9
            or abs(
                float(explanation["prior_weight"])
                - variance / float(row.prior_variance)
            )
            > 1e-9
        ):
            raise ValueError(
                "rating update differs from one shrink of source-game evidence"
            )
    return {
        "states": len(states),
        "source_game_role_contributions": used,
        "fcs_fallback_states": fallback,
    }


def _verify_bundle(
    bundle: dict[str, Any], accepted: pd.DataFrame, states: pd.DataFrame
) -> dict[str, int]:
    if bundle.get("schema_version") != "v5_inference_bundle_v1" or bundle.get(
        "feature_order"
    ) != list(FEATURES):
        raise ValueError("inference bundle schema or feature order changed")
    if bundle.get("development_seasons") != list(SEASONS):
        raise ValueError("inference bundle training seasons changed")
    if set(bundle.get("targets", {})) != {"margin", "total"}:
        raise ValueError("inference bundle lacks a target")
    frame = accepted.copy()
    for side in ("home", "away"):
        for role in ("offense", "defense"):
            name = f"{side}_{role}"
            part = states[states.role.eq(role)][
                ["season", "game_id", "team", "mean"]
            ].rename(columns={"team": f"{side}_team", "mean": name})
            frame = frame.drop(columns=name).merge(
                part, on=["season", "game_id", f"{side}_team"], validate="one_to_one"
            )
    if len(frame) != len(accepted) or frame[list(FEATURES)].isna().any().any():
        raise ValueError("bridge fit frame changed game population")
    counts = {}
    for target in ("margin", "total"):
        spec = bundle["targets"][target]
        if float(spec["alpha"]) != 10 or spec["head"] != "reference":
            raise ValueError("successor changed the frozen alpha-10 reference head")
        names = list(spec["feature_names"])
        clean = frame.dropna(subset=[f"actual_{target}", f"offset_{target}", *FEATURES])
        centers = clean[list(FEATURES)].mean()
        scales = clean[list(FEATURES)].std(ddof=0).clip(lower=0.05)
        x = (clean[names] - centers[names]) / scales[names]
        y = clean[f"actual_{target}"].to_numpy(float) - clean[
            f"offset_{target}"
        ].to_numpy(float)
        fitted = Ridge(alpha=10).fit(x.to_numpy(float), y)
        if (
            names
            != [
                name
                for name in FEATURES
                if ((clean[name] - centers[name]) / scales[name]).nunique(dropna=False)
                > 1
            ]
            or max(
                abs(float(spec["center"][name]) - float(centers[name]))
                for name in names
            )
            > 1e-12
            or max(
                abs(float(spec["scale"][name]) - float(scales[name])) for name in names
            )
            > 1e-12
            or not np.allclose(spec["coefficients"], fitted.coef_, atol=1e-10, rtol=0)
            or abs(float(spec["intercept"]) - float(fitted.intercept_)) > 1e-10
            or int(spec["training_rows"]) != len(clean)
        ):
            raise ValueError(
                "exported bridge coefficients differ from independent refit"
            )
        errors = []
        for season in SEASONS:
            if season < 2017:
                continue
            train = frame[frame.season.lt(season)]
            test = frame[frame.season.eq(season)]
            c = train[list(FEATURES)].mean()
            s = train[list(FEATURES)].std(ddof=0).clip(lower=0.05)
            varying = [
                name
                for name in FEATURES
                if ((train[name] - c[name]) / s[name]).nunique(dropna=False) > 1
            ]
            model = Ridge(alpha=10).fit(
                ((train[varying] - c[varying]) / s[varying]).to_numpy(float),
                train[f"actual_{target}"].to_numpy(float)
                - train[f"offset_{target}"].to_numpy(float),
            )
            prediction = model.predict(
                ((test[varying] - c[varying]) / s[varying]).to_numpy(float)
            )
            errors.extend(
                (
                    test[f"actual_{target}"].to_numpy(float)
                    - test[f"offset_{target}"].to_numpy(float)
                    - prediction
                ).tolist()
            )
        variance = max(float(np.mean(np.square(errors))), 1e-6)
        if abs(float(spec["calibration_variance"]) - variance) > 1e-9:
            raise ValueError(
                "exported interval variance differs from earlier-only refit"
            )
        counts[target] = len(errors)
    return counts


def verify(
    *,
    manifest_raw: bytes,
    state_raw: bytes,
    bundle_raw: bytes,
    cache: Path | None = None,
    corrected_lock: Path | None = None,
) -> dict[str, Any]:
    manifest = json.loads(manifest_raw)
    verify_signed_payload(manifest, label="intended-update bridge")
    if (
        manifest.get("schema_version") != "v5_intended_update_bridge_manifest_v1"
        or manifest.get("state") != "frozen"
    ):
        raise ValueError("unknown or incomplete intended-update bridge manifest")
    if manifest.get("production_activation_authorized") is not False:
        raise ValueError("bridge artifact cannot authorize a production release")
    if corrected_lock is None:
        for name, (uri, digest) in PINS.items():
            if manifest["parents"].get(name) != {"uri": uri, "raw_sha256": digest}:
                raise ValueError("certified historical parent changed")
    else:
        lock_raw = corrected_lock.read_bytes()
        if manifest["parents"] != corrected_parents(json.loads(lock_raw), lock_raw):
            raise ValueError("corrected bridge parents differ from the source lock")
    refs = manifest["output_refs"]
    if (
        _sha(state_raw) != refs["historical_states"]["raw_sha256"]
        or _sha(bundle_raw) != refs["inference_bundle"]["raw_sha256"]
    ):
        raise ValueError("stored bridge child checksum differs")
    states = pd.read_parquet(io.BytesIO(state_raw))
    bundle = json.loads(bundle_raw)
    if corrected_lock is not None:
        frames = historical_frames(
            rebuild_run(get_storage(environment="preview"), json.loads(lock_raw))
        )
        population, observations, accepted = (
            frames["population"],
            frames["observations"],
            frames["v5_features"],
        )
    else:
        population, observations, accepted = _historical_features_from_sources(cache)
    state_checks = _verify_states(states, population, observations)
    calibration = _verify_bundle(bundle, accepted, states)
    if state_checks["states"] != int(refs["historical_states"]["rows"]):
        raise ValueError("manifest state count differs")
    if calibration != manifest["calibration_counts"]:
        raise ValueError("manifest calibration counts differ")
    return signed_payload(
        {
            "schema_version": "v5_intended_update_bridge_verification_v1",
            "state": "verified",
            "bridge_manifest_raw_sha256": _sha(manifest_raw),
            "historical_states_raw_sha256": _sha(state_raw),
            "inference_bundle_raw_sha256": _sha(bundle_raw),
            "state_checks": state_checks,
            "calibration_counts": calibration,
            "production_activation_authorized": False,
        }
    )


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-uri")
    parser.add_argument("--local-output", type=Path)
    parser.add_argument("--historical-cache", type=Path)
    parser.add_argument(
        "--corrected-lock",
        type=Path,
        help="verify against the published corrected rebuild named by this lock",
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if bool(args.manifest_uri) == bool(args.local_output):
        raise ValueError("provide one manifest URI or local output directory")
    if args.apply and (args.local_output or args.historical_cache):
        raise ValueError(
            "immutable verifier must re-read Preview R2 artifacts and sources"
        )
    storage = get_storage(environment="preview") if args.manifest_uri else None
    if storage:
        raw = storage.read_bytes(args.manifest_uri)
        manifest = json.loads(raw)
        refs = manifest["output_refs"]
        state_raw = storage.read_bytes(refs["historical_states"]["uri"])
        bundle_raw = storage.read_bytes(refs["inference_bundle"]["uri"])
    else:
        root = args.local_output
        raw = (root / "bridge-manifest.json").read_bytes()
        state_raw = (root / "historical-states.parquet").read_bytes()
        bundle_raw = (root / "bundle.json").read_bytes()
    result = verify(
        manifest_raw=raw,
        state_raw=state_raw,
        bundle_raw=bundle_raw,
        cache=args.historical_cache,
        corrected_lock=args.corrected_lock,
    )
    if args.apply:
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain=v1"], text=True
        ).strip()
        if dirty:
            raise ValueError("verifier publication requires clean committed code")
        uri = (
            f"{args.manifest_uri.rsplit('/', 1)[0]}/verification/verifier-manifest.json"
        )
        payload = canonical_json(result)
        if storage.exists(uri):
            if storage.read_bytes(uri) != payload:
                raise ValueError("immutable verifier object collision")
        else:
            storage.write_bytes(payload, uri)
        print(json.dumps({"verification_uri": uri, "raw_sha256": _sha(payload)}))
    else:
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
