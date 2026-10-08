#!/usr/bin/env python3
"""Build the versioned repaired historical ratings and through-2025 bridge.

Preflight is local and read-only. Immutable Preview R2 publication requires the
exact reviewed evidence, a clean committed checkout, and an independent verifier.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.intended_update_bundle import fit_intended_update_bundle
from cks_picks_cfb.ratings_lab.adjusted_game import CutoffAdjustment
from cks_picks_cfb.ratings_lab.artifacts import (
    LocalLabStore,
    R2LabStore,
    ReadOnlySource,
    ResearchStorage,
    canonical_json,
)
from cks_picks_cfb.ratings_lab.corpus import PINS, Corpus, load_v5_corpus
from cks_picks_cfb.ratings_lab.replay import replay
from cks_picks_cfb.ratings_lab.updaters import V5_GAME_AT_CUTOFF, V5_SNAPSHOT_STREAM
from cks_picks_cfb.ratings_lab.v5_control import (
    V5Control,
    apply_fcs_pool,
    load_v5_control,
    replay_v5_control,
)
from cks_picks_cfb.rebuild.successor_sources import (
    HISTORICAL_FRAMES,
    corrected_parents,
    historical_frames,
    rebuild_run,
)

OUTPUT_ROOT = "artifacts/research/data-first-football-v1/forecasts/intended-update/runs"
SCHEMA_VERSION = "v5_intended_update_bridge_manifest_v1"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _source(output: Path) -> ResearchStorage:
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise ValueError("intended-update bundle requires CFB_STORAGE_BACKEND=r2")
    names = ("BUCKET", "ACCOUNT_ID", "ACCESS_KEY", "SECRET_KEY")
    config = {name: os.getenv(f"CFB_R2_PREVIEW_{name}") for name in names}
    if not all(config.values()):
        raise ValueError("Preview R2 source credentials are incomplete")
    return ResearchStorage(
        ReadOnlySource(
            R2LabStore(
                bucket=config["BUCKET"],
                account=config["ACCOUNT_ID"],
                access=config["ACCESS_KEY"],
                secret=config["SECRET_KEY"],
                endpoint=os.getenv("CFB_R2_PREVIEW_ENDPOINT"),
            )
        ),
        LocalLabStore(output),
    )


def _cached(root: Path) -> tuple[Corpus, V5Control]:
    return _from_frames(
        {name: pd.read_parquet(root / f"{name}.parquet") for name in HISTORICAL_FRAMES}
    )


def _from_frames(frames: dict[str, pd.DataFrame]) -> tuple[Corpus, V5Control]:
    def frame(name: str) -> pd.DataFrame:
        return frames[name]

    corpus = Corpus(
        frame("population"),
        frame("observations"),
        pd.DataFrame(),
        frame("terminal"),
        frame("outcomes"),
        frame("v5_predictions"),
        frame("v5_features"),
        {name: {"uri": uri, "sha256": digest} for name, (uri, digest) in PINS.items()},
        {},
    )
    control = V5Control(frame("snapshots"), frame("priors"), frame("rating_states"))
    return corpus, control


def _states(
    corpus: Corpus, control: V5Control
) -> tuple[pd.DataFrame, dict[str, float]]:
    _, fidelity = replay_v5_control(corpus, control, V5_SNAPSHOT_STREAM)
    if (
        fidelity.get("max_abs_rating_mean", float("inf")) > 1e-9
        or fidelity.get("max_abs_rating_variance", float("inf")) > 1e-9
        or fidelity.get("max_abs_usable_exposure", float("inf")) > 1e-9
    ):
        raise ValueError("accepted V5 control does not reproduce certified states")
    adjuster = CutoffAdjustment(corpus, control.snapshots)
    fcs, no_predecessor = control.fcs_fallbacks(corpus)
    fixed_priors = control.fixed_priors()
    neutral_keys = {
        (season, team, role)
        for season, team in fcs
        for role in ("offense", "defense")
        if (season, team, role) not in fixed_priors
    }
    states = replay(
        corpus.games(),
        corpus.individual_observations("ppp"),
        design=V5_GAME_AT_CUTOFF,
        measurement_id="ppp_adj_game_at_cutoff_v1",
        fixed_priors=fixed_priors,
        neutral_fallback_keys=neutral_keys,
        cutoff_evidence=adjuster.game_evidence,
    )
    states = apply_fcs_pool(states, fcs=fcs, no_predecessor=no_predecessor)
    if len(states) != 35740:
        raise ValueError("repaired historical rating state population changed")
    rows = pd.DataFrame.from_records(
        [
            {
                "candidate_id": item.candidate_id,
                "season": item.season,
                "week": item.week,
                "game_id": item.game_id,
                "cutoff_utc": item.cutoff_utc,
                "team": item.team,
                "role": item.role,
                "mean": item.rating.mean,
                "variance": item.rating.variance,
                "prior_mean": item.prior.mean,
                "prior_variance": item.prior.variance,
                "usable_exposure": item.usable_exposure,
                "evidence_game_ids": json.dumps(item.evidence_game_ids),
                "explanation": canonical_json(item.explanation).decode(),
            }
            for item in states
        ]
    )
    return rows, fidelity


def build(
    *,
    run_id: str,
    output: Path,
    code_sha: str,
    cache: Path | None = None,
    corrected_lock: Path | None = None,
) -> dict[str, Any]:
    if not re.fullmatch(r"v5-intended-update-[a-z0-9-]+", run_id):
        raise ValueError("invalid intended-update run ID")
    forbidden = Path(__file__).resolve().parents[2] / "data"
    if output.resolve() == forbidden or forbidden in output.resolve().parents:
        raise ValueError("bundle output cannot use repository ./data")
    output.mkdir(parents=True, exist_ok=True)
    parents = {
        name: {"uri": uri, "raw_sha256": digest} for name, (uri, digest) in PINS.items()
    }
    if corrected_lock is not None:
        lock_raw = corrected_lock.read_bytes()
        lock = json.loads(lock_raw)
        run = rebuild_run(get_storage(environment="preview"), lock)
        corpus, control = _from_frames(historical_frames(run))
        parents = corrected_parents(lock, lock_raw)
    elif cache is None:
        storage = _source(output)
        corpus = load_v5_corpus(storage)
        control = load_v5_control(storage, corpus)
    else:
        corpus, control = _cached(cache)
    repaired, fidelity = _states(corpus, control)
    bundle, fit_frame, calibration_counts = fit_intended_update_bundle(
        corpus.v5_features, repaired
    )
    states_buffer = io.BytesIO()
    repaired.to_parquet(states_buffer, index=False, compression="zstd")
    state_raw = states_buffer.getvalue()
    bundle_raw = canonical_json(bundle)
    prefix = f"{OUTPUT_ROOT}/{run_id}"
    manifest = signed_payload(
        {
            "schema_version": SCHEMA_VERSION,
            "state": "frozen",
            "identity": {
                "run_id": run_id,
                "code_sha": code_sha,
                "environment": "preview",
                "candidate_id": V5_GAME_AT_CUTOFF.candidate_id,
            },
            "parents": parents,
            "output_refs": {
                "historical_states": {
                    "uri": f"{prefix}/historical-states.parquet",
                    "raw_sha256": _sha(state_raw),
                    "rows": len(repaired),
                },
                "inference_bundle": {
                    "uri": f"{prefix}/bundle.json",
                    "raw_sha256": _sha(bundle_raw),
                },
            },
            "accepted_v5_control_fidelity": fidelity,
            "training_rows": len(fit_frame),
            "training_seasons": sorted(set(fit_frame.season.astype(int))),
            "calibration_counts": dict(calibration_counts),
            "production_activation_authorized": False,
        }
    )
    (output / "historical-states.parquet").write_bytes(state_raw)
    (output / "bundle.json").write_bytes(bundle_raw)
    (output / "bridge-manifest.json").write_bytes(canonical_json(manifest))
    return manifest


def _write_once(storage: Any, uri: str, raw: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != raw:
            raise ValueError(f"immutable intended-update artifact collision: {uri}")
        return
    storage.write_bytes(raw, uri)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--local-output", type=Path, required=True)
    parser.add_argument("--historical-cache", type=Path)
    parser.add_argument(
        "--corrected-lock",
        type=Path,
        help="build from the published corrected rebuild named by this successor lock",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--preflight-evidence", type=Path)
    args = parser.parse_args()
    if args.apply and args.historical_cache:
        raise ValueError("immutable publication must re-read certified R2 parents")
    manifest = build(
        run_id=args.run_id,
        output=args.local_output,
        code_sha=args.expected_code_sha,
        cache=args.historical_cache,
        corrected_lock=args.corrected_lock,
    )
    if not args.apply:
        print(json.dumps(manifest, sort_keys=True))
        return
    if (
        not args.preflight_evidence
        or json.loads(args.preflight_evidence.read_bytes()) != manifest
    ):
        raise ValueError("bundle apply differs from reviewed preflight")
    actual_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain=v1"], text=True
    ).strip()
    if dirty or actual_sha != args.expected_code_sha:
        raise ValueError(
            "bundle publication requires the expected clean committed code"
        )
    storage = get_storage(environment="preview")
    refs = manifest["output_refs"]
    _write_once(
        storage,
        refs["historical_states"]["uri"],
        (args.local_output / "historical-states.parquet").read_bytes(),
    )
    _write_once(
        storage,
        refs["inference_bundle"]["uri"],
        (args.local_output / "bundle.json").read_bytes(),
    )
    uri = f"{OUTPUT_ROOT}/{args.run_id}/bridge-manifest.json"
    _write_once(storage, uri, (args.local_output / "bridge-manifest.json").read_bytes())
    print(
        json.dumps(
            {"manifest_uri": uri, "manifest_raw_sha256": _sha(storage.read_bytes(uri))}
        )
    )


if __name__ == "__main__":
    main()
