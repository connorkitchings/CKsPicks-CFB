"""Command-line entry point for resumable weekly operations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from dotenv import load_dotenv
from omegaconf import OmegaConf

from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ops.state_machine import (
    OperationContext,
    PipelineStep,
    PostgresStateStore,
    StateMachine,
    WebhookFailureNotifier,
    new_context,
    subprocess_step,
)


def _python(script: str, *args: object) -> list[str]:
    return [sys.executable, script, *(str(arg) for arg in args)]


def _require_week(context: OperationContext) -> int:
    if context.week is None:
        raise ValueError(f"{context.command} requires a week")
    return context.week


def _snapshot_inputs_step(argv: Sequence[str], output_uri: str) -> PipelineStep:
    def action(_: OperationContext) -> Sequence[Mapping[str, Any]]:
        completed = subprocess.run(
            list(argv),
            check=False,
            env={**os.environ, "PYTHONPATH": ".:src"},
        )
        if completed.returncode != 0:
            raise subprocess.CalledProcessError(completed.returncode, list(argv))
        refs = json.loads(get_storage().read_bytes(output_uri).decode("utf-8"))
        return list(refs)

    def resume_validator(
        _: OperationContext, outputs: Sequence[Mapping[str, Any]]
    ) -> bool:
        try:
            storage = get_storage()
            persisted = json.loads(storage.read_bytes(output_uri).decode("utf-8"))
        except Exception:
            return False
        return list(outputs) == persisted

    return PipelineStep(
        "snapshot_inputs",
        action,
        definition={"argv": list(argv), "output_uri": output_uri},
        resume_validator=resume_validator,
    )


def _fetch_source_step(
    *, name: str, argv: Sequence[str], conn_url: str, entity: str
) -> PipelineStep:
    def action(context: OperationContext) -> Sequence[Mapping[str, Any]]:
        ingestion_run_id = f"{context.pipeline_run_id}:{entity}"
        completed = subprocess.run(
            list(argv),
            check=False,
            env={
                **os.environ,
                "PYTHONPATH": ".:src",
                "CFB_INGESTION_RUN_ID": ingestion_run_id,
            },
        )
        if completed.returncode != 0:
            raise subprocess.CalledProcessError(completed.returncode, list(argv))
        with psycopg.connect(conn_url) as conn:
            rows = conn.execute(
                "SELECT capture_id, content_sha, uri, row_count "
                "FROM catalog.source_captures WHERE ingestion_run_id = %s "
                "ORDER BY captured_at, capture_id",
                (ingestion_run_id,),
            ).fetchall()
        if not rows:
            raise RuntimeError(f"Source step {entity} produced no registered captures")
        return tuple(
            {
                "capture_id": str(row[0]),
                "content_sha": str(row[1]),
                "uri": str(row[2]),
                "row_count": int(row[3]),
            }
            for row in rows
        )

    def resume_validator(
        _: OperationContext, outputs: Sequence[Mapping[str, Any]]
    ) -> bool:
        if not outputs:
            return False
        try:
            with psycopg.connect(conn_url) as conn:
                rows = conn.execute(
                    "SELECT capture_id, content_sha, uri, row_count "
                    "FROM catalog.source_captures WHERE capture_id = ANY(%s)",
                    ([str(output["capture_id"]) for output in outputs],),
                ).fetchall()
        except Exception:
            return False
        actual = {
            str(row[0]): {
                "capture_id": str(row[0]),
                "content_sha": str(row[1]),
                "uri": str(row[2]),
                "row_count": int(row[3]),
            }
            for row in rows
        }
        return all(
            actual.get(str(output.get("capture_id"))) == dict(output)
            for output in outputs
        )

    return PipelineStep(
        name,
        action,
        definition={"argv": list(argv), "entity": entity},
        resume_validator=resume_validator,
    )


def _silver_from_ingestion_step(
    *,
    name: str,
    dataset: str,
    entity: str,
    conn_url: str,
    output_ref_uri: str,
    as_of: str,
    games_ref_uri: str | None = None,
    week_policy_ref_uri: str | None = None,
) -> PipelineStep:
    """Materialize one immutable Silver ref from this run's captured source rows."""

    def action(context: OperationContext) -> Sequence[Mapping[str, Any]]:
        ingestion_run_id = f"{context.pipeline_run_id}:{entity}"
        with psycopg.connect(conn_url) as conn:
            rows = conn.execute(
                "SELECT capture_id FROM catalog.source_captures "
                "WHERE ingestion_run_id = %s ORDER BY captured_at, capture_id",
                (ingestion_run_id,),
            ).fetchall()
        if not rows:
            raise RuntimeError(f"No captures available for {entity} Silver build")
        argv = _python(
            "scripts/pipeline/build_silver.py",
            "--dataset",
            dataset,
            "--as-of",
            as_of,
            "--output-ref-uri",
            output_ref_uri,
        )
        if games_ref_uri:
            argv.extend(["--games-ref-uri", games_ref_uri])
        if week_policy_ref_uri:
            argv.extend(["--week-policy-ref-uri", week_policy_ref_uri])
        for row in rows:
            argv.extend(["--capture-id", str(row[0])])
        completed = subprocess.run(
            argv, check=False, env={**os.environ, "PYTHONPATH": ".:src"}
        )
        if completed.returncode != 0:
            raise subprocess.CalledProcessError(completed.returncode, argv)
        ref = json.loads(get_storage().read_bytes(output_ref_uri).decode("utf-8"))
        return (
            {
                "ref_uri": output_ref_uri,
                "capture_ids": [str(row[0]) for row in rows],
                **ref,
            },
        )

    def resume_validator(
        _: OperationContext, outputs: Sequence[Mapping[str, Any]]
    ) -> bool:
        return bool(outputs) and get_storage().exists(output_ref_uri)

    return PipelineStep(
        name,
        action,
        definition={
            "dataset": dataset,
            "entity": entity,
            "output_ref_uri": output_ref_uri,
            "as_of": as_of,
        },
        resume_validator=resume_validator,
    )


