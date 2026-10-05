"""Stage 2: re-derive Silver byplay/drives/team-game/reconciliation, season by season.

Normalized Silver parents are the exact Phase 2c versions the Step 5 byplay was built
from (``conf/rebuild/phase2c_silver_parents_v1.json``, 8,936 FBS-involved games). The
corrected derivation uses nullable PPA, stream-score reconciliation and the pinned
corrections version. Each season is built in a throwaway local lake and streamed out, so
no more than one season is in memory.
"""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
from collections.abc import Iterator, Mapping
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput
from cks_picks_cfb.rebuild.plan import FORBIDDEN_SEASONS, HISTORICAL_SEASONS

DERIVED = {
    "byplay": "byplay_v1",
    "drives": "drives_v1",
    "reconciled_team_game": "team_game_v1",
    "source_reconciliation": "reconciliation_v1",
}
PARENT_ORDER = ("plays", "fbs_involved_games", "teams", "team_game_stats")
PIN_SCHEMA = "rebuild_6a_silver_parents_v1"
CORRECTIONS_DATASET = "data_corrections"
SUMMARY = "rebuild/6a/{run_id}/silver/summary.json"
PIPELINE_CONFIG = {
    "pipeline": "team_game_pipeline_v1",
    "nullable_ppa": True,
    "stream_score_reconciliation": True,
    "corrections_dataset": CORRECTIONS_DATASET,
}


def config_sha(config: Mapping[str, Any] = PIPELINE_CONFIG) -> str:
    """Config identity; includes nullable_ppa so a zero-filled build cannot collide."""
    return hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def check_capture_manifest(raw: bytes, expected: str) -> None:
    """Accept the raw-byte hash or the manifest's own signed checksum, else fail."""
    if hashlib.sha256(raw).hexdigest() == expected:
        return
    if json.loads(raw).get("manifest_sha256") == expected:
        return
    raise GateError("play capture manifest differs from the pinned source set")


def season_list(plan_seasons: tuple[int, ...]) -> list[int]:
    seasons = sorted(plan_seasons)
    if set(seasons) & set(FORBIDDEN_SEASONS) or set(seasons) != set(HISTORICAL_SEASONS):
        raise GateError("silver seasons must be exactly 2015-2019 and 2021-2025")
    return seasons


def _missing_normalized(series: pd.Series) -> pd.Series:
    """Treat NaN/None and the legacy literal strings 'nan'/'None' as one missing value."""
    out = series.astype(object).where(series.notna(), None)
    return out.where(~out.isin(["nan", "None"]), None)


def value_differences(new: pd.DataFrame, legacy: pd.DataFrame) -> dict[str, int]:
    """Per-column count of rows whose value differs after missing-value normalization."""
    if len(new) != len(legacy):
        raise GateError("cannot compare byplay frames of different length")
    diffs: dict[str, int] = {}
    for column in sorted(set(new.columns) & set(legacy.columns)):
        a = _missing_normalized(new[column].reset_index(drop=True))
        b = _missing_normalized(legacy[column].reset_index(drop=True))
        same = (a == b) | (a.isna() & b.isna())
        if count := int((~same).sum()):
            diffs[column] = count
    return diffs


#: Documented, bounded change: CFBD ``Punt Return`` rows used to count as plays
#: (``st == 0``) and are now tagged special teams (known issue 2, fix ``5acd051``).
PUNT_FIX_COLUMNS = ("st", "st_punt")


def punt_return_fix(new: pd.DataFrame, legacy: pd.DataFrame) -> dict[str, Any]:
    """Describe rows whose special-teams flags changed and whether they fit the fix."""
    if len(new) != len(legacy):
        raise GateError("cannot compare byplay frames of different length")
    a, b = new.reset_index(drop=True), legacy.reset_index(drop=True)
    changed = pd.Series(False, index=a.index)
    for column in PUNT_FIX_COLUMNS:
        changed |= a[column].astype(object) != b[column].astype(object)
    rows = int(changed.sum())
    fits = bool(
        rows == 0
        or (
            (a.loc[changed, "play_type"] == "Punt Return").all()
            and all(
                ((b.loc[changed, c] == 0) & (a.loc[changed, c] == 1)).all()
                for c in PUNT_FIX_COLUMNS
            )
        )
    )
    return {"rows": rows, "fits_punt_return_fix": fits}


