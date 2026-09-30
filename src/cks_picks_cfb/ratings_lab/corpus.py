"""Import the exact accepted V5 historical evidence as a research corpus."""

from __future__ import annotations

import io
import json
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any

import pandas as pd

from cks_picks_cfb.audit.corpus import concat_all, read_any
from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.lake import read_dataset
from cks_picks_cfb.forecast.final_historical_scorecard import (
    EXPECTED_ROWS_BY_SEASON,
    EXPECTED_TOTAL_GAMES,
    EXPECTED_TOTAL_ROWS,
)
from cks_picks_cfb.forecast.live_sources import _historical_features
from cks_picks_cfb.ratings.possession_rating_materializer import _core_eligibility_refs

from .artifacts import ResearchArtifact, ResearchStorage, canonical_json, sha256
from .contracts import DEVELOPMENT_SEASONS, Game, Observation

BASE = "artifacts/research/data-first-football-v1/"
PINS = {
    "forecast": (
        BASE + "forecasts/runs/forecast-v1-20260921-5afd577-11c/forecast-manifest.json",
        "186f4dc1b0cadeee3ae1ad0a021bcd40a8dd2a027d93fe8b0f6c73cc018d521e",
    ),
    "verification": (
        BASE
        + "forecasts/runs/forecast-v1-20260921-5afd577-11c/verification/verifier-manifest.json",
        "ba60166bab17189209adca91e043338337b1a895c2d1637495abf1fa94ae0246",
    ),
    "measurement": (
        BASE
        + "possession-v1/measurements/runs/possession-v1-measurements-20260921-r9/measurement-manifest.json",
        "10b380d69524d20ce694833821d0a309a60c532d4eca05d8e8129200461dbf56",
    ),
    "rating": (
        BASE
        + "possession-v1/ratings/runs/possession-v1-ratings-20260921-11d59ee-r9cert/retained-rating-manifest.json",
        "9d00e63564691c0323fa203b76b4ee49a9fff5aa945fdb8fa000142f640e4ba0",
    ),
    "repair": (
        BASE + "repair/v2/runs/repair-v2-20260909T1417Z/repair-manifest.json",
        "b55af0dd7952a4b5e0d663b82182b351ec5496a292246a934a857c354058e0b4",
    ),
}


@dataclass
class Corpus:
    population: pd.DataFrame
    observations: pd.DataFrame
    scoring_events: pd.DataFrame
    terminal: pd.DataFrame
    outcomes: pd.DataFrame
    v5_predictions: pd.DataFrame
    v5_features: pd.DataFrame
    parents: dict[str, dict[str, str]]
    lower_level_refs: dict[int, dict[str, Any]]
    storage: Any = None
    byplay: pd.DataFrame | None = None

    def read_byplay(self, season: int | None = None) -> pd.DataFrame:
        if self.byplay is not None:
            if season is not None:
                return self.byplay[self.byplay["season"].eq(season)].copy()
            return self.byplay.copy()
        if self.storage is None:
            raise ValueError(
                "Corpus has no storage attached to read lower-level byplay"
            )
        from cks_picks_cfb.data.lake import DatasetRef, read_dataset

        source = (
            self.storage.source if hasattr(self.storage, "source") else self.storage
        )
        seasons = (
            [season] if season is not None else sorted(self.lower_level_refs.keys())
        )
        frames = []
        for s in seasons:
            ref_dict = self.lower_level_refs.get(s, {}).get("byplay")
            if not ref_dict:
                continue
            ref = DatasetRef(**ref_dict) if isinstance(ref_dict, dict) else ref_dict
            frames.append(read_dataset(source, ref))
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def games(self) -> list[Game]:
        merged = self.population.merge(
            self.outcomes[["season", "game_id", "home_points", "away_points"]],
            on=["season", "game_id"],
            how="left",
            validate="one_to_one",
        )
        return [
            Game(
                int(r.season),
                int(r.week),
                int(r.game_id),
                pd.Timestamp(r.kickoff_utc).isoformat(),
                str(r.home_team),
                str(r.away_team),
                bool(r.forecast_eligible),
                None if pd.isna(r.home_points) else float(r.home_points),
                None if pd.isna(r.away_points) else float(r.away_points),
            )
            for r in merged.itertuples(index=False)
        ]

    def individual_observations(self, measurement_id: str = "ppp") -> list[Observation]:
        selected = self.observations[
            self.observations["measurement_id"].eq(measurement_id)
        ]
        result: list[Observation] = []
        for r in selected.itertuples(index=False):
            valid = (
                str(r.coverage_status) == "observed"
                and pd.notna(r.raw_value)
                and float(r.denominator) > 0
            )
            result.append(
                Observation(
                    int(r.season),
                    int(r.week),
                    int(r.game_id),
                    str(r.team),
                    str(r.unit_role),
                    measurement_id,
                    float(r.raw_value) if valid else None,
                    float(r.denominator) if pd.notna(r.denominator) else 0.0,
                    (pd.Timestamp(r.kickoff_utc) + timedelta(hours=6)).isoformat(),
                    "historically_reconstructed",
                    missing_reason=None
                    if valid
                    else str(r.missing_reason or r.coverage_status),
                )
            )
        return result


