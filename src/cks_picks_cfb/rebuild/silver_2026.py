"""Stage: re-derive the certified Week 4 2026 Silver with nullable PPA.

The pinned 2026 byplay was built from four parents (plays, games, teams, team game stats;
no corrections or venues). They are re-derived here exactly like the historical seasons and
compared with the legacy byplay: only ``ppa`` (and the documented punt-return flags) may
differ. 2026 scoring stays at baseline; nothing here admits a 2026 allocation change.
"""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
from collections.abc import Iterator
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from cks_picks_cfb.rebuild import silver
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput
from cks_picks_cfb.rebuild.retry import RetryingStorage

PIN_SCHEMA = "rebuild_6a_silver_2026_parents_v1"
PARENT_ORDER = ("plays", "games", "teams", "team_game_stats")
SUMMARY = "rebuild/6a/{run_id}/silver_2026/summary.json"
PIPELINE_CONFIG = {
    **silver.PIPELINE_CONFIG,
    "scope": "season_2026",
    "corrections_dataset": None,
}


def config_sha() -> str:
    return silver.config_sha(PIPELINE_CONFIG)


def pinned_parents(pin_file: dict[str, Any]) -> list:
    if pin_file.get("schema_version") != PIN_SCHEMA:
        raise GateError("2026 silver parent pin file has the wrong schema")
    by_name = {item["dataset"]: item for item in pin_file["parents"]}
    if set(by_name) != set(PARENT_ORDER) or len(pin_file["parents"]) != len(
        PARENT_ORDER
    ):
        raise GateError(f"2026 parents must be exactly {list(PARENT_ORDER)}")
    return [silver._ref(by_name[name]) for name in PARENT_ORDER]


def derive(
    storage, context: StageContext, pin_file: dict[str, Any], work: Path
) -> tuple[dict[str, Any], list[tuple[str, bytes]]]:
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

    parents = pinned_parents(pin_file)
    frames = {ref.dataset: read_dataset(storage, ref) for ref in parents}
    games = frames["games"].rename(columns={"kickoff_utc": "start_date"})
    byplay, drives, team_game, _ = build_preaggregation_pipeline(
        frames["plays"],
        games_df=games,
        teams_df=frames["teams"],
        venues_df=None,
        weather_df=None,
        corrections_df=None,
        nullable_ppa=True,
    )
    reconciliation = reconcile_completed_games(
        games,
        team_game.merge(
            stream_points_by_team_game(byplay), on=["game_id", "team"], how="left"
        ),
        frames["team_game_stats"],
        declared_incomplete_game_ids=None,
    )
    outputs = {
        "byplay": byplay,
        "drives": drives,
        "reconciled_team_game": team_game,
        "source_reconciliation": reconciliation,
    }
    as_of = datetime.fromisoformat(
        context.plan.policies["silver_2026_as_of"].replace("Z", "+00:00")
    )
    local = LocalStorage(str(work))
    files: list[tuple[str, bytes]] = []
    summary: dict[str, Any] = {"datasets": {}}
    for dataset, frame in outputs.items():
        validate_frame(frame, schema_for(dataset, silver.DERIVED[dataset]))
        ref, _ = build_dataset_version(
            local,
            build=BuildRequest(
                dataset=dataset,
                parent_refs=tuple(parents),
                code_sha=context.code_sha,
                config_sha=config_sha(),
                as_of=as_of,
                schema_version=silver.DERIVED[dataset],
                tier="silver",
            ),
            records=frame.to_dict("records"),
            partitions={"seasons": [2026]},
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
        }
    legacy = read_dataset(storage, silver._ref(pin_file["legacy_comparison"]["byplay"]))
    summary["ppa"] = {
        "rows": int(len(byplay)),
        "legacy_rows": int(len(legacy)),
        "rows_equal": len(byplay) == len(legacy),
        "null_ppa": int(byplay["ppa"].isna().sum()),
        "legacy_zero_ppa": int((legacy["ppa"] == 0).sum()),
    }
    summary["value_differences"] = silver.value_differences(byplay, legacy)
    summary["punt_return_fix"] = silver.punt_return_fix(byplay, legacy)
    summary["reconciliation"] = {
        "classifications": {
            str(k): int(v)
            for k, v in reconciliation["classification"].value_counts().items()
        },
        "blocking": int(reconciliation["blocking"].fillna(True).sum()),
    }
    summary["completed_games"] = int(reconciliation["game_id"].nunique())
    summary["parents"] = [ref.version_id for ref in parents]
    summary["config"] = PIPELINE_CONFIG
    summary["config_sha"] = config_sha()
    return summary, files