def _ref(entry: Mapping[str, Any]):
    from cks_picks_cfb.data.lake import DatasetRef

    return DatasetRef(
        dataset=entry["dataset"],
        version_id=entry["version_id"],
        schema_version=entry["schema_version"],
        content_sha=entry["content_sha"],
        uri=entry["uri"],
    )


def _season_pin(
    context: StageContext, pin_file: Mapping[str, Any], season: int
) -> tuple[Mapping[str, Any], list]:
    """Pinned parent refs for one season, in the legacy build's parent order."""
    if pin_file.get("schema_version") != PIN_SCHEMA:
        raise GateError("silver parent pin file has the wrong schema")
    entry = (pin_file.get("seasons") or {}).get(str(season))
    if entry is None:
        raise GateError(f"silver parent pin file lacks season {season}")
    order = (*PARENT_ORDER, CORRECTIONS_DATASET)
    by_name = {item["dataset"]: item for item in entry["parents"]}
    if set(by_name) != set(order) or len(entry["parents"]) != len(order):
        raise GateError(f"{season}: parent pin must be exactly {list(order)}")
    corrections = context.plan.policies["corrections_ref"]
    if (
        by_name[CORRECTIONS_DATASET]["version_id"] != corrections["version_id"]
        or by_name[CORRECTIONS_DATASET]["content_sha"] != corrections["content_sha"]
    ):
        raise GateError(f"{season}: corrections parent differs from the plan policy")
    return entry, [_ref(by_name[name]) for name in order]


def legacy_parity(
    storage, entry: Mapping[str, Any], outputs: Mapping[str, pd.DataFrame]
) -> dict[str, Any]:
    """Like-for-like counts and per-game reconciliation classes against the legacy build."""
    from cks_picks_cfb.data.lake import read_dataset

    legacy = {
        name: read_dataset(storage, _ref(entry["legacy_comparison"][name]))
        for name in ("drives", "reconciled_team_game", "source_reconciliation")
    }
    new_rec = outputs["source_reconciliation"][["game_id", "classification"]]
    merged = new_rec.merge(
        legacy["source_reconciliation"][["game_id", "classification"]],
        on="game_id",
        how="outer",
        suffixes=("_new", "_legacy"),
        indicator=True,
    )
    mismatched = merged[
        (merged["_merge"] != "both")
        | (merged["classification_new"] != merged["classification_legacy"])
    ]
    return {
        "drives_rows_equal": len(outputs["drives"]) == len(legacy["drives"]),
        "team_game_rows_equal": len(outputs["reconciled_team_game"])
        == len(legacy["reconciled_team_game"]),
        "reconciliation_rows_equal": len(new_rec)
        == len(legacy["source_reconciliation"]),
        "reconciliation_class_mismatches": int(len(mismatched)),
    }


