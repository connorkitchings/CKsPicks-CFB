"""Research-only CLI. Every write needs --apply and explicit lab credentials."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv

from cks_picks_cfb.ratings_lab.artifacts import ResearchStorage, open_research_storage
from cks_picks_cfb.ratings_lab.contracts import Observation, Rating, RatingState
from cks_picks_cfb.ratings_lab.corpus import (
    PINS,
    load_persisted_corpus,
    load_v5_corpus,
    persist_corpus,
)
from cks_picks_cfb.ratings_lab.evaluation import (
    common_bridge_predictions,
    frame_with_candidate_states,
    frozen_v5_predictions,
    paired_comparison,
    scorecard,
)
from cks_picks_cfb.ratings_lab.measurements import (
    MeasurementRecipe,
    build_cumulative,
    build_individual,
    observation_frame,
    terminal_standardized_seeds,
)
from cks_picks_cfb.ratings_lab.replay import REGISTRY, register, replay
from cks_picks_cfb.ratings_lab.stages import (
    read_frame_stage,
    write_frame_stage,
    write_report,
)
from cks_picks_cfb.ratings_lab.updaters import load_candidate_configs

ROOT = Path(__file__).resolve().parents[2]
_CANDIDATES_DIR = ROOT / "conf/research/candidates"


def _hashes() -> tuple[str, str]:
    package = ROOT / "src/cks_picks_cfb/ratings_lab"
    digest = hashlib.sha256()
    for path in sorted(package.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    lock = ROOT / "uv.lock"
    return digest.hexdigest(), hashlib.sha256(lock.read_bytes()).hexdigest()


def _load_yaml_candidates() -> None:
    """Load YAML candidate files and register them into REGISTRY."""
    yaml_candidates = load_candidate_configs(
        _CANDIDATES_DIR, existing_ids=set(REGISTRY)
    )
    for design in yaml_candidates.values():
        register(design)


def _manifest(storage: ResearchStorage, key: str, stage: str):
    ref, payload = storage.stage_at(key)
    if payload["stage"] != stage:
        raise ValueError(f"expected {stage} stage")
    return ref


def _require_parent(storage: ResearchStorage, ref, name: str, expected: str) -> None:
    _, payload = storage.stage_at(ref.key)
    if payload["metadata"]["parents"].get(name) != expected:
        raise ValueError(f"{payload['stage']} stage has a different {name} parent")


def _observations(frame: pd.DataFrame) -> list[Observation]:
    rows = []
    for raw in frame.to_dict("records"):
        contributors = raw.get("contributors")
        raw["contributors"] = (
            tuple(contributors)
            if hasattr(contributors, "__iter__") and not isinstance(contributors, str)
            else ()
        )
        if pd.isna(raw.get("value")):
            raw["value"] = None
        if pd.isna(raw.get("missing_reason")):
            raw["missing_reason"] = None
        rows.append(Observation(**raw))
    return rows


def _states(frame: pd.DataFrame) -> list[RatingState]:
    return [
        RatingState(
            row.candidate_id,
            int(row.season),
            int(row.week),
            int(row.game_id),
            row.cutoff_utc,
            row.team,
            row.role,
            Rating(
                float(row.rating_mean),
                None if pd.isna(row.rating_variance) else float(row.rating_variance),
            ),
            Rating(
                float(row.prior_mean),
                None if pd.isna(row.prior_variance) else float(row.prior_variance),
            ),
            float(row.usable_exposure),
            tuple(json.loads(row.evidence_game_ids)),
            json.loads(row.explanation),
        )
        for row in frame.itertuples(index=False)
    ]


def _state_frame(states: list[RatingState]) -> pd.DataFrame:
    return pd.DataFrame.from_records(
        [
            {
                "candidate_id": row.candidate_id,
                "season": row.season,
                "week": row.week,
                "game_id": row.game_id,
                "cutoff_utc": row.cutoff_utc,
                "team": row.team,
                "role": row.role,
                "rating_mean": row.rating.mean,
                "rating_variance": row.rating.variance,
                "prior_mean": row.prior.mean,
                "prior_variance": row.prior.variance,
                "usable_exposure": row.usable_exposure,
                "evidence_game_ids": json.dumps(row.evidence_game_ids),
                "explanation": json.dumps(row.explanation, sort_keys=True),
            }
            for row in states
        ]
    )


def _print(value: object) -> None:
    print(json.dumps(value, sort_keys=True, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Versioned, isolated ratings research")
    parser.add_argument(
        "--config",
        default=str(
            Path(__file__).resolve().parents[2]
            / "conf/research/ratings_lab_v1/protocol.yaml"
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in (
        "validate",
        "import-corpus",
        "build-measurements",
        "replay",
        "evaluate",
        "compare",
        "explain",
        "status",
    ):
        cmd = commands.add_parser(name)
        if name in {"build-measurements", "replay", "evaluate", "compare"}:
            cmd.add_argument("--corpus-key", required=True)
        if name in {"replay", "evaluate", "compare", "explain", "status"}:
            cmd.add_argument("--stage-key", required=True)
        if name == "compare":
            cmd.add_argument("--reference-key")
        if name == "build-measurements":
            cmd.add_argument("--recipe", default="v5_raw_ppp_game_v1")
            cmd.add_argument("--measurement-id", default="ppp")
        if name == "replay":
            cmd.add_argument("--candidate", default="carryover_only_rho_0_60_v1")
            cmd.add_argument("--measurement-id", default="ppp")
        if name == "evaluate":
            cmd.add_argument("--candidate", default="carryover_only_rho_0_60_v1")
        if name == "explain":
            for field in ("season", "game_id", "team", "role"):
                cmd.add_argument(
                    f"--{field.replace('_', '-')}",
                    required=True,
                    type=int if field in {"season", "game_id"} else str,
                )
        if name in {
            "import-corpus",
            "build-measurements",
            "replay",
            "evaluate",
            "compare",
        }:
            cmd.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    _load_yaml_candidates()
    config_raw = Path(args.config).read_bytes()
    protocol = yaml.safe_load(config_raw)
    if (
        protocol.get("protocol_id") != "ratings_lab_historical_v1"
        or protocol.get("development_seasons")
        != [2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025]
        or protocol.get("availability_policy") != "v5_later_week_6h_v1"
        or protocol.get("headline_seasons") != [2022, 2023, 2024, 2025]
        or protocol.get("timing_class") != "historically_reconstructed"
        or protocol.get("measurement_recipe")
        not in {"v5_raw_ppp_game_v1", "v6_4factor_game_v1"}
        or protocol.get("bridge") != "alpha10_expanding_v1"
        or protocol.get("calibration") != "earlier_rolling_residual_v1"
        or protocol.get("bootstrap_seed") != 20260928
        or protocol.get("bootstrap_replicates") != 2000
        or protocol.get("research_prefix") != "ratings-lab/v1/"
    ):
        raise ValueError("unsupported ratings laboratory protocol")
    config_sha = hashlib.sha256(config_raw).hexdigest()
    load_dotenv()
    storage = open_research_storage()
    code_sha, lock_sha = _hashes()
    if args.command == "validate":
        for name, (key, digest) in PINS.items():
            storage.read_source(key=key, expected_sha256=digest)
        _print(
            {
                "source": storage.source.identity,
                "output": storage.output.identity,
                "pinned_parents": list(PINS),
                "code_sha": code_sha,
                "lock_sha": lock_sha,
                "config_sha": config_sha,
            }
        )
        return 0
    if args.command == "status":
        _, payload = storage.stage_at(args.stage_key)
        _print(
            {
                "key": args.stage_key,
                "stage": payload["stage"],
                "identity": payload["identity"],
                "children": len(payload["children"]),
                "metadata": payload["metadata"],
            }
        )
        return 0
    if args.command == "import-corpus":
        corpus = load_v5_corpus(storage)
        counts = {
            name: len(getattr(corpus, name))
            for name in (
                "population",
                "observations",
                "scoring_events",
                "terminal",
                "outcomes",
                "v5_predictions",
                "v5_features",
            )
        }
        if args.apply:
            ref = persist_corpus(
                storage,
                corpus,
                code_sha=code_sha,
                lock_sha=lock_sha,
                config_sha=config_sha,
            )
            _print({"manifest": ref.as_dict(), "rows": counts})
        else:
            _print({"dry_run": True, "rows": counts, "parents": corpus.parents})
        return 0
    corpus_ref = (
        _manifest(storage, args.corpus_key, "corpus")
        if hasattr(args, "corpus_key")
        else None
    )
    corpus = load_persisted_corpus(storage, corpus_ref) if corpus_ref else None
    if args.command == "build-measurements":
        recipe = MeasurementRecipe(
            recipe_id=args.recipe, measurement_id=args.measurement_id
        )
        individual = build_individual(corpus, recipe)
        cumulative = build_cumulative(corpus.games(), individual)
        frame = observation_frame(individual + cumulative)
        if args.apply:
            ref = write_frame_stage(
                storage,
                stage="measurements",
                frame=frame,
                parents={"corpus": corpus_ref.sha256},
                config={**asdict(recipe), "protocol_sha": config_sha},
                code_sha=code_sha,
                lock_sha=lock_sha,
            )
            _print(
                {
                    "manifest": ref.as_dict(),
                    "individual": len(individual),
                    "cumulative": len(cumulative),
                }
            )
        else:
            _print(
                {
                    "dry_run": True,
                    "individual": len(individual),
                    "cumulative": len(cumulative),
                }
            )
        return 0
    if args.command == "replay":
        stage_ref = _manifest(storage, args.stage_key, "measurements")
        _require_parent(storage, stage_ref, "corpus", corpus_ref.sha256)
        observations = _observations(
            read_frame_stage(storage, stage_ref, "measurements")
        )
        candidate = REGISTRY[args.candidate]
        individual = [obs for obs in observations if obs.kind == "individual"]
        states = replay(
            corpus.games(),
            observations,
            design=candidate,
            measurement_id=args.measurement_id,
            external_terminals=terminal_standardized_seeds(
                individual,
                signed_defense=(
                    args.measurement_id not in {"ppp", "raw_points_per_possession"}
                ),
            )
            if args.candidate == "carryover_only_rho_0_60_v1"
            else None,
        )
        frame = _state_frame(states)
        if args.apply:
            ref = write_frame_stage(
                storage,
                stage="ratings",
                frame=frame,
                parents={"corpus": corpus_ref.sha256, "measurements": stage_ref.sha256},
                config={
                    "candidate": args.candidate,
                    "mode": candidate.mode,
                    "measurement_id": args.measurement_id,
                    "protocol_sha": config_sha,
                },
                code_sha=code_sha,
                lock_sha=lock_sha,
            )
            _print({"manifest": ref.as_dict(), "states": len(states)})
        else:
            _print({"dry_run": True, "states": len(states)})
        return 0
    if args.command == "evaluate":
        diagnostics = None
        if args.stage_key == "frozen-v5":
            predictions = frozen_v5_predictions(corpus)
            parent = "frozen-v5"
        elif args.stage_key == "v5-common":
            predictions = common_bridge_predictions(
                corpus, corpus.v5_features, candidate_id="v5_common_alpha10_v1"
            )
            diagnostics = common_bridge_predictions(
                corpus,
                corpus.v5_features,
                candidate_id="v5_common_alpha10_v1",
                seasons=(2018, 2019, 2021),
            )
            parent = "v5-common"
        else:
            state_ref = _manifest(storage, args.stage_key, "ratings")
            _require_parent(storage, state_ref, "corpus", corpus_ref.sha256)
            states = _states(read_frame_stage(storage, state_ref, "ratings"))
            frame = frame_with_candidate_states(corpus, states)
            predictions = common_bridge_predictions(
                corpus, frame, candidate_id=args.candidate
            )
            diagnostics = common_bridge_predictions(
                corpus, frame, candidate_id=args.candidate, seasons=(2018, 2019, 2021)
            )
            parent = state_ref.sha256
        report = scorecard(predictions)
        early_report = scorecard(diagnostics) if diagnostics is not None else None
        if args.apply:
            ref = write_frame_stage(
                storage,
                stage="predictions",
                frame=predictions,
                parents={"corpus": corpus_ref.sha256, "ratings": parent},
                config={
                    "candidate": parent
                    if parent in {"frozen-v5", "v5-common"}
                    else args.candidate,
                    "bridge": "alpha10_expanding_v1",
                    "protocol_sha": config_sha,
                },
                code_sha=code_sha,
                lock_sha=lock_sha,
            )
            early_ref = (
                write_frame_stage(
                    storage,
                    stage="early-diagnostic",
                    frame=diagnostics,
                    parents={"corpus": corpus_ref.sha256, "ratings": parent},
                    config={
                        "candidate": parent
                        if parent == "v5-common"
                        else args.candidate,
                        "bridge": "alpha10_expanding_v1",
                        "protocol_sha": config_sha,
                    },
                    code_sha=code_sha,
                    lock_sha=lock_sha,
                )
                if diagnostics is not None
                else None
            )
            _print(
                {
                    "manifest": ref.as_dict(),
                    "early_manifest": early_ref.as_dict() if early_ref else None,
                    "scorecard": report,
                    "early_diagnostic": early_report,
                }
            )
        else:
            _print(
                {"dry_run": True, "scorecard": report, "early_diagnostic": early_report}
            )
        return 0
    if args.command == "compare":
        candidate_ref = _manifest(storage, args.stage_key, "predictions")
        _require_parent(storage, candidate_ref, "corpus", corpus_ref.sha256)
        candidate = read_frame_stage(storage, candidate_ref, "predictions")
        if args.reference_key:
            reference_ref = _manifest(storage, args.reference_key, "predictions")
            _require_parent(storage, reference_ref, "corpus", corpus_ref.sha256)
            reference = read_frame_stage(storage, reference_ref, "predictions")
            reference_parent = reference_ref.sha256
        else:
            reference = frozen_v5_predictions(corpus)
            reference_parent = "frozen-v5"
        report = paired_comparison(candidate, reference, corpus)
        if args.apply:
            ref = write_report(
                storage,
                report=report,
                parents={
                    "corpus": corpus_ref.sha256,
                    "candidate": candidate_ref.sha256,
                    "reference": reference_parent,
                },
                config={
                    "protocol": "expanding_alpha10_v1",
                    "bootstrap_seed": 20260928,
                    "replicates": 2000,
                    "protocol_sha": config_sha,
                },
                code_sha=code_sha,
                lock_sha=lock_sha,
            )
            _print({"manifest": ref.as_dict(), "paired": report["paired"]})
        else:
            _print({"dry_run": True, "paired": report["paired"]})
        return 0
    if args.command == "explain":
        state_ref = _manifest(storage, args.stage_key, "ratings")
        states = read_frame_stage(storage, state_ref, "ratings")
        selected = states[
            (states.season.eq(args.season))
            & (states.game_id.eq(args.game_id))
            & (states.team.eq(args.team))
            & (states.role.eq(args.role))
        ]
        if len(selected) != 1:
            raise ValueError("exactly one team-game-role state is required")
        _print(selected.iloc[0].to_dict())
        return 0
    raise AssertionError("unreachable command")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyError, ValueError) as exc:
        print(f"ratings-lab: {exc}", file=sys.stderr)
        sys.exit(2)