def _week_policy_from_ingestion_step(
    *, conn_url: str, output_ref_uri: str, as_of: str
) -> PipelineStep:
    """Build Week 0 policy using only this operation's schedule capture."""

    def action(context: OperationContext) -> Sequence[Mapping[str, Any]]:
        with psycopg.connect(conn_url) as conn:
            rows = conn.execute(
                "SELECT capture_id FROM catalog.source_captures "
                "WHERE ingestion_run_id = %s ORDER BY captured_at, capture_id",
                (f"{context.pipeline_run_id}:games",),
            ).fetchall()
        if not rows:
            raise RuntimeError("No schedule captures available for week policy")
        argv = _python(
            "scripts/pipeline/build_schedule_week_policy.py",
            "--season",
            context.season,
            "--assignments",
            f"conf/policy/canonical_week_{context.season}_v1.yaml",
            "--as-of",
            as_of,
            "--output-ref-uri",
            output_ref_uri,
            "--environment",
            context.environment,
        )
        for row in rows:
            argv.extend(["--capture-id", str(row[0])])
        completed = subprocess.run(
            argv, check=False, env={**os.environ, "PYTHONPATH": ".:src"}
        )
        if completed.returncode != 0:
            raise subprocess.CalledProcessError(completed.returncode, argv)
        ref = json.loads(get_storage().read_bytes(output_ref_uri).decode("utf-8"))
        return ({"ref_uri": output_ref_uri, **ref},)

    return PipelineStep(
        "build_week_policy",
        action,
        definition={"output_ref_uri": output_ref_uri, "as_of": as_of},
        resume_validator=lambda _, outputs: bool(outputs)
        and get_storage().exists(output_ref_uri),
    )


def _resolve_frozen_run(conn_url: str, season: int, week: int) -> str:
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT run_id FROM prediction_runs WHERE season = %s AND week = %s "
                "AND state = 'frozen' ORDER BY frozen_at DESC LIMIT 1",
                (season, week),
            )
            row = cur.fetchone()
    if not row:
        raise RuntimeError(f"No frozen run for {season} week {week}")
    return str(row[0])


def _history_objects(prefix: str):
    from cks_picks_cfb.data.history import (
        FORBIDDEN_YEARS,
        PRIOR_ONLY_2019_ENTITIES,
        inventory_historical_source,
    )
    from cks_picks_cfb.data.storage import get_source_storage

    source = get_source_storage()
    destination = get_storage(environment="preview")
    if getattr(source.backend, "bucket", None) == getattr(destination, "bucket", None):
        raise RuntimeError(
            "Historical source and preview destination buckets must differ"
        )
    objects = inventory_historical_source(source, prefix=prefix)
    eligible = []
    for item in objects:
        if item.years & FORBIDDEN_YEARS:
            continue
        if 2019 in item.years and item.entity not in PRIOR_ONLY_2019_ENTITIES:
            continue
        eligible.append(item)
    return source, destination, objects, eligible


def _inventory_source_action(prefix: str):
    def action(context: OperationContext) -> Sequence[Mapping[str, Any]]:
        from cks_picks_cfb.data.history import (
            inventory_report,
            inventory_schema_report,
            object_json,
        )

        source, destination, objects, eligible = _history_objects(prefix)
        report = {
            **inventory_report(objects),
            "schemas": inventory_schema_report(source, eligible),
            "eligible_object_count": len(eligible),
            "eligible_objects": [object_json(item) for item in eligible],
        }
        uri = (
            f"artifacts/{context.environment}/history-inventory/"
            f"{context.pipeline_run_id}.json"
        )
        payload = json.dumps(report, indent=2, sort_keys=True, default=str).encode()
        if destination.exists(uri):
            if destination.read_bytes(uri) != payload:
                raise FileExistsError(f"Immutable inventory exists: {uri}")
        else:
            destination.write_bytes(payload, uri)
        return ({"inventory_uri": uri, **inventory_report(objects)},)

    return action


def _import_history_action(conn_url: str, source, destination, item):
    def action(_: OperationContext) -> Sequence[Mapping[str, Any]]:
        from cks_picks_cfb.data.history import import_historical_object

        capture = import_historical_object(
            source=source,
            destination=destination,
            conn_url=conn_url,
            item=item,
        )
        return (
            {
                "capture_id": capture.capture_id,
                "provider": capture.provider,
                "entity": capture.entity,
                "captured_at": capture.captured_at.isoformat(),
                "effective_at": (
                    capture.effective_at.isoformat() if capture.effective_at else None
                ),
                "content_sha": capture.content_sha,
                "object_sha": capture.object_sha,
                "uri": capture.uri,
                "row_count": capture.row_count,
            },
        )

    return action


def _hydrate_history_action(conn_url: str, destination, eligible):
    def action(context: OperationContext) -> Sequence[Mapping[str, Any]]:
        from cks_picks_cfb.data.catalog import begin_ingestion_run, finish_ingestion_run
        from cks_picks_cfb.data.history import hydrate_historical_catalog

        ingestion_run_id = f"hydrate-history-{context.pipeline_run_id}"
        begin_ingestion_run(
            conn_url,
            ingestion_run_id=ingestion_run_id,
            provider="preview_r2",
            entity="historical_catalog",
            request={"operation": "hydrate_existing_preview_observations"},
        )
        try:
            result = hydrate_historical_catalog(
                destination=destination,
                conn_url=conn_url,
                eligible=eligible,
                ingestion_run_id=ingestion_run_id,
            )
            finish_ingestion_run(conn_url, ingestion_run_id, succeeded=True)
            return (result,)
        except Exception as exc:
            finish_ingestion_run(
                conn_url,
                ingestion_run_id,
                succeeded=False,
                error_category=type(exc).__name__,
                error_detail=str(exc),
            )
            raise

    return action