def derive_season(
    storage, context: StageContext, pin_file, source_set, season: int, work: Path
) -> tuple[dict[str, Any], list[tuple[str, bytes]]]:
    from cks_picks_cfb.data.history_play_capture import (
        manifest_declared_missing_game_ids,
    )
    from cks_picks_cfb.data.lake import (
        BuildRequest,
        build_dataset_version,
        read_dataset,
    )
    from cks_picks_cfb.data.reconciliation import (
        reconcile_completed_games,
        stream_points_by_team_game,
    )
    from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
    from cks_picks_cfb.data.storage.local import LocalStorage
    from cks_picks_cfb.features.pipeline import build_preaggregation_pipeline

    entry, parents = _season_pin(context, pin_file, season)
    frames = {ref.dataset: read_dataset(storage, ref) for ref in parents}
    games = frames["fbs_involved_games"].rename(columns={"kickoff_utc": "start_date"})
    byplay, drives, team_game, _ = build_preaggregation_pipeline(
        frames["plays"],
        games_df=games,
        teams_df=frames.get("teams"),
        venues_df=None,
        weather_df=None,
        corrections_df=frames.get(CORRECTIONS_DATASET),
        nullable_ppa=PIPELINE_CONFIG["nullable_ppa"],
    )
    plays_entry = [
        e
        for e in source_set["entries"]
        if int(e["season"]) == season and e["entity"] == "plays"
    ]
    if len(plays_entry) != 1:
        raise GateError(f"source set must hold exactly one {season} plays entry")
    manifest_uri = plays_entry[0]["manifest_uri"]
    check_capture_manifest(
        storage.read_bytes(manifest_uri), plays_entry[0]["manifest_sha256"]
    )
    declared = manifest_declared_missing_game_ids(storage, manifest_uri, season=season)
    reconciliation = reconcile_completed_games(
        games,
        team_game.merge(
            stream_points_by_team_game(byplay), on=["game_id", "team"], how="left"
        ),
        frames.get("team_game_stats"),
        declared_incomplete_game_ids=declared,
    )
    outputs = {
        "byplay": byplay,
        "drives": drives,
        "reconciled_team_game": team_game,
        "source_reconciliation": reconciliation,
    }
    as_of = datetime.fromisoformat(
        context.plan.policies["silver_as_of"].replace("Z", "+00:00")
    )
    local = LocalStorage(str(work))
    files: list[tuple[str, bytes]] = []
    summary: dict[str, Any] = {
        "season": season,
        "datasets": {},
        "declared_missing_games": len(declared),
        "games": int(len(games)),
    }
    for dataset, frame in outputs.items():
        validate_frame(frame, schema_for(dataset, DERIVED[dataset]))
        ref, manifest = build_dataset_version(
            local,
            build=BuildRequest(
                dataset=dataset,
                parent_refs=tuple(parents),
                code_sha=context.code_sha,
                config_sha=config_sha(),
                as_of=as_of,
                schema_version=DERIVED[dataset],
                tier="silver",
            ),
            records=frame.to_dict("records"),
            partitions={"seasons": [season]},
            validation={
                "nonempty": not frame.empty,
                "no_blocking_conflicts": not (
                    dataset == "source_reconciliation"
                    and frame["blocking"].fillna(True).any()
                ),
            },
        )
        base = ref.uri.rsplit("/", 1)[0]
        keys = [f"{base}/data.parquet", f"{base}/manifest.json"]
        for key in keys:
            files.append((key, (work / key).read_bytes()))
        summary["datasets"][dataset] = {
            "ref": asdict(ref),
            "rows": int(len(frame)),
            "keys": keys,
            "manifest_sha256": hashlib.sha256(
                (work / keys[1]).read_bytes()
            ).hexdigest(),
        }
    legacy = read_dataset(storage, _ref(entry["legacy_comparison"]["byplay"]))
    summary["ppa"] = {
        "rows": int(len(byplay)),
        "legacy_rows": int(len(legacy)),
        "rows_equal": len(byplay) == len(legacy),
        "columns_equal": sorted(byplay.columns) == sorted(legacy.columns),
        "null_ppa": int(byplay["ppa"].isna().sum()),
        "legacy_null_ppa": int(legacy["ppa"].isna().sum()),
        "legacy_zero_ppa": int((legacy["ppa"] == 0).sum()),
    }
    summary["value_differences"] = value_differences(byplay, legacy)
    summary["punt_return_fix"] = punt_return_fix(byplay, legacy)
    summary["reconciliation"] = {
        "classifications": {
            str(k): int(v)
            for k, v in reconciliation["classification"].value_counts().items()
        },
        "blocking": int(reconciliation["blocking"].fillna(True).sum()),
    }
    summary["legacy_parity"] = legacy_parity(storage, entry, outputs)
    summary["parents"] = [r.version_id for r in parents]
    return summary, files


