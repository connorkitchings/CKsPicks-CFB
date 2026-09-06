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


def _source_subprocess_timeout_seconds() -> float:
    """Return the hard deadline for one resumable source-capture child."""

    value = float(os.getenv("CFB_SOURCE_SUBPROCESS_TIMEOUT_SECONDS", "600"))
    if value <= 0:
        raise ValueError("CFB_SOURCE_SUBPROCESS_TIMEOUT_SECONDS must be positive")
    return value


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
        timeout_seconds = _source_subprocess_timeout_seconds()
        try:
            completed = subprocess.run(
                list(argv),
                check=False,
                timeout=timeout_seconds,
                env={
                    **os.environ,
                    "PYTHONPATH": ".:src",
                    "CFB_INGESTION_RUN_ID": ingestion_run_id,
                },
            )
        except subprocess.TimeoutExpired as exc:
            from cks_picks_cfb.data.catalog import finish_ingestion_run

            finish_ingestion_run(
                conn_url,
                ingestion_run_id,
                succeeded=False,
                error_category="subprocess_timeout",
                error_detail=f"{entity} exceeded {timeout_seconds:g} seconds",
            )
            raise RuntimeError(
                f"Source step {entity} exceeded its {timeout_seconds:g}-second "
                "subprocess deadline"
            ) from exc
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
        definition={
            "argv": list(argv),
            "entity": entity,
            "subprocess_timeout_seconds": _source_subprocess_timeout_seconds(),
        },
        resume_validator=resume_validator,
    )


def _soft_fail_market_quotes_step(
    *, conn_url: str, year: int, week: int
) -> PipelineStep:
    """Opt-in live The Odds API capture; provider errors degrade to CFBD-only.

    Markets are evaluation-only: when the step is enabled but the provider
    fails, a loud warning is emitted (stderr + best-effort webhook) and the
    publish proceeds on the CFBD capture alone. The step records its status
    durably in the run's step outputs so a degraded capture is never a silent
    success.
    """

    def _warn(context: OperationContext, category: str, detail: str) -> None:
        message = (
            f"WARNING: the_odds_api market capture degraded to CFBD-only "
            f"({context.pipeline_run_id} ingest_market_quotes): {category}: {detail}"
        )
        print(message, file=sys.stderr)
        try:
            from cks_picks_cfb.ops.notifier import WebhookFailureNotifier

            notifier = WebhookFailureNotifier.from_env()
            if notifier is not None:
                notifier.notify(
                    context,
                    "ingest_market_quotes",
                    category=category,
                    detail=detail,
                )
        except Exception:  # pragma: no cover - notification is best effort
            pass

    def action(context: OperationContext) -> Sequence[Mapping[str, Any]]:
        if os.getenv("CFB_ODDS_API_ENABLED", "0") != "1":
            return [{"status": "skipped", "reason": "CFB_ODDS_API_ENABLED != 1"}]
        if not os.getenv("THE_ODDS_API_KEY"):
            return [{"status": "skipped", "reason": "THE_ODDS_API_KEY not set"}]
        argv = _python(
            "scripts/data/fetch_odds_api_market_quotes.py",
            "--year",
            year,
            "--week",
            week,
            "--confirm",
        )
        ingestion_run_id = f"{context.pipeline_run_id}:market_quotes"
        timeout_seconds = _source_subprocess_timeout_seconds()
        try:
            completed = subprocess.run(
                list(argv),
                check=False,
                timeout=timeout_seconds,
                env={
                    **os.environ,
                    "PYTHONPATH": ".:src",
                    "CFB_INGESTION_RUN_ID": ingestion_run_id,
                },
            )
        except subprocess.TimeoutExpired as exc:
            _warn(
                context,
                "subprocess_timeout",
                f"the_odds_api capture exceeded {timeout_seconds:g} seconds: {exc}",
            )
            return [
                {
                    "status": "degraded",
                    "error_category": "subprocess_timeout",
                    "ingestion_run_id": ingestion_run_id,
                }
            ]
        if completed.returncode != 0:
            _warn(
                context,
                "subprocess_error",
                f"the_odds_api capture exited {completed.returncode}",
            )
            return [
                {
                    "status": "degraded",
                    "error_category": "subprocess_error",
                    "returncode": completed.returncode,
                    "ingestion_run_id": ingestion_run_id,
                }
            ]
        with psycopg.connect(conn_url) as conn:
            rows = conn.execute(
                "SELECT capture_id FROM catalog.source_captures "
                "WHERE ingestion_run_id = %s AND provider = 'the_odds_api' "
                "AND state = 'registered' ORDER BY captured_at, capture_id",
                (ingestion_run_id,),
            ).fetchall()
        if not rows:
            _warn(
                context,
                "no_registered_capture",
                "the_odds_api subprocess succeeded but registered no captures",
            )
            return [
                {
                    "status": "degraded",
                    "error_category": "no_registered_capture",
                    "ingestion_run_id": ingestion_run_id,
                }
            ]
        return tuple(
            {
                "status": "captured",
                "capture_id": str(row[0]),
                "provider": "the_odds_api",
            }
            for row in rows
        )

    def resume_validator(
        _: OperationContext, outputs: Sequence[Mapping[str, Any]]
    ) -> bool:
        # Never re-issue a paid provider request on resume: skipped and
        # degraded outcomes are final for this run, and captured rows must
        # still exist in the catalog to be skipped.
        if not outputs:
            return False
        statuses = {str(output.get("status")) for output in outputs}
        if not statuses <= {"skipped", "degraded", "captured"}:
            return False
        capture_ids = [
            str(output["capture_id"])
            for output in outputs
            if output.get("capture_id") is not None
        ]
        if not capture_ids:
            return True
        try:
            with psycopg.connect(conn_url) as conn:
                rows = conn.execute(
                    "SELECT capture_id FROM catalog.source_captures "
                    "WHERE capture_id = ANY(%s)",
                    (capture_ids,),
                ).fetchall()
        except Exception:
            return False
        return {str(row[0]) for row in rows} == set(capture_ids)

    return PipelineStep(
        "ingest_market_quotes",
        action,
        definition={
            "year": year,
            "week": week,
            "provider": "the_odds_api",
            "soft_fail": True,
            "subprocess_timeout_seconds": _source_subprocess_timeout_seconds(),
        },
        resume_validator=resume_validator,
    )


