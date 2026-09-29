"""Reproduce and compare the V5 intended-update estimators in local research output.

Reads pinned accepted V5 parents through a read-only R2 adapter. No source,
production, Neon, or public artifact writes are possible through this command.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.ratings_lab.adjusted_game import CutoffAdjustment
from cks_picks_cfb.ratings_lab.artifacts import (
    LocalLabStore,
    R2LabStore,
    ReadOnlySource,
    ResearchStorage,
    canonical_json,
    sha256,
)
from cks_picks_cfb.ratings_lab.contracts import RatingState
from cks_picks_cfb.ratings_lab.corpus import PINS, Corpus, load_v5_corpus
from cks_picks_cfb.ratings_lab.evaluation import (
    common_bridge_predictions,
    frame_with_candidate_states,
    frozen_v5_predictions,
    paired_comparison,
    scorecard,
)
from cks_picks_cfb.ratings_lab.replay import replay
from cks_picks_cfb.ratings_lab.updaters import (
    V5_GAME_AT_CUTOFF,
    V5_GAME_FIRST_BOUNDARY,
    V5_SINGLE_CUMULATIVE,
    V5_SNAPSHOT_STREAM,
)
from cks_picks_cfb.ratings_lab.v5_control import (
    V5Control,
    apply_fcs_pool,
    load_v5_control,
    replay_v5_control,
)


def _storage(root: Path) -> ResearchStorage:
    load_dotenv()
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise ValueError("V5 source requires CFB_STORAGE_BACKEND=r2")
    required = ("BUCKET", "ACCOUNT_ID", "ACCESS_KEY", "SECRET_KEY")
    config = {name: os.getenv(f"CFB_R2_PREVIEW_{name}") for name in required}
    if not all(config.values()):
        raise ValueError("Preview read-source configuration is incomplete")
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
        LocalLabStore(root),
    )


def _cached(root: Path) -> tuple[Corpus, V5Control]:
    def read(name: str) -> pd.DataFrame:
        return pd.read_parquet(root / f"{name}.parquet")

    corpus = Corpus(
        read("population"),
        read("observations"),
        pd.DataFrame(),
        read("terminal"),
        read("outcomes"),
        read("v5_predictions"),
        read("v5_features"),
        {name: {"uri": uri, "sha256": digest} for name, (uri, digest) in PINS.items()},
        {},
    )
    control = V5Control(read("snapshots"), read("priors"), read("rating_states"))
    return corpus, control


def _write_frame(root: Path, name: str, frame: pd.DataFrame) -> dict[str, object]:
    path = root / f"{name}.parquet"
    frame.to_parquet(path, index=False, compression="zstd")
    data = path.read_bytes()
    return {"file": path.name, "rows": len(frame), "sha256": sha256(data)}


def _states_frame(states: list[RatingState]) -> pd.DataFrame:
    return pd.DataFrame(
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


def run(output: Path, cache: Path | None = None) -> None:
    forbidden_data_root = Path(__file__).resolve().parents[2] / "data"
    if (
        output.resolve() == forbidden_data_root
        or forbidden_data_root in output.resolve().parents
    ):
        raise ValueError("research output cannot be repository ./data")
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    if cache is None:
        storage = _storage(output)
        corpus = load_v5_corpus(storage)
        control = load_v5_control(storage, corpus)
    else:
        corpus, control = _cached(cache)
    states_control, fidelity = replay_v5_control(corpus, control, V5_SNAPSHOT_STREAM)
    print("certified replica fidelity", fidelity, flush=True)
    raw = corpus.individual_observations("ppp")
    adjuster = CutoffAdjustment(corpus, control.snapshots)
    fcs, no_predecessor = control.fcs_fallbacks(corpus)
    fixed_priors = control.fixed_priors()
    neutral_keys = {
        (season, team, role)
        for season, team in fcs
        for role in ("offense", "defense")
        if (season, team, role) not in fixed_priors
    }
    candidates = {V5_SNAPSHOT_STREAM.candidate_id: states_control}
    for design, evidence, provider, measurement in (
        (V5_GAME_AT_CUTOFF, raw, adjuster.game_evidence, "ppp_adj_game_at_cutoff_v1"),
        (
            V5_SINGLE_CUMULATIVE,
            raw,
            adjuster.single_cumulative,
            "ppp_adj_single_cumulative_v1",
        ),
        (
            V5_GAME_FIRST_BOUNDARY,
            adjuster.first_boundary_stream(raw),
            None,
            "ppp_adj_game_first_boundary_v1",
        ),
    ):
        print("replaying", design.candidate_id, flush=True)
        states = replay(
            corpus.games(),
            evidence,
            design=design,
            measurement_id=measurement,
            fixed_priors=fixed_priors,
            neutral_fallback_keys=neutral_keys,
            cutoff_evidence=provider,
        )
        candidates[design.candidate_id] = apply_fcs_pool(
            states, fcs=fcs, no_predecessor=no_predecessor
        )
        print(
            "replayed",
            design.candidate_id,
            len(states),
            round(time.monotonic() - started, 1),
            flush=True,
        )
    artifacts = {}
    predictions = {}
    early_predictions = {}
    for name, states in candidates.items():
        artifacts[f"states_{name}"] = _write_frame(
            output, f"states_{name}", _states_frame(states)
        )
        frame = frame_with_candidate_states(corpus, states)
        preds = common_bridge_predictions(corpus, frame, candidate_id=name)
        predictions[name] = preds
        artifacts[f"predictions_{name}"] = _write_frame(
            output, f"predictions_{name}", preds
        )
        early = common_bridge_predictions(
            corpus, frame, candidate_id=name, seasons=(2018, 2019, 2021)
        )
        early_predictions[name] = early
        artifacts[f"early_predictions_{name}"] = _write_frame(
            output, f"early_predictions_{name}", early
        )
        print("bridged", name, round(time.monotonic() - started, 1), flush=True)
    reference = predictions[V5_SNAPSHOT_STREAM.candidate_id]
    comparisons = {
        name: paired_comparison(preds, reference, corpus)
        for name, preds in predictions.items()
        if name != V5_SNAPSHOT_STREAM.candidate_id
    }
    comparisons["cutoff_timing_vs_first_boundary"] = paired_comparison(
        predictions[V5_GAME_AT_CUTOFF.candidate_id],
        predictions[V5_GAME_FIRST_BOUNDARY.candidate_id],
        corpus,
    )
    frozen = frozen_v5_predictions(corpus)
    frozen_pair = reference.merge(
        frozen,
        on=["season", "week", "game_id", "target"],
        suffixes=("_research", "_frozen"),
        validate="one_to_one",
    )
    frozen_max_difference = float(
        (frozen_pair.prediction_research - frozen_pair.prediction_frozen).abs().max()
    )
    if frozen_max_difference > 1e-9:
        raise ValueError("replica bridge does not match frozen V5 forecasts")
    state_tables = {name: _states_frame(states) for name, states in candidates.items()}
    dynamic = state_tables[V5_GAME_AT_CUTOFF.candidate_id]
    cumulative = state_tables[V5_SINGLE_CUMULATIVE.candidate_id]
    paired_state = dynamic.merge(
        cumulative,
        on=["season", "week", "game_id", "team", "role"],
        suffixes=("_game", "_cumulative"),
        validate="one_to_one",
    )
    sparse_state_count = int(
        (paired_state.mean_game - paired_state.mean_cumulative).abs().gt(1e-10).sum()
    )
    missing_context_count = sum(
        contribution["missing_context_reason"] is not None
        for state in candidates[V5_GAME_AT_CUTOFF.candidate_id]
        for contribution in state.explanation.get("evidence_contributions", [])
    )
    report = {
        "schema_version": "v5_intended_update_review_v1",
        "parents": {
            name: {"uri": uri, "sha256": digest} for name, (uri, digest) in PINS.items()
        },
        "replica_fidelity": fidelity,
        "frozen_v5_bridge_max_abs_difference": frozen_max_difference,
        "sparse_graph": {
            "missing_context_contributions": missing_context_count,
            "game_vs_cumulative_different_states": sparse_state_count,
            "max_abs_state_difference": float(
                (paired_state.mean_game - paired_state.mean_cumulative).abs().max()
            ),
        },
        "metrics": {name: scorecard(preds) for name, preds in predictions.items()},
        "early_diagnostics": {
            name: scorecard(preds) for name, preds in early_predictions.items()
        },
        "comparisons": comparisons,
        "artifacts": artifacts,
    }
    payload = canonical_json(report)
    path = output / "intended_update_report.json"
    path.write_bytes(payload)
    print(
        "report",
        path,
        sha256(payload),
        "seconds",
        round(time.monotonic() - started, 1),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-output", required=True, type=Path)
    parser.add_argument(
        "--verified-cache",
        type=Path,
        help="Reuse previously verified pinned parquet inputs for local rerun",
    )
    args = parser.parse_args()
    run(args.local_output, args.verified_cache)