def _load_manifest(storage: ResearchStorage, name: str) -> dict[str, Any]:
    uri, expected = PINS[name]
    raw = storage.read_source(key=uri, expected_sha256=expected)
    manifest = json.loads(raw)
    verify_signed_payload(manifest, label=name)
    return manifest


def load_v5_corpus(storage: ResearchStorage) -> Corpus:
    """Read verified parents and source outputs; no research or source writes."""
    manifests = {name: _load_manifest(storage, name) for name in PINS}
    forecast, verification = manifests["forecast"], manifests["verification"]
    if (
        verification.get("state") != "verified"
        or not verification.get("final_fit_verified")
        or verification.get("forecast_manifest_raw_sha256") != PINS["forecast"][1]
    ):
        raise ValueError("accepted V5 forecast lacks matching independent verification")
    for name in ("measurement", "rating", "repair"):
        parents = forecast.get("parents") or {}
        if (
            parents.get(f"{name}_manifest_uri") != PINS[name][0]
            or parents.get(f"{name}_manifest_raw_sha256") != PINS[name][1]
        ):
            raise ValueError(f"accepted V5 {name} parent changed")
    measurement = manifests["measurement"]
    if (
        measurement.get("certification_sha256")
        != "fc26a3d03416e688dc437ad863653dfac7df6faad51b478a7b94f466c0d870c3"
    ):
        raise ValueError("measurement certification changed")
    source = storage.source
    mrefs = measurement["output_refs"]
    frames = {
        name: concat_all(read_any(source, mrefs[name]))
        for name in ("population", "observations", "scoring_events", "terminal")
    }
    population = frames["population"]
    if (
        len(population) != 8936
        or int(population["forecast_eligible"].sum()) != 8935
        or set(population["season"].astype(int)) != set(DEVELOPMENT_SEASONS)
        or population.duplicated(["season", "game_id"]).any()
    ):
        raise ValueError("accepted population coverage changed")
    refs = _core_eligibility_refs(source, manifests["repair"])
    outcomes = pd.concat(
        [
            read_dataset(source, refs[season]["game_outcomes"])
            for season in DEVELOPMENT_SEASONS
        ],
        ignore_index=True,
    )
    outcomes = outcomes[
        ["season", "game_id", "completed", "home_points", "away_points"]
    ]
    if outcomes.duplicated(["season", "game_id"]).any():
        raise ValueError("duplicate outcome key")
    predictions = concat_all(
        read_any(source, forecast["output_refs"]["forecast_prediction"])
    )
    if (
        len(predictions) != EXPECTED_TOTAL_ROWS
        or predictions["game_id"].nunique() != EXPECTED_TOTAL_GAMES
        or predictions.groupby("season").size().to_dict()
        != {s: n * 2 for s, n in EXPECTED_ROWS_BY_SEASON.items()}
    ):
        raise ValueError("accepted V5 prediction population changed")
    v5_features = _historical_features(source, forecast)
    if len(v5_features) != 8935 or v5_features.duplicated(["season", "game_id"]).any():
        raise ValueError("accepted V5 bridge population changed")
    return Corpus(
        population,
        frames["observations"],
        frames["scoring_events"],
        frames["terminal"],
        outcomes,
        predictions,
        v5_features,
        {
            name: {"uri": uri, "sha256": digest, "storage_identity": source.identity}
            for name, (uri, digest) in PINS.items()
        },
        {
            season: {name: asdict(ref) for name, ref in sources.items()}
            for season, sources in refs.items()
        },
        storage=storage,
    )