def _history_play_capture_step(
    *,
    season: int,
    conn_url: str,
    manifest_uri: str,
    games_manifest_uri: str,
    identity: Mapping[str, Any],
) -> PipelineStep:
    """Capture one successor R1 season as a resumable weekly request set."""

    def action(context: OperationContext) -> Sequence[Mapping[str, Any]]:
        from cks_picks_cfb.data.history_play_capture import HistoryPlayCaptureSet

        result = HistoryPlayCaptureSet(
            conn_url=conn_url,
            storage=get_storage(environment="preview"),
            pipeline_run_id=context.pipeline_run_id,
            season=season,
            manifest_uri=manifest_uri,
            identity=identity,
            games_manifest_uri=games_manifest_uri,
            write_compatibility_projection=False,
        ).run()
        return (
            {
                "manifest_uri": manifest_uri,
                "manifest_sha256": result["manifest_sha256"],
                "ingestion_run_id": result["ingestion_run_id"],
                "capture_ids": [entry["capture_id"] for entry in result["requests"]],
            },
        )

    def resume_validator(
        _: OperationContext, outputs: Sequence[Mapping[str, Any]]
    ) -> bool:
        if not outputs or not get_storage(environment="preview").exists(manifest_uri):
            return False
        try:
            raw = json.loads(
                get_storage(environment="preview").read_bytes(manifest_uri).decode()
            )
        except Exception:
            return False
        return (
            raw.get("contract_version") == "play-capture-set-v2"
            and raw.get("state") == "complete"
            and raw.get("identity") == dict(identity)
            and raw.get("manifest_sha256") == outputs[0].get("manifest_sha256")
        )

    from cks_picks_cfb.data.history_play_capture import load_history_play_capture_policy

    policy = load_history_play_capture_policy()
    return PipelineStep(
        f"capture_successor_history_{season}_plays",
        action,
        definition={
            "season": season,
            "entity": f"successor_history_{season}_plays",
            "manifest_uri": manifest_uri,
            "games_manifest_uri": games_manifest_uri,
            "policy_version": policy.version,
            "policy_sha256": policy.sha256,
            "identity": dict(identity),
            "capture_only": True,
        },
        resume_validator=resume_validator,
    )