def _history_silver_steps(environment: str = "preview") -> list[PipelineStep]:
    """Return the deterministic all-years Silver build sequence."""
    as_of = "2026-08-09T23:59:59Z"
    steps: list[PipelineStep] = []

    def add(
        dataset: str,
        season: int,
        *,
        games: bool = False,
        optional: bool = False,
        week_policy: bool = False,
    ):
        output = f"artifacts/preview/refs/history/{dataset}-{season}.json"
        argv = _python(
            "scripts/pipeline/build_history_silver.py",
            "--dataset",
            dataset,
            "--season",
            str(season),
            "--as-of",
            as_of,
            "--output-ref-uri",
            output,
            "--environment",
            environment,
        )
        if games:
            argv.extend(
                [
                    "--games-ref-uri",
                    f"artifacts/preview/refs/history/games-{season}.json",
                ]
            )
        if week_policy:
            argv.extend(
                [
                    "--week-policy-ref-uri",
                    f"artifacts/preview/refs/history/schedule_week_policy-{season}.json",
                ]
            )
        if optional:
            argv.append("--optional")
        steps.append(subprocess_step(f"silver_{dataset}_{season}", argv))

    def add_policy(season: int):
        steps.append(
            subprocess_step(
                f"silver_schedule_week_policy_{season}",
                _python(
                    "scripts/pipeline/build_schedule_week_policy.py",
                    "--season",
                    str(season),
                    "--assignments",
                    f"conf/policy/canonical_week_{season}_v1.yaml",
                    "--as-of",
                    as_of,
                    "--output-ref-uri",
                    f"artifacts/preview/refs/history/schedule_week_policy-{season}.json",
                    "--environment",
                    environment,
                ),
            )
        )

    add("preseason_team_inputs", 2019)
    for season in (2021, 2022, 2023, 2024, 2025, 2026):
        if season == 2026:
            add_policy(2026)
        for dataset in (
            "teams",
            "team_aliases",
            "venues",
            "games",
            "schedule_revisions",
            "game_outcomes",
        ):
            if season == 2026 and dataset in {"games", "schedule_revisions"}:
                add(dataset, season, week_policy=True)
            elif dataset in {"venues", "team_aliases"}:
                add(dataset, season, optional=True)
            else:
                add(dataset, season)
        if season <= 2025:
            add("plays", season, games=True)
            add("team_game_stats", season, optional=True)
        add("legacy_market_references", season)
        add("market_quotes", season, games=True, optional=True)
        add("market_snapshots", season, games=True, optional=True)
        add("weather_observations", season, optional=True)
        add("preseason_team_inputs", season, optional=True)
    for season in (2021, 2022, 2023, 2024, 2025):
        steps.append(
            subprocess_step(
                f"team_game_{season}",
                _python(
                    "scripts/pipeline/build_team_game_dataset.py",
                    "--plays-ref-uri",
                    f"artifacts/preview/refs/history/plays-{season}.json",
                    "--games-ref-uri",
                    f"artifacts/preview/refs/history/games-{season}.json",
                    "--teams-ref-uri",
                    f"artifacts/preview/refs/history/teams-{season}.json",
                    "--venues-ref-uri",
                    f"artifacts/preview/refs/history/venues-{season}.json",
                    "--game-stats-ref-uri",
                    f"artifacts/preview/refs/history/team_game_stats-{season}.json",
                    "--corrections-ref-uri",
                    "artifacts/preview/refs/data-corrections-v1.json",
                    "--as-of",
                    as_of,
                    "--output-ref-uri",
                    f"artifacts/preview/refs/history/reconciled_team_game-{season}.json",
                    "--environment",
                    environment,
                ),
            )
        )
    for dataset in (
        "games",
        "schedule_revisions",
        "game_outcomes",
        "plays",
        "team_game_stats",
        "legacy_market_references",
        "reconciled_team_game",
    ):
        argv = _python(
            "scripts/pipeline/combine_history_versions.py",
            "--dataset",
            dataset,
            "--as-of",
            as_of,
            "--output-ref-uri",
            f"artifacts/preview/refs/history/{dataset}-2021-2025.json",
            "--environment",
            environment,
        )
        if dataset in {
            "team_game_stats",
            "weather_observations",
            "preseason_team_inputs",
        }:
            argv.append("--optional")
        for season in (2021, 2022, 2023, 2024, 2025):
            argv.extend(["--season", str(season)])
        steps.append(subprocess_step(f"combine_{dataset}_2021_2025", argv))
    schedule_argv = _python(
        "scripts/pipeline/combine_history_versions.py",
        "--dataset",
        "games",
        "--as-of",
        as_of,
        "--allow-2026",
        "--output-ref-uri",
        "artifacts/preview/refs/history/games-2021-2026.json",
        "--environment",
        environment,
    )
    for season in (2021, 2022, 2023, 2024, 2025, 2026):
        schedule_argv.extend(["--season", str(season)])
    steps.append(subprocess_step("combine_games_2021_2026", schedule_argv))
    steps.extend(
        [
            subprocess_step(
                "build_temporal_matchups",
                _python(
                    "scripts/pipeline/build_temporal_matchups.py",
                    "--team-game-ref-uri",
                    "artifacts/preview/refs/history/reconciled_team_game-2021-2025.json",
                    "--schedule-ref-uri",
                    "artifacts/preview/refs/history/games-2021-2026.json",
                    "--prior-2019-ref-uri",
                    "artifacts/preview/refs/history/preseason_team_inputs-2019.json",
                    "--as-of",
                    as_of,
                    "--output-ref-uri",
                    "artifacts/preview/refs/history/temporal-matchup-inputs.json",
                    "--environment",
                    environment,
                ),
            ),
            subprocess_step(
                "build_structural_gold",
                _python(
                    "scripts/pipeline/build_regime_features.py",
                    "--matchups-ref-uri",
                    "artifacts/preview/refs/history/temporal-matchup-inputs.json",
                    "--schedule-ref-uri",
                    "artifacts/preview/refs/history/games-2021-2026.json",
                    "--as-of",
                    as_of,
                    "--output-ref-uri",
                    "artifacts/preview/refs/history/point-in-time-core.json",
                    "--environment",
                    environment,
                ),
            ),
            subprocess_step(
                "build_selection_baselines",
                _python(
                    "scripts/pipeline/generate_baseline_predictions.py",
                    "--core-ref-uri",
                    "artifacts/preview/refs/history/point-in-time-core.json",
                    "--as-of",
                    as_of,
                    "--output-ref-uri",
                    "artifacts/preview/refs/history/baselines-selection.json",
                    "--environment",
                    environment,
                ),
            ),
            subprocess_step(
                "assemble_selection_gold",
                _python(
                    "scripts/pipeline/assemble_model_ready_features.py",
                    "--core-ref-uri",
                    "artifacts/preview/refs/history/point-in-time-core.json",
                    "--baselines-ref-uri",
                    "artifacts/preview/refs/history/baselines-selection.json",
                    "--as-of",
                    as_of,
                    "--output-ref-uri",
                    "artifacts/preview/refs/history/model-ready-selection.json",
                    "--environment",
                    environment,
                ),
            ),
        ]
    )
    return steps