def build(context: StageContext) -> StageOutput:
    from dotenv import load_dotenv

    load_dotenv()
    from cks_picks_cfb.data.storage import get_storage
    from cks_picks_cfb.data.storage.base import StorageSettings

    settings = StorageSettings.from_env(environment="preview")
    if f"r2:{settings.account_id}:{settings.bucket}" != context.plan.storage_identity:
        raise GateError("storage identity differs from the plan")
    storage = RetryingStorage(get_storage(environment="preview"))
    pin_file = json.loads(context.read_input("silver_2026_parents"))
    prefix = SUMMARY.format(run_id=context.plan.run_id)

    def artifacts() -> Iterator[tuple[str, bytes]]:
        with tempfile.TemporaryDirectory(prefix="6a-silver-2026-") as tmp:
            summary, files = derive(storage, context, pin_file, Path(tmp))
            yield from files
        yield (
            prefix,
            json.dumps(summary, indent=2, sort_keys=True, default=str).encode(),
        )

    return StageOutput(artifacts=artifacts(), metrics={"season": 2026})


def staged(context: StageContext, dataset: str) -> pd.DataFrame:
    summary = json.loads(
        context.read_artifact("silver_2026", SUMMARY.format(run_id=context.plan.run_id))
    )
    key = summary["datasets"][dataset]["keys"][0]
    return pd.read_parquet(io.BytesIO(context.read_artifact("silver_2026", key)))


def verify(context: StageContext) -> list[str]:
    from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame

    stage = context.stage.name
    summary = json.loads(
        context.read_artifact(stage, SUMMARY.format(run_id=context.plan.run_id))
    )
    problems: list[str] = []
    if summary["config_sha"] != config_sha() or not summary["config"]["nullable_ppa"]:
        problems.append("2026 silver config is not the nullable-PPA reconciled build")
    if summary["reconciliation"]["blocking"]:
        problems.append("blocking reconciliation rows")
    if not summary["ppa"]["rows_equal"]:
        problems.append("byplay rows differ from the legacy Week 4 byplay")
    differences, fix = summary["value_differences"], summary["punt_return_fix"]
    if unexplained := set(differences) - {"ppa", *silver.PUNT_FIX_COLUMNS}:
        problems.append(f"unexplained byplay value changes {sorted(unexplained)}")
    for column in silver.PUNT_FIX_COLUMNS:
        if differences.get(column, 0) != fix["rows"]:
            problems.append(f"{column} changes differ from the punt fix")
    if not fix["fits_punt_return_fix"]:
        problems.append("special-teams changes are not the punt fix")
    if differences.get("ppa") != summary["ppa"]["null_ppa"]:
        problems.append("ppa changes are not exactly the nulled values")
    if summary["ppa"]["null_ppa"] <= 0:
        problems.append("no null PPA: nullable mode not in effect")
    for dataset, info in summary["datasets"].items():
        data_key, manifest_key = info["keys"]
        data = context.read_artifact(stage, data_key)
        manifest = json.loads(context.read_artifact(stage, manifest_key))
        if hashlib.sha256(data).hexdigest() != manifest["content_sha"]:
            problems.append(f"{dataset}: data hash != manifest")
        if manifest["config_sha"] != config_sha():
            problems.append(f"{dataset}: wrong config sha")
        if list(manifest["parent_versions"]) != summary["parents"]:
            problems.append(f"{dataset}: parent versions differ")
        frame = pd.read_parquet(io.BytesIO(data))
        if len(frame) != info["rows"] or manifest["row_count"] != info["rows"]:
            problems.append(f"{dataset}: row count mismatch")
        validate_frame(frame, schema_for(dataset, silver.DERIVED[dataset]))
    return problems