def _successor_r1_identity() -> dict[str, str]:
    """Bind a full-corpus R1 run to code and immutable policy inputs."""

    from cks_picks_cfb.data.history_play_capture import load_history_play_capture_policy
    from cks_picks_cfb.data.history_source_capture import (
        load_history_source_capture_policy,
    )

    def sha(path: str) -> str:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    code_sha = completed.stdout.strip()
    if not code_sha:
        raise ValueError("Successor R1 requires a committed Git code identity")
    play_policy = load_history_play_capture_policy()
    source_policy = load_history_source_capture_policy()
    config_shas = {
        "season_lineage_sha256": sha("conf/ratings/successor_v2_season_lineage.yaml"),
        "play_capture_policy_sha256": play_policy.sha256,
        "source_capture_policy_sha256": source_policy.sha256,
        "measurement_config_sha256": sha("conf/ratings/measurement_successor_v2.yaml"),
        "state_config_sha256": sha("conf/ratings/team_state_successor_v2.yaml"),
    }
    return {
        "code_sha": code_sha,
        **config_shas,
        "configuration_sha256": hashlib.sha256(
            json.dumps(config_shas, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


SUCCESSOR_R1_COMMIT_PATHS = (
    "conf/ratings/history_play_capture_v2.yaml",
    "conf/ratings/history_source_capture_v2.yaml",
    "conf/ratings/measurement_successor_v2.yaml",
    "conf/ratings/successor_v2_season_lineage.yaml",
    "conf/ratings/team_state_successor_v2.yaml",
    "scripts/data/history_source_capture_worker.py",
    "scripts/pipeline/audit_successor_cross_lineage.py",
    "scripts/pipeline/build_history_silver.py",
    "scripts/pipeline/build_team_game_dataset.py",
    "scripts/pipeline/build_rating_measurements.py",
    "scripts/pipeline/build_rating_team_states.py",
    "scripts/pipeline/build_successor_history_ref_set.py",
    "scripts/pipeline/build_successor_legacy_comparison_ref_set.py",
    "scripts/pipeline/build_successor_r1_foundation.py",
    "scripts/pipeline/certify_successor_history.py",
    "src/cks_picks_cfb/data/catalog.py",
    "src/cks_picks_cfb/data/game_stats.py",
    "src/cks_picks_cfb/data/history_play_capture.py",
    "src/cks_picks_cfb/data/history_source_capture.py",
    "src/cks_picks_cfb/data/plays.py",
    "src/cks_picks_cfb/data/reconciliation.py",
    "src/cks_picks_cfb/data/schema_contracts.py",
    "src/cks_picks_cfb/data/venues.py",
    "src/cks_picks_cfb/features/situational.py",
    "src/cks_picks_cfb/ops/__main__.py",
    "src/cks_picks_cfb/ratings/audit.py",
    "src/cks_picks_cfb/ratings/cross_lineage.py",
    "src/cks_picks_cfb/ratings/state_audit.py",
    "src/cks_picks_cfb/ratings/state_contracts.py",
    "src/cks_picks_cfb/ratings/states.py",
    "src/cks_picks_cfb/ratings/successor_history.py",
)


def _verify_successor_r1_committed_code() -> str:
    """Require the implementation named by R1 manifests to be committed exactly."""

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    if not head:
        raise RuntimeError("Successor R1 requires a committed Git HEAD")
    for path in SUCCESSOR_R1_COMMIT_PATHS:
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            capture_output=True,
            text=True,
            check=False,
        )
        if tracked.returncode:
            raise RuntimeError(
                f"Successor R1 implementation path is not committed: {path}"
            )
    dirty = subprocess.run(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            *SUCCESSOR_R1_COMMIT_PATHS,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if dirty.stdout:
        raise RuntimeError(
            "Successor R1 implementation paths must be clean and committed before capture"
        )
    return head


def _successor_preview_runtime_step(identity: Mapping[str, Any]) -> PipelineStep:
    """Fail before R1 writes when Preview R2/CFBD isolation is not configured."""

    def action(_: OperationContext) -> Sequence[Mapping[str, Any]]:
        committed_code_sha = _verify_successor_r1_committed_code()
        if committed_code_sha != identity.get("code_sha"):
            raise RuntimeError("Successor R1 code SHA differs from its run identity")
        if os.getenv("CFB_STORAGE_BACKEND", "").lower() != "r2":
            raise RuntimeError("Successor R1 requires CFB_STORAGE_BACKEND=r2")
        if not os.getenv("PREVIEW_DATABASE_URL"):
            raise RuntimeError("Successor R1 requires PREVIEW_DATABASE_URL")
        if not os.getenv("CFBD_API_KEY"):
            raise RuntimeError("Successor R1 requires CFBD_API_KEY")
        try:
            get_storage(environment="preview")
        except (RuntimeError, ValueError) as exc:
            raise RuntimeError(
                f"Successor R1 Preview R2 isolation failed: {exc}"
            ) from exc
        return (
            {
                "environment": "preview",
                "storage_backend": "r2",
                "preview_database_configured": True,
                "cfbd_configured": True,
                "code_sha": committed_code_sha,
            },
        )

    return PipelineStep(
        "validate_successor_r1_preview_runtime",
        action,
        definition={
            "environment": "preview",
            "required_storage_backend": "r2",
            "required_credentials": ("PREVIEW_DATABASE_URL", "CFBD_API_KEY"),
            "identity": dict(identity),
        },
        resume_validator=lambda _, __: False,
    )


def _history_source_capture_step(
    *,
    season: int,
    entity: str,
    conn_url: str,
    manifest_uri: str,
    identity: Mapping[str, Any],
) -> PipelineStep:
    """Capture one non-play R1 entity without legacy compatibility writes."""

    def action(context: OperationContext) -> Sequence[Mapping[str, Any]]:
        from cks_picks_cfb.data.history_source_capture import HistorySourceCaptureSet

        result = HistorySourceCaptureSet(
            conn_url=conn_url,
            storage=get_storage(environment="preview"),
            pipeline_run_id=context.pipeline_run_id,
            season=season,
            entity=entity,
            manifest_uri=manifest_uri,
            identity=identity,
            games_manifest_uri=(
                manifest_uri.rsplit("/", 1)[0] + "/games.json"
                if entity in {"venues", "game_stats"}
                else None
            ),
        ).run()
        return (
            {
                "manifest_uri": manifest_uri,
                "manifest_sha256": result["manifest_sha256"],
                "ingestion_run_id": result["ingestion_run_id"],
                "capture_ids": [entry["capture_id"] for entry in result["requests"]],
            },
        )

    def resume_validator(
        _: OperationContext, outputs: Sequence[Mapping[str, Any]]
    ) -> bool:
        if not outputs or not get_storage(environment="preview").exists(manifest_uri):
            return False
        try:
            raw = json.loads(
                get_storage(environment="preview").read_bytes(manifest_uri).decode()
            )
        except Exception:
            return False
        return (
            raw.get("contract_version") == "source-capture-entity-set-v2"
            and raw.get("state") == "complete"
            and raw.get("identity") == dict(identity)
            and raw.get("manifest_sha256") == outputs[0].get("manifest_sha256")
        )

    return PipelineStep(
        f"capture_successor_history_{season}_{entity}",
        action,
        definition={
            "season": season,
            "entity": f"successor_history_{season}_{entity}",
            "manifest_uri": manifest_uri,
            "identity": dict(identity),
            "capture_only": True,
        },
        resume_validator=resume_validator,
    )


def _successor_source_set_step(
    *, manifest_uri: str, comparison_ref_set_uri: str, identity: Mapping[str, Any]
) -> PipelineStep:
    """Close the full R1 source manifest only after every exact set completes."""

    def action(context: OperationContext) -> Sequence[Mapping[str, Any]]:
        from cks_picks_cfb.data.season_lineage import load_season_lineage_policy

        policy = load_season_lineage_policy(
            "conf/ratings/successor_v2_season_lineage.yaml"
        )
        storage = get_storage(environment="preview")
        comparison = json.loads(storage.read_bytes(comparison_ref_set_uri).decode())
        if (
            comparison.get("contract_version")
            != "successor-legacy-comparison-ref-set-v1"
            or comparison.get("state") != "complete"
            or not comparison.get("manifest_sha256")
        ):
            raise RuntimeError("R1 comparison evidence manifest is not complete")
        entries = []
        for season in policy.historical_development_seasons:
            for entity in ("teams", "games", "venues", "game_stats", "plays"):
                entity_uri = (
                    f"{policy.research_prefix}/r1/{context.pipeline_run_id}/captures/"
                    f"{season}/{entity}.json"
                )
                if not storage.exists(entity_uri):
                    raise RuntimeError(
                        f"Missing complete R1 capture manifest: {entity_uri}"
                    )
                raw = json.loads(storage.read_bytes(entity_uri).decode())
                expected_version = (
                    "play-capture-set-v2"
                    if entity == "plays"
                    else "source-capture-entity-set-v2"
                )
                if (
                    raw.get("contract_version") != expected_version
                    or raw.get("state") != "complete"
                    or raw.get("identity") != dict(identity)
                    or raw.get("season") != season
                ):
                    raise RuntimeError(
                        f"Invalid complete R1 capture manifest: {entity_uri}"
                    )
                entries.append(
                    {
                        "season": season,
                        "entity": entity,
                        "manifest_uri": entity_uri,
                        "manifest_sha256": raw["manifest_sha256"],
                        "ingestion_run_id": raw["ingestion_run_id"],
                        "capture_ids": [item["capture_id"] for item in raw["requests"]],
                        "requests": raw["requests"],
                    }
                )
        payload: dict[str, Any] = {
            "contract_version": "successor-history-source-set-v2",
            "state": "complete",
            "pipeline_run_id": context.pipeline_run_id,
            "identity": dict(identity),
            "comparison_ref_set_uri": comparison_ref_set_uri,
            "comparison_ref_set_sha256": comparison["manifest_sha256"],
            "seasons": list(policy.historical_development_seasons),
            "entries": entries,
        }
        payload["manifest_sha256"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        encoded = json.dumps(payload, indent=2, sort_keys=True).encode()
        if storage.exists(manifest_uri):
            if storage.read_bytes(manifest_uri) != encoded:
                raise FileExistsError(
                    f"Immutable R1 source manifest collision: {manifest_uri}"
                )
        else:
            storage.write_bytes(encoded, manifest_uri)
        return (
            {
                "manifest_uri": manifest_uri,
                "manifest_sha256": payload["manifest_sha256"],
            },
        )

    def resume_validator(
        _: OperationContext, outputs: Sequence[Mapping[str, Any]]
    ) -> bool:
        if not outputs or not get_storage(environment="preview").exists(manifest_uri):
            return False
        try:
            raw = json.loads(
                get_storage(environment="preview").read_bytes(manifest_uri).decode()
            )
        except Exception:
            return False
        return (
            raw.get("contract_version") == "successor-history-source-set-v2"
            and raw.get("state") == "complete"
            and raw.get("identity") == dict(identity)
            and raw.get("comparison_ref_set_uri") == comparison_ref_set_uri
            and raw.get("manifest_sha256") == outputs[0].get("manifest_sha256")
        )

    return PipelineStep(
        "close_successor_history_source_set",
        action,
        definition={
            "manifest_uri": manifest_uri,
            "comparison_ref_set_uri": comparison_ref_set_uri,
            "identity": dict(identity),
        },
        resume_validator=resume_validator,
    )


def _reconcile_abandoned_history_play_capture_action(
    conn_url: str, ingestion_run_ids: Sequence[str]
):
    """Finalize only known-abandoned inner R1 captures after failed outer steps."""

    def action(_: OperationContext) -> Sequence[Mapping[str, Any]]:
        from cks_picks_cfb.data.catalog import finish_ingestion_run

        results: list[Mapping[str, Any]] = []
        with psycopg.connect(conn_url) as conn:
            for ingestion_run_id in ingestion_run_ids:
                if ":successor_history_2015_plays" not in ingestion_run_id:
                    raise ValueError(
                        "only abandoned 2015 successor play runs may reconcile"
                    )
                outer_run_id = ingestion_run_id.rsplit(":", 1)[0]
                row = conn.execute(
                    "SELECT i.state, p.state, s.state FROM catalog.ingestion_runs i "
                    "JOIN ops.pipeline_runs p ON p.pipeline_run_id = %s "
                    "JOIN ops.pipeline_steps s ON s.pipeline_run_id = p.pipeline_run_id "
                    "AND s.step_name = 'capture_successor_history_2015_plays' "
                    "WHERE i.ingestion_run_id = %s",
                    (outer_run_id, ingestion_run_id),
                ).fetchone()
                if not row:
                    raise LookupError(
                        f"No failed outer evidence for {ingestion_run_id}"
                    )
                if tuple(str(value) for value in row) != (
                    "running",
                    "failed",
                    "failed",
                ):
                    raise ValueError(
                        "reconciliation requires running inner capture and failed outer step"
                    )
                results.append(
                    {"ingestion_run_id": ingestion_run_id, "state": "failed"}
                )
        for result in results:
            finish_ingestion_run(
                conn_url,
                str(result["ingestion_run_id"]),
                succeeded=False,
                error_category="reconciled_abandoned_operation",
                error_detail="Outer successor R1 play step was already failed; preserved diagnostic evidence.",
            )
        return tuple(results)

    return action


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
    # Source and Preview may intentionally share an R2 bucket. Immutable path
    # namespaces plus distinct Neon branches provide the isolation boundary.
    objects = inventory_historical_source(source, prefix=prefix)
    eligible = []
    for item in objects:
        if item.years & FORBIDDEN_YEARS:
            continue
        if PRIOR_ONLY_2019_ENTITIES and (
            2019 in item.years and item.entity not in PRIOR_ONLY_2019_ENTITIES
        ):
            continue
        eligible.append(item)
    return source, destination, objects, eligible


def _rating_history_silver_steps(
    *, environment: str, as_of: str, pipeline_run_id: str
) -> list[PipelineStep]:
    """Build full-corpus R1 refs from one complete source-set manifest."""

    from cks_picks_cfb.data.season_lineage import load_season_lineage_policy

    policy = load_season_lineage_policy("conf/ratings/successor_v2_season_lineage.yaml")
    prefix = f"{policy.research_prefix}/r1/{pipeline_run_id}"
    source_set_uri = f"{prefix}/source-set.json"
    steps: list[PipelineStep] = []

    def add(dataset: str, season: int, *, games: bool = False) -> None:
        argv = _python(
            "scripts/pipeline/build_history_silver.py",
            "--dataset",
            dataset,
            "--season",
            season,
            "--as-of",
            as_of,
            "--output-ref-uri",
            f"{prefix}/refs/{dataset}-{season}.json",
            "--identity-label",
            "rating_successor_v2_r1_full_corpus",
            "--environment",
            environment,
            "--source-set-uri",
            source_set_uri,
        )
        if games:
            argv.extend(["--games-ref-uri", f"{prefix}/refs/games-{season}.json"])
        steps.append(subprocess_step(f"successor_silver_{dataset}_{season}", argv))

    for season in policy.historical_development_seasons:
        for dataset in ("teams", "venues", "games", "game_outcomes"):
            add(dataset, season)
        add("plays", season, games=True)
        add("team_game_stats", season)
        steps.append(
            subprocess_step(
                f"successor_reconciled_team_game_{season}",
                _python(
                    "scripts/pipeline/build_team_game_dataset.py",
                    "--plays-ref-uri",
                    f"{prefix}/refs/plays-{season}.json",
                    "--games-ref-uri",
                    f"{prefix}/refs/games-{season}.json",
                    "--teams-ref-uri",
                    f"{prefix}/refs/teams-{season}.json",
                    "--venues-ref-uri",
                    f"{prefix}/refs/venues-{season}.json",
                    "--game-stats-ref-uri",
                    f"{prefix}/refs/team_game_stats-{season}.json",
                    "--play-capture-manifest-uri",
                    f"{prefix}/captures/{season}/plays.json",
                    "--corrections-ref-uri",
                    "artifacts/preview/refs/data-corrections-v1.json",
                    "--as-of",
                    as_of,
                    "--output-ref-uri",
                    f"{prefix}/refs/reconciled_team_game-{season}.json",
                    "--output-ref-set-uri",
                    f"{prefix}/derived/{season}/rating-input-ref-set.json",
                    "--environment",
                    environment,
                ),
            )
        )
    return steps


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
    if context.command == "prepare-rating-history":
        assert options is not None and as_of is not None
        if year != 2026:
            raise ValueError(
                "prepare-rating-history uses --year 2026 as its protected context"
            )
        from cks_picks_cfb.data.season_lineage import load_season_lineage_policy

        policy = load_season_lineage_policy(
            "conf/ratings/successor_v2_season_lineage.yaml"
        )
        identity = _successor_r1_identity()
        prefix = f"{policy.research_prefix}/r1/{context.pipeline_run_id}"
        comparison_ref_set_uri = f"{prefix}/comparison-ref-set.json"
        steps: list[PipelineStep] = [_successor_preview_runtime_step(identity)]
        comparison_argv = _python(
            "scripts/pipeline/build_successor_legacy_comparison_ref_set.py",
            "--environment",
            environment,
            "--as-of",
            as_of,
            "--output-uri",
            comparison_ref_set_uri,
        )
        if getattr(options, "comparison_ref_set_uri", None):
            comparison_argv.extend(
                ["--comparison-ref-set-uri", options.comparison_ref_set_uri]
            )
        steps.append(
            subprocess_step(
                "freeze_successor_legacy_comparison_evidence", comparison_argv
            )
        )
        if not options.skip_capture:
            for season in policy.historical_development_seasons:
                for entity in ("teams", "games", "venues", "game_stats"):
                    steps.append(
                        _history_source_capture_step(
                            season=season,
                            entity=entity,
                            conn_url=conn_url,
                            manifest_uri=f"{prefix}/captures/{season}/{entity}.json",
                            identity=identity,
                        )
                    )
                steps.append(
                    _history_play_capture_step(
                        season=season,
                        conn_url=conn_url,
                        manifest_uri=f"{prefix}/captures/{season}/plays.json",
                        games_manifest_uri=f"{prefix}/captures/{season}/games.json",
                        identity=identity,
                    )
                )
            steps.append(
                _successor_source_set_step(
                    manifest_uri=f"{prefix}/source-set.json",
                    comparison_ref_set_uri=comparison_ref_set_uri,
                    identity=identity,
                )
            )
        steps.extend(
            _rating_history_silver_steps(
                environment=environment,
                as_of=as_of,
                pipeline_run_id=context.pipeline_run_id,
            )
        )
        steps.append(
            subprocess_step(
                "close_successor_history_derived_ref_set",
                _python(
                    "scripts/pipeline/build_successor_history_ref_set.py",
                    "--environment",
                    environment,
                    "--source-set-uri",
                    f"{prefix}/source-set.json",
                    "--output-uri",
                    f"{prefix}/derived-ref-set.json",
                ),
            )
        )
        from cks_picks_cfb.ratings.contracts import load_measurement_config
        from cks_picks_cfb.ratings.state_contracts import load_team_state_config

        measurement = load_measurement_config(
            "conf/ratings/measurement_successor_v2.yaml"
        )
        states = load_team_state_config("conf/ratings/team_state_successor_v2.yaml")
        measurement_prefix = f"{prefix}/foundation/measurements/{measurement.design_id}"
        state_prefix = f"{prefix}/foundation/states/{states.design_id}"
        steps.extend(
            [
                subprocess_step(
                    "audit_successor_cross_lineage",
                    _python(
                        "scripts/pipeline/audit_successor_cross_lineage.py",
                        "--environment",
                        environment,
                        "--derived-ref-set-uri",
                        f"{prefix}/derived-ref-set.json",
                        "--comparison-ref-set-uri",
                        comparison_ref_set_uri,
                        "--report-uri",
                        f"{prefix}/cross-lineage.json",
                    ),
                ),
                subprocess_step(
                    "build_successor_r1_foundation",
                    _python(
                        "scripts/pipeline/build_successor_r1_foundation.py",
                        "--environment",
                        environment,
                        "--as-of",
                        as_of,
                        "--derived-ref-set-uri",
                        f"{prefix}/derived-ref-set.json",
                        "--output-manifest-uri",
                        f"{prefix}/foundation/manifest.json",
                    ),
                ),
                subprocess_step(
                    "certify_successor_history",
                    _python(
                        "scripts/pipeline/certify_successor_history.py",
                        "--environment",
                        environment,
                        "--derived-ref-set-uri",
                        f"{prefix}/derived-ref-set.json",
                        "--measurement-report-uri",
                        f"{measurement_prefix}/report.json",
                        "--state-report-uri",
                        f"{state_prefix}/report.json",
                        "--cross-lineage-report-uri",
                        f"{prefix}/cross-lineage.json",
                        "--expanded-ref-set-uri",
                        f"{prefix}/ref-set.json",
                        "--coverage-report-uri",
                        f"{prefix}/coverage.json",
                    ),
                ),
            ]
        )
        return steps
    if context.command == "verify-history-play-sample":
        assert options is not None
        if year != 2026:
            raise ValueError(
                "verify-history-play-sample uses --year 2026 as protected context"
            )
        return [
            subprocess_step(
                "verify_2015_week_1_play_compatibility",
                _python(
                    "scripts/data/verify_history_play_sample.py",
                    "--history-season",
                    options.history_season,
                    "--provider-week",
                    options.provider_week,
                    "--expected-play-count",
                    options.expected_play_count,
                ),
            )
        ]
    if context.command == "reconcile-history-play-captures":
        assert options is not None
        return [
            PipelineStep(
                "reconcile_abandoned_history_play_captures",
                _reconcile_abandoned_history_play_capture_action(
                    conn_url, options.ingestion_run_id
                ),
                definition={"ingestion_run_ids": list(options.ingestion_run_id)},
            )
        ]
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
            "--environment",
            environment,
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
            "--environment",
            environment,
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
                argv.extend(["--season", str(historic_year)])
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
            _soft_fail_market_quotes_step(conn_url=conn_url, year=year, week=week),
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
        "prepare-rating-history",
        "verify-history-play-sample",
        "reconcile-history-play-captures",
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
            "prepare-rating-history",
            "verify-history-play-sample",
            "reconcile-history-play-captures",
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
            "prepare-rating-history",
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
        if command in {
            "inventory-source",
            "import-history",
            "hydrate-history",
            "prepare-rating-history",
            "verify-history-play-sample",
            "reconcile-history-play-captures",
        }:
            sub.add_argument("--prefix", default="")
            if command == "import-history":
                sub.add_argument(
                    "--skip-imports",
                    action="store_true",
                    help="Skip raw capture imports and run downstream Silver/Gold steps",
                )
            if command == "prepare-rating-history":
                sub.add_argument(
                    "--comparison-ref-set-uri",
                    help=(
                        "Optional immutable legacy 2019/2021–2025 comparison "
                        "evidence override; otherwise resolve it from Preview catalog."
                    ),
                )
                sub.add_argument(
                    "--skip-capture",
                    action="store_true",
                    help=(
                        "Run downstream-only recovery from an existing complete "
                        "full-corpus R1 source-set manifest."
                    ),
                )
            if command == "verify-history-play-sample":
                sub.add_argument("--history-season", type=int, default=2015)
                sub.add_argument("--provider-week", type=int, default=1)
                sub.add_argument("--expected-play-count", type=int, default=15369)
            if command == "reconcile-history-play-captures":
                sub.add_argument("--ingestion-run-id", action="append", required=True)
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
        args.command
        in {
            "inventory-source",
            "import-history",
            "hydrate-history",
            "prepare-rating-history",
            "verify-history-play-sample",
            "reconcile-history-play-captures",
        }
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