def build_steps(
    context: OperationContext,
    *,
    conn_url: str,
    waiver: str | None = None,
    options: argparse.Namespace | None = None,
) -> list[PipelineStep]:
    year = context.season
    week = context.week
    as_of = context.as_of
    environment = context.environment
    if context.command in {"inventory-source", "import-history", "hydrate-history"}:
        assert options is not None
        prefix = options.prefix or ""
        source, destination, _, eligible = _history_objects(prefix)
        steps = [PipelineStep("inventory_source", _inventory_source_action(prefix))]
        if context.command == "hydrate-history":
            return [
                PipelineStep(
                    "hydrate_existing_preview_observations",
                    _hydrate_history_action(conn_url, destination, eligible),
                )
            ]
        if context.command == "import-history":
            steps.append(
                subprocess_step(
                    "seed_corrections",
                    _python("scripts/pipeline/seed_data_corrections.py"),
                )
            )
            if not getattr(options, "skip_imports", False):
                for item in eligible:
                    suffix = hashlib.sha256(item.uri.encode()).hexdigest()[:16]
                    steps.append(
                        PipelineStep(
                            f"import_{suffix}",
                            _import_history_action(conn_url, source, destination, item),
                        )
                    )
            steps.extend(_history_silver_steps(environment))
            steps.extend(
                [
                    PipelineStep(
                        "audit_structural",
                        _audit_data_action(conn_url, mode="structural"),
                    ),
                    PipelineStep(
                        "audit_model_ready",
                        _audit_data_action(conn_url, mode="model-ready"),
                    ),
                ]
            )
        return steps
    if context.command == "fetch-source":
        assert options is not None and options.entity
        weekly = {"plays", "betting_lines", "game_stats"}
        if options.entity in weekly:
            if week is None:
                raise ValueError(f"fetch-source {options.entity} requires --week")
            argv = _python(
                "scripts/data/ingest_week.py",
                "--year",
                year,
                "--week",
                week,
                "--entities",
                options.entity,
            )
        else:
            argv = _python(
                "scripts/data/ingest_season.py",
                "--year",
                year,
                "--entities",
                options.entity,
            )
        return [
            _fetch_source_step(
                name=f"fetch_{options.entity}",
                argv=argv,
                conn_url=conn_url,
                entity=options.entity,
            )
        ]
    if context.command == "build-silver":
        assert options is not None and as_of is not None
        argv = _python(
            "scripts/pipeline/build_silver.py",
            "--dataset",
            options.dataset,
            "--as-of",
            as_of,
            "--output-ref-uri",
            options.output_ref_uri,
        )
        for capture_id in options.capture_id:
            argv.extend(["--capture-id", capture_id])
        if options.games_ref_uri:
            argv.extend(["--games-ref-uri", options.games_ref_uri])
        if options.week_policy_ref_uri:
            argv.extend(["--week-policy-ref-uri", options.week_policy_ref_uri])
        return [subprocess_step("build_silver", argv)]
    if context.command == "build-team-game":
        assert options is not None and as_of is not None
        argv = _python(
            "scripts/pipeline/build_team_game_dataset.py",
            "--plays-ref-uri",
            options.plays_ref_uri,
            "--games-ref-uri",
            options.games_ref_uri,
            "--as-of",
            as_of,
            "--output-ref-uri",
            options.output_ref_uri,
        )
        for name in ("teams", "venues", "weather", "game_stats", "corrections"):
            value = getattr(options, f"{name}_ref_uri")
            if value:
                argv.extend([f"--{name.replace('_', '-')}-ref-uri", value])
        return [subprocess_step("build_team_game", argv)]
    if context.command == "build-features":
        assert options is not None and as_of is not None
        argv = _python(
            "scripts/pipeline/build_regime_features.py",
            "--matchups-ref-uri",
            options.matchups_ref_uri,
            "--schedule-ref-uri",
            options.schedule_ref_uri,
            "--as-of",
            as_of,
            "--output-ref-uri",
            options.output_ref_uri,
        )
        if options.baselines_ref_uri:
            argv.extend(["--baselines-ref-uri", options.baselines_ref_uri])
        return [
            subprocess_step(
                "build_features",
                argv,
            )
        ]
    if context.command == "build-baselines":
        assert options is not None and as_of is not None
        argv = _python(
            "scripts/pipeline/generate_baseline_predictions.py",
            "--core-ref-uri",
            options.core_ref_uri,
            "--as-of",
            as_of,
            "--output-ref-uri",
            options.output_ref_uri,
        )
        if options.include_locked_2025:
            argv.extend(
                [
                    "--include-locked-2025",
                    "--frozen-design-sha",
                    options.frozen_design_sha,
                ]
            )
        argv.extend(["--environment", environment])
        return [subprocess_step("build_baselines", argv)]
    if context.command == "assemble-model-ready":
        assert options is not None and as_of is not None
        argv = _python(
            "scripts/pipeline/assemble_model_ready_features.py",
            "--core-ref-uri",
            options.core_ref_uri,
            "--baselines-ref-uri",
            options.baselines_ref_uri,
            "--as-of",
            as_of,
            "--output-ref-uri",
            options.output_ref_uri,
            "--environment",
            environment,
        )
        if options.markets_ref_uri:
            argv.extend(["--markets-ref-uri", options.markets_ref_uri])
        if options.preseason_features_ref_uri:
            argv.extend(
                [
                    "--preseason-features-ref-uri",
                    options.preseason_features_ref_uri,
                    "--feature-track",
                    options.feature_track,
                ]
            )
        return [subprocess_step("assemble_model_ready", argv)]
    if context.command == "prepare-week":
        assert week is not None and as_of is not None
        root = f"artifacts/{environment}/pipeline-runs/{context.pipeline_run_id}"
        history = f"artifacts/{environment}/refs/history"
        refs = {
            "policy": f"{root}/schedule_week_policy_ref.json",
            "games": f"{root}/games_ref.json",
            "outcomes": f"{root}/game_outcomes_ref.json",
            "plays": f"{root}/plays_ref.json",
            "stats": f"{root}/team_game_stats_ref.json",
            "team_game": f"{root}/reconciled_team_game_ref.json",
            "rating_input_ref_set": f"{root}/rating_input_ref_set.json",
            "schedule": f"{root}/schedule_2021_2026_ref.json",
            "all_outcomes": f"{root}/outcomes_2021_2026_ref.json",
            "all_team_game": f"{root}/team_game_2021_2026_ref.json",
            "temporal": f"{root}/temporal_matchups_ref.json",
            "gold": f"{root}/point_in_time_matchups_ref.json",
        }
        steps: list[PipelineStep] = [
            _fetch_source_step(
                name="ingest_schedule",
                argv=_python(
                    "scripts/data/ingest_season.py",
                    "--year",
                    year,
                    "--entities",
                    "games",
                ),
                conn_url=conn_url,
                entity="games",
            ),
        ]
        for completed_week in range(0, week):
            for entity in ("plays", "game_stats"):
                steps.append(
                    _fetch_source_step(
                        name=f"ingest_{entity}_week_{completed_week}",
                        argv=_python(
                            "scripts/data/ingest_week.py",
                            "--year",
                            year,
                            "--week",
                            completed_week,
                            "--entities",
                            entity,
                        ),
                        conn_url=conn_url,
                        entity=entity,
                    )
                )
        steps.extend(
            [
                _week_policy_from_ingestion_step(
                    conn_url=conn_url, output_ref_uri=refs["policy"], as_of=as_of
                ),
                _silver_from_ingestion_step(
                    name="build_games",
                    dataset="games",
                    entity="games",
                    conn_url=conn_url,
                    output_ref_uri=refs["games"],
                    as_of=as_of,
                    week_policy_ref_uri=refs["policy"],
                ),
                _silver_from_ingestion_step(
                    name="build_outcomes",
                    dataset="game_outcomes",
                    entity="games",
                    conn_url=conn_url,
                    output_ref_uri=refs["outcomes"],
                    as_of=as_of,
                ),
                _silver_from_ingestion_step(
                    name="build_plays",
                    dataset="plays",
                    entity="plays",
                    conn_url=conn_url,
                    output_ref_uri=refs["plays"],
                    as_of=as_of,
                    games_ref_uri=refs["games"],
                ),
                _silver_from_ingestion_step(
                    name="build_team_game_stats",
                    dataset="team_game_stats",
                    entity="game_stats",
                    conn_url=conn_url,
                    output_ref_uri=refs["stats"],
                    as_of=as_of,
                    games_ref_uri=refs["games"],
                ),
                subprocess_step(
                    "build_current_team_game",
                    _python(
                        "scripts/pipeline/build_team_game_dataset.py",
                        "--plays-ref-uri",
                        refs["plays"],
                        "--games-ref-uri",
                        refs["games"],
                        "--teams-ref-uri",
                        f"{history}/teams-{year}.json",
                        "--game-stats-ref-uri",
                        refs["stats"],
                        "--corrections-ref-uri",
                        f"{history}/data-corrections-v1.json",
                        "--as-of",
                        as_of,
                        "--output-ref-uri",
                        refs["team_game"],
                        "--output-ref-set-uri",
                        refs["rating_input_ref_set"],
                        "--environment",
                        environment,
                    ),
                ),
            ]
        )
        for name, dataset, current_ref in (
            ("combine_schedule", "games", refs["games"]),
            ("combine_outcomes", "game_outcomes", refs["outcomes"]),
            ("combine_team_game", "reconciled_team_game", refs["team_game"]),
        ):
            output_ref = {
                "games": refs["schedule"],
                "game_outcomes": refs["all_outcomes"],
                "reconciled_team_game": refs["all_team_game"],
            }[dataset]
            argv = _python(
                "scripts/pipeline/combine_history_versions.py",
                "--dataset",
                dataset,
                "--as-of",
                as_of,
                "--output-ref-uri",
                output_ref,
                "--allow-2026",
                "--ref-uri",
                current_ref,
                "--environment",
                environment,
            )
            for historic_year in range(2021, 2026):
                argv.extend(["--season", historic_year])
            steps.append(subprocess_step(name, argv))
        steps.extend(
            [
                subprocess_step(
                    "build_temporal_matchups",
                    _python(
                        "scripts/pipeline/build_temporal_matchups.py",
                        "--team-game-ref-uri",
                        refs["all_team_game"],
                        "--schedule-ref-uri",
                        refs["schedule"],
                        "--prior-2019-ref-uri",
                        f"{history}/preseason_team_inputs-2019.json",
                        "--outcomes-ref-uri",
                        refs["all_outcomes"],
                        "--inference-season",
                        year,
                        "--as-of",
                        as_of,
                        "--output-ref-uri",
                        refs["temporal"],
                        "--environment",
                        environment,
                    ),
                ),
                subprocess_step(
                    "build_gold",
                    _python(
                        "scripts/pipeline/build_regime_features.py",
                        "--matchups-ref-uri",
                        refs["temporal"],
                        "--schedule-ref-uri",
                        refs["schedule"],
                        "--baselines-ref-uri",
                        f"{history}/baselines-selection.json",
                        "--as-of",
                        as_of,
                        "--output-ref-uri",
                        refs["gold"],
                        "--environment",
                        environment,
                    ),
                ),
                subprocess_step(
                    "target_week_readiness",
                    _python(
                        "scripts/pipeline/check_prepared_week.py",
                        "--year",
                        year,
                        "--week",
                        week,
                        "--as-of",
                        as_of,
                        "--games-ref-uri",
                        refs["games"],
                        "--outcomes-ref-uri",
                        refs["outcomes"],
                        "--gold-ref-uri",
                        refs["gold"],
                        "--environment",
                        environment,
                    ),
                ),
            ]
        )
        return steps
    if context.command == "readiness":
        assert week is not None and as_of is not None
        config = str(getattr(options, "config", "conf/weekly_bets/v2_champion.yaml"))
        return [
            subprocess_step(
                "preflight",
                _python(
                    "scripts/pipeline/preflight.py",
                    "--year",
                    year,
                    "--week",
                    week,
                    "--as-of",
                    as_of,
                    "--config",
                    config,
                ),
            ),
            subprocess_step("contracts", _python("contracts/validation.py")),
            PipelineStep(
                "audit_data", _audit_data_action(conn_url, mode="model-ready")
            ),
        ]
    if context.command == "publish-week":
        assert week is not None and as_of is not None
        if not context.prediction_run_id:
            raise ValueError("publish-week requires a prediction run ID")
        dataset_refs_uri = (
            f"artifacts/{context.environment}/pipeline-runs/"
            f"{context.pipeline_run_id}/input_refs.json"
        )
        market_ref_uri = (
            f"artifacts/{context.environment}/pipeline-runs/"
            f"{context.pipeline_run_id}/market_snapshots_ref.json"
        )
        config = str(getattr(options, "config", "conf/weekly_bets/v2_champion.yaml"))
        prepared_gold_ref_uri = getattr(options, "prepared_gold_ref_uri", None)
        if week > 0 and not prepared_gold_ref_uri:
            raise ValueError(
                "publish-week after Week 0 requires --prepared-gold-ref-uri from prepare-week"
            )
        return [
            subprocess_step(
                "preflight",
                _python(
                    "scripts/pipeline/preflight.py",
                    "--year",
                    year,
                    "--week",
                    week,
                    "--as-of",
                    as_of,
                    "--config",
                    config,
                ),
            ),
            PipelineStep(
                "audit_data", _audit_data_action(conn_url, mode="model-ready")
            ),
            subprocess_step(
                "ingest_schedule",
                _python(
                    "scripts/data/ingest_season.py",
                    "--year",
                    year,
                    "--entities",
                    "games",
                ),
            ),
            _fetch_source_step(
                name="ingest_market",
                argv=_python(
                    "scripts/data/ingest_week.py",
                    "--year",
                    year,
                    "--week",
                    week,
                    "--entities",
                    "betting_lines",
                ),
                conn_url=conn_url,
                entity="betting_lines",
            ),
            subprocess_step(
                "build_market_snapshot",
                _python(
                    "scripts/pipeline/build_week_market_snapshot.py",
                    "--year",
                    year,
                    "--week",
                    week,
                    "--as-of",
                    as_of,
                    "--pipeline-run-id",
                    context.pipeline_run_id,
                    "--output-ref-uri",
                    market_ref_uri,
                ),
            ),
            _snapshot_inputs_step(
                _python(
                    "scripts/pipeline/snapshot_week_inputs.py",
                    "--year",
                    year,
                    "--week",
                    week,
                    "--as-of",
                    as_of,
                    "--pipeline-run-id",
                    context.pipeline_run_id,
                    "--market-ref-uri",
                    market_ref_uri,
                )
                + (
                    ["--prepared-gold-ref-uri", prepared_gold_ref_uri]
                    if prepared_gold_ref_uri
                    else []
                ),
                dataset_refs_uri,
            ),
            subprocess_step(
                "predict",
                _python(
                    "scripts/pipeline/generate_weekly_bets.py",
                    "--year",
                    year,
                    "--week",
                    week,
                    "--as-of",
                    as_of,
                    "--run-id",
                    context.prediction_run_id,
                    "--run-state",
                    "preview",
                    "--config",
                    config,
                    "--dataset-refs-uri",
                    dataset_refs_uri,
                    "--upload-artifact",
                ),
            ),
            subprocess_step(
                "activate",
                _python(
                    "scripts/pipeline/publish_to_db.py",
                    "--year",
                    year,
                    "--week",
                    week,
                    "--run-id",
                    context.prediction_run_id,
                    "--state",
                    "published",
                    "--from-artifact",
                    "--config",
                    config,
                ),
            ),
        ]
    if context.command == "freeze-week":
        assert week is not None
        argv = _python(
            "scripts/pipeline/freeze_week.py", "--year", year, "--week", week
        )
        if waiver:
            argv.extend(["--waiver", waiver])
        return [subprocess_step("freeze", argv)]
    if context.command == "close-week":
        assert week is not None and as_of is not None
        run_id = _resolve_frozen_run(conn_url, year, week)
        outcomes_ref_uri = (
            f"artifacts/{context.environment}/pipeline-runs/"
            f"{context.pipeline_run_id}/game_outcomes_ref.json"
        )
        return [
            _fetch_source_step(
                name="ingest_finals",
                argv=_python(
                    "scripts/data/ingest_season.py",
                    "--year",
                    year,
                    "--entities",
                    "games",
                ),
                conn_url=conn_url,
                entity="games",
            ),
            _silver_from_ingestion_step(
                name="build_game_outcomes",
                dataset="game_outcomes",
                entity="games",
                conn_url=conn_url,
                output_ref_uri=outcomes_ref_uri,
                as_of=as_of,
            ),
            subprocess_step(
                "ingest_completed_week",
                _python(
                    "scripts/data/ingest_week.py",
                    "--year",
                    year,
                    "--week",
                    week,
                    "--entities",
                    "plays,betting_lines,game_stats",
                ),
            ),
            subprocess_step(
                "score",
                _python(
                    "scripts/pipeline/score_weekly_bets.py",
                    "--year",
                    year,
                    "--week",
                    week,
                    "--run-id",
                    run_id,
                    "--from-artifact",
                    "--outcomes-ref-uri",
                    outcomes_ref_uri,
                    "--upload-artifact",
                )
                + [
                    item
                    for value in getattr(options, "cancellation_waiver", [])
                    for item in ("--cancellation-waiver", value)
                ],
            ),
            subprocess_step(
                "publish_grades",
                _python(
                    "scripts/pipeline/score_to_db.py",
                    "--year",
                    year,
                    "--week",
                    week,
                    "--run-id",
                    run_id,
                    "--from-artifact",
                ),
            ),
        ]
    if context.command == "replay-season":
        return [
            subprocess_step(
                "replay",
                _python(
                    "scripts/pipeline/replay_season.py",
                    "--year",
                    year,
                    "--environment",
                    context.environment,
                ),
            )
        ]
    if context.command == "reconcile":
        return [PipelineStep("reconcile_artifacts", _reconcile_action(conn_url))]
    if context.command == "audit-data":
        assert options is not None
        return [
            PipelineStep(
                f"audit_{options.mode}",
                _audit_data_action(conn_url, mode=options.mode),
            )
        ]
    raise ValueError(f"Unsupported operation: {context.command}")