def build(context: StageContext) -> StageOutput:
    from dotenv import load_dotenv

    load_dotenv()
    from cks_picks_cfb.data.storage import get_storage
    from cks_picks_cfb.data.storage.base import StorageSettings

    settings = StorageSettings.from_env(environment="preview")
    if f"r2:{settings.account_id}:{settings.bucket}" != context.plan.storage_identity:
        raise GateError("storage identity differs from the plan")
    storage = get_storage(environment="preview")
    source_set = json.loads(context.read_input("r1_source_set"))
    pin_file = json.loads(context.read_input("phase2c_silver_parents"))
    if source_set.get("state") != "complete":
        raise GateError("R1 source set must be complete")
    seasons = season_list(context.plan.seasons)
    prefix = SUMMARY.format(run_id=context.plan.run_id)
    summaries: list[dict[str, Any]] = []

    def artifacts() -> Iterator[tuple[str, bytes]]:
        for season in seasons:
            with tempfile.TemporaryDirectory(prefix=f"6a-silver-{season}-") as tmp:
                summary, files = derive_season(
                    storage, context, pin_file, source_set, season, Path(tmp)
                )
                summaries.append(summary)
                yield from files
        yield (
            prefix,
            json.dumps(
                {
                    "config": PIPELINE_CONFIG,
                    "config_sha": config_sha(),
                    "seasons": summaries,
                },
                indent=2,
                sort_keys=True,
            ).encode(),
        )

    return StageOutput(artifacts=artifacts(), metrics={"seasons": len(seasons)})


def verify(context: StageContext) -> list[str]:
    """Independently re-check staged datasets against their manifests and pins."""
    from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame

    stage = context.stage.name
    summary = json.loads(
        context.read_artifact(stage, SUMMARY.format(run_id=context.plan.run_id))
    )
    problems: list[str] = []
    if summary["config_sha"] != config_sha() or not summary["config"]["nullable_ppa"]:
        problems.append("silver config is not the nullable-PPA stream-reconciled build")
    found = sorted(item["season"] for item in summary["seasons"])
    if found != sorted(HISTORICAL_SEASONS):
        problems.append(f"seasons built {found}")
    any_null_ppa = False
    for item in summary["seasons"]:
        season = item["season"]
        if item["reconciliation"]["blocking"]:
            problems.append(f"{season}: blocking reconciliation rows")
        if not item["ppa"]["rows_equal"]:
            problems.append(f"{season}: byplay rows differ from legacy")
        parity = item["legacy_parity"]
        for name in (
            "drives_rows_equal",
            "team_game_rows_equal",
            "reconciliation_rows_equal",
        ):
            if not parity[name]:
                problems.append(f"{season}: {name} is false against the legacy build")
        if parity["reconciliation_class_mismatches"]:
            problems.append(f"{season}: reconciliation classes differ from legacy")
        any_null_ppa = any_null_ppa or item["ppa"]["null_ppa"] > 0
        differences = item["value_differences"]
        fix = item["punt_return_fix"]
        if unexplained := set(differences) - {"ppa", *PUNT_FIX_COLUMNS}:
            problems.append(
                f"{season}: unexplained byplay value changes {sorted(unexplained)}"
            )
        for column in PUNT_FIX_COLUMNS:
            if differences.get(column, 0) != fix["rows"]:
                problems.append(f"{season}: {column} changes differ from the punt fix")
        if not fix["fits_punt_return_fix"]:
            problems.append(f"{season}: special-teams changes are not the punt fix")
        if item["value_differences"].get("ppa") != item["ppa"]["null_ppa"]:
            problems.append(f"{season}: ppa changes are not exactly the nulled values")
        for dataset, info in item["datasets"].items():
            data_key, manifest_key = info["keys"]
            data = context.read_artifact(stage, data_key)
            manifest = json.loads(context.read_artifact(stage, manifest_key))
            if hashlib.sha256(data).hexdigest() != manifest["content_sha"]:
                problems.append(f"{season}/{dataset}: data hash != manifest")
            if manifest["config_sha"] != config_sha():
                problems.append(f"{season}/{dataset}: wrong config sha")
            if list(manifest["parent_versions"]) != item["parents"]:
                problems.append(f"{season}/{dataset}: parent versions differ")
            frame = pd.read_parquet(io.BytesIO(data))
            if len(frame) != info["rows"] or manifest["row_count"] != info["rows"]:
                problems.append(f"{season}/{dataset}: row count mismatch")
            validate_frame(frame, schema_for(dataset, DERIVED[dataset]))
            if (
                dataset == "byplay"
                and int(frame["ppa"].isna().sum()) != item["ppa"]["null_ppa"]
            ):
                problems.append(f"{season}: null PPA count differs from the summary")
    if not any_null_ppa:
        problems.append("no null PPA in any season: nullable mode not in effect")
    return problems