def frame_bytes(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False, compression="zstd")
    return buffer.getvalue()


def persist_corpus(
    storage: ResearchStorage,
    corpus: Corpus,
    *,
    code_sha: str,
    lock_sha: str,
    config_sha: str = "",
) -> ResearchArtifact:
    identity = sha256(
        canonical_json(
            {
                "parents": corpus.parents,
                "code_sha": code_sha,
                "lock_sha": lock_sha,
                "config_sha": config_sha,
            }
        )
    )[:24]
    children: list[ResearchArtifact] = []
    counts: dict[str, int] = {}
    for name in (
        "population",
        "observations",
        "scoring_events",
        "terminal",
        "outcomes",
        "v5_predictions",
        "v5_features",
    ):
        frame = getattr(corpus, name)
        counts[name] = len(frame)
        for season, part in frame.groupby("season", sort=True):
            keys = [
                key
                for key in (
                    "season",
                    "week",
                    "game_id",
                    "team",
                    "unit_role",
                    "measurement_id",
                    "target",
                )
                if key in part
            ]
            data = frame_bytes(
                part.sort_values(keys, kind="mergesort") if keys else part
            )
            digest = sha256(data)
            children.append(
                storage.write(
                    key=f"ratings-lab/v1/runs/{identity}/corpus/{name}/season={int(season)}/{digest}.parquet",
                    data=data,
                )
            )
    return storage.publish_stage(
        stage="corpus",
        identity=identity,
        children=children,
        metadata={
            "parents": corpus.parents,
            "lower_level_refs": corpus.lower_level_refs,
            "row_counts": counts,
            "code_sha": code_sha,
            "lock_sha": lock_sha,
            "config_sha": config_sha,
        },
    )


def load_persisted_corpus(
    storage: ResearchStorage, manifest: ResearchArtifact
) -> Corpus:
    payload = json.loads(storage.read_output(manifest))
    if (
        payload.get("schema_version") != "ratings_lab_stage_v1"
        or payload.get("stage") != "corpus"
    ):
        raise ValueError("not a ratings laboratory corpus")
    frames: dict[str, list[pd.DataFrame]] = {}
    for child in payload["children"]:
        ref = ResearchArtifact(**child)
        name = ref.key.split("/corpus/")[1].split("/")[0]
        frames.setdefault(name, []).append(
            pd.read_parquet(io.BytesIO(storage.read_output(ref)))
        )
    required = {
        "population",
        "observations",
        "scoring_events",
        "terminal",
        "outcomes",
        "v5_predictions",
        "v5_features",
    }
    if set(frames) != required:
        raise ValueError("incomplete corpus artifact")
    data = {name: pd.concat(parts, ignore_index=True) for name, parts in frames.items()}
    return Corpus(
        **data,
        parents=payload["metadata"]["parents"],
        lower_level_refs=payload["metadata"]["lower_level_refs"],
        storage=storage,
    )