def _reconcile_action(conn_url: str):
    def action(context: OperationContext) -> Sequence[Mapping[str, Any]]:
        storage = get_storage()
        prefix = f"artifacts/{context.environment}/"
        manifests = [
            path
            for path in storage.list_files(prefix)
            if path.endswith("manifest.json")
        ]
        with psycopg.connect(conn_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT artifact_uri, artifact_sha256 FROM prediction_runs")
                registered = {str(uri): str(sha) for uri, sha in cur.fetchall()}
                results: list[Mapping[str, Any]] = []
                for manifest_uri in manifests:
                    payload = storage.read_bytes(manifest_uri)
                    manifest_sha = hashlib.sha256(payload).hexdigest()
                    status = (
                        "registered"
                        if any(
                            uri.rsplit("/", 1)[0] == manifest_uri.rsplit("/", 1)[0]
                            for uri in registered
                        )
                        else "orphaned"
                    )
                    cur.execute(
                        "INSERT INTO ops.reconciliation_status "
                        "(object_uri, object_sha256, status, pipeline_run_id, reconciled_at) "
                        "VALUES (%s, %s, %s, %s, NOW()) "
                        "ON CONFLICT (object_uri) DO UPDATE SET object_sha256 = EXCLUDED.object_sha256, "
                        "status = EXCLUDED.status, pipeline_run_id = EXCLUDED.pipeline_run_id, "
                        "reconciled_at = NOW()",
                        (
                            manifest_uri,
                            manifest_sha,
                            status,
                            context.pipeline_run_id,
                        ),
                    )
                    results.append({"uri": manifest_uri, "status": status})
            conn.commit()
        return results

    return action


def _audit_data_action(conn_url: str, *, mode: str):
    def action(_: OperationContext) -> Sequence[Mapping[str, Any]]:
        from cks_picks_cfb.models.training_policy import policy_from_mapping
        from cks_picks_cfb.ops.data_audit import (
            audit_catalog,
            audit_exact_markets,
            result_json,
        )

        if mode == "exact-market":
            ref, result = audit_exact_markets(conn_url, get_storage())
            print(result_json(ref, result))
            if not result.passed:
                raise RuntimeError(
                    "Exact-market audit failed: " + "; ".join(result.errors)
                )
            return [
                {
                    "dataset": ref.dataset,
                    "checks": {k: bool(v) for k, v in result.checks.items()},
                    "coverage": dict(result.coverage),
                }
            ]
        policy = policy_from_mapping(
            OmegaConf.to_container(
                OmegaConf.load(Path("conf/training/week0_2026.yaml")), resolve=True
            )
        )
        ref, result = audit_catalog(conn_url, get_storage(), policy, mode=mode)
        print(result_json(ref, result))
        if not result.passed:
            raise RuntimeError("Data audit failed: " + "; ".join(result.errors))
        return [
            {
                "dataset": ref.dataset,
                "version_id": ref.version_id,
                "checks": {k: bool(v) for k, v in result.checks.items()},
            }
        ]

    return action


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in (
        "inventory-source",
        "import-history",
        "hydrate-history",
        "fetch-source",
        "build-silver",
        "build-team-game",
        "build-features",
        "build-baselines",
        "assemble-model-ready",
        "prepare-week",
        "readiness",
        "publish-week",
        "freeze-week",
        "close-week",
        "replay-season",
        "reconcile",
        "audit-data",
    ):
        sub = subparsers.add_parser(command)
        sub.add_argument("--year", type=int, required=True)
        if command not in {
            "inventory-source",
            "import-history",
            "hydrate-history",
            "replay-season",
            "reconcile",
            "audit-data",
            "build-silver",
            "build-team-game",
            "build-features",
            "build-baselines",
            "assemble-model-ready",
            "fetch-source",
        }:
            sub.add_argument("--week", type=int, required=True)
        if command in {
            "readiness",
            "publish-week",
            "build-silver",
            "build-team-game",
            "build-features",
            "build-baselines",
            "assemble-model-ready",
            "prepare-week",
            "close-week",
        }:
            sub.add_argument("--as-of", required=True)
        if command in {"readiness", "publish-week"}:
            sub.add_argument(
                "--config",
                default="conf/weekly_bets/v2_champion.yaml",
                help="Weekly model configuration used by preflight and publication.",
            )
        if command == "publish-week":
            sub.add_argument("--prepared-gold-ref-uri")
        sub.add_argument(
            "--environment", choices=("preview", "production"), required=True
        )
        sub.add_argument("--pipeline-run-id")
        sub.add_argument("--crash-after-step", help=argparse.SUPPRESS)
        if command == "freeze-week":
            sub.add_argument("--waiver")
        if command == "close-week":
            sub.add_argument(
                "--cancellation-waiver",
                action="append",
                default=[],
                metavar="GAME_ID:REASON",
            )
        if command == "fetch-source":
            sub.add_argument("--entity", required=True)
            sub.add_argument("--week", type=int)
        if command in {"inventory-source", "import-history", "hydrate-history"}:
            sub.add_argument("--prefix", default="")
            if command == "import-history":
                sub.add_argument(
                    "--skip-imports",
                    action="store_true",
                    help="Skip raw capture imports and run downstream Silver/Gold steps",
                )
        if command == "audit-data":
            sub.add_argument(
                "--mode",
                choices=("structural", "model-ready", "exact-market"),
                default="model-ready",
            )
        if command == "build-silver":
            sub.add_argument("--dataset", required=True)
            sub.add_argument("--capture-id", action="append", required=True)
            sub.add_argument("--games-ref-uri")
            sub.add_argument("--week-policy-ref-uri")
            sub.add_argument("--output-ref-uri", required=True)
        if command == "build-team-game":
            sub.add_argument("--plays-ref-uri", required=True)
            sub.add_argument("--games-ref-uri", required=True)
            sub.add_argument("--teams-ref-uri")
            sub.add_argument("--venues-ref-uri")
            sub.add_argument("--weather-ref-uri")
            sub.add_argument("--game-stats-ref-uri")
            sub.add_argument("--corrections-ref-uri", required=True)
            sub.add_argument("--output-ref-uri", required=True)
        if command == "build-features":
            sub.add_argument("--matchups-ref-uri", required=True)
            sub.add_argument("--schedule-ref-uri", required=True)
            sub.add_argument("--baselines-ref-uri")
            sub.add_argument("--output-ref-uri", required=True)
        if command == "build-baselines":
            sub.add_argument("--core-ref-uri", required=True)
            sub.add_argument("--output-ref-uri", required=True)
            sub.add_argument("--include-locked-2025", action="store_true")
            sub.add_argument("--frozen-design-sha")
        if command == "assemble-model-ready":
            sub.add_argument("--core-ref-uri", required=True)
            sub.add_argument("--baselines-ref-uri", required=True)
            sub.add_argument("--markets-ref-uri")
            sub.add_argument("--preseason-features-ref-uri")
            sub.add_argument("--feature-track", choices=("strict", "reconstructed"))
            sub.add_argument("--output-ref-uri", required=True)
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    try:
        conn_url = resolve_runtime_target(args.environment).database_url
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    if (
        args.command in {"inventory-source", "import-history", "hydrate-history"}
        and args.environment != "preview"
    ):
        raise SystemExit(
            "Historical bootstrap operations are permitted only in preview"
        )
    os.environ["DATABASE_URL"] = conn_url
    os.environ["CFB_ARTIFACT_ENV"] = args.environment
    os.environ["CFB_RUNTIME_TARGET_RESOLVED"] = args.environment
    context = new_context(
        command=args.command,
        environment=args.environment,
        season=args.year,
        week=getattr(args, "week", None),
        as_of=getattr(args, "as_of", None),
        pipeline_run_id=args.pipeline_run_id,
    )
    steps = build_steps(
        context,
        conn_url=conn_url,
        waiver=getattr(args, "waiver", None),
        options=args,
    )
    with PostgresStateStore(conn_url) as store:
        StateMachine(
            store,
            crash_after_step=getattr(args, "crash_after_step", None),
            notifier=WebhookFailureNotifier.from_env(),
        ).run(context, steps)


if __name__ == "__main__":
    main()
