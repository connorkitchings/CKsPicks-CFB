"""Manual, evidence-bound V5 weekly stage controller.

The controller records research applies in the existing ops state machine. It
never turns a successful preflight into an apply without a separate invocation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

import requests

from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ops.contracts import OperationContext
from cks_picks_cfb.ops.state_machine import (
    PipelineStep,
    PostgresStateStore,
    StateMachine,
)

COMPONENT_STAGE = {
    "repair": "refresh",
    "measurement": "refresh",
    "rating": "refresh",
    "forecast": "forecast",
    "readiness": "forecast",
    "prepare": "publish",
    "publish": "publish",
    "freeze": "freeze",
    "close": "close",
}
ORDER = tuple(COMPONENT_STAGE)
SCRIPTS = {
    "repair": "scripts/research/run_data_first_repair_v2.py",
    "measurement": "scripts/research/run_data_first_possession_measurements.py",
    "rating": "scripts/research/run_data_first_possession_rating_replay.py",
    "forecast": "scripts/research/run_v5_live_forecast.py",
    "readiness": "scripts/research/run_v5_shadow_readiness.py",
    "prepare": "scripts/pipeline/generate_weekly_bets.py",
}
VERIFIERS = {
    "repair": "scripts/research/verify_data_first_repair_v3.py",
    "measurement": "scripts/research/verify_data_first_possession_measurements.py",
    "rating": "scripts/research/verify_data_first_possession_rating_replay.py",
    "forecast": "scripts/research/run_v5_live_forecast.py",
    "readiness": "scripts/research/verify_v5_shadow.py",
}
ARGUMENTS = {
    "repair": {"season-2026-inputs-uri", "repair-v2-anchor-uri"},
    "measurement": {"repair-manifest-uri"},
    "rating": {
        "measurement-manifest-uri",
        "historical-rating-manifest-uri",
        "recruiting-manifest-uri",
        "returning-production-manifest-uri",
        "coaches-manifest-uri",
    },
    "forecast": {"measurement-manifest-uri", "rating-manifest-uri", "schedule-ref-uri"},
    "readiness": {
        "candidate-manifest-uri",
        "rating-manifest-uri",
        "measurement-manifest-uri",
        "repair-manifest-uri",
        "v4-prediction-ref-uri",
        "input-refs-uri",
        "slate-ref-uri",
    },
    "prepare": {"dataset-refs-uri"},
}
REQUIRED = {
    "repair": {"season-2026-inputs-uri", "repair-v2-anchor-uri"},
    "measurement": {"repair-manifest-uri"},
    "rating": ARGUMENTS["rating"],
    "forecast": ARGUMENTS["forecast"],
    "readiness": ARGUMENTS["readiness"],
    "prepare": {"dataset-refs-uri"},
}
EVIDENCE_ARGUMENT = {"measurement", "rating", "forecast", "readiness"}


class V5CycleError(ValueError):
    """A stage is unsafe or inconsistent with its reviewed descriptor."""


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def _clean_committed() -> None:
    result = subprocess.run(
        ["git", "status", "--porcelain"], check=True, capture_output=True, text=True
    )
    if result.stdout.strip():
        raise V5CycleError("apply requires a completely clean committed worktree")


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _runner_env(spec: CycleSpec) -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONPATH": ".:src",
        "CFB_ARTIFACT_ENV": spec.environment,
    }


def _read_json_output(stdout: str) -> dict[str, Any]:
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        result = None
        decoder = json.JSONDecoder()
        for offset, char in enumerate(stdout):
            if char != "{":
                continue
            try:
                candidate, end = decoder.raw_decode(stdout[offset:])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and not stdout[offset + end :].strip():
                result = candidate
                break
    if not isinstance(result, dict):
        raise V5CycleError("component did not return a JSON object")
    return result


@dataclass(frozen=True)
class CycleSpec:
    cycle_id: str
    season: int
    week: int
    environment: str
    code_sha: str
    components: Mapping[str, Mapping[str, Any]]

    @classmethod
    def load(cls, path: Path) -> "CycleSpec":
        raw = json.loads(path.read_text())
        if raw.get("schema_version") != "v5_weekly_cycle_v1":
            raise V5CycleError("unexpected cycle descriptor version")
        cycle_id = str(raw.get("cycle_id", ""))
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{5,63}", cycle_id):
            raise V5CycleError("cycle_id must be a stable lowercase identifier")
        if raw.get("environment") not in {"preview", "production"}:
            raise V5CycleError("invalid cycle environment")
        if int(raw.get("season", 0)) != 2026 or not 0 <= int(raw.get("week", -1)) <= 20:
            raise V5CycleError("cycle must target a valid 2026 week")
        components = raw.get("components")
        if not isinstance(components, dict) or set(components) - set(ORDER):
            raise V5CycleError("cycle components are invalid")
        if not re.fullmatch(r"[0-9a-f]{40}", str(raw.get("code_sha", ""))):
            raise V5CycleError("cycle requires an exact committed code SHA")
        return cls(
            cycle_id,
            int(raw["season"]),
            int(raw["week"]),
            str(raw["environment"]),
            str(raw["code_sha"]),
            components,
        )

    def component(self, name: str) -> Mapping[str, Any]:
        if name not in self.components:
            raise V5CycleError(f"descriptor lacks {name}")
        item = self.components[name]
        if not isinstance(item, dict):
            raise V5CycleError("component must be an object")
        if name in SCRIPTS:
            if name != "prepare" and self.environment != "preview":
                raise V5CycleError("research applications are Preview-only")
            args = item.get("arguments")
            if not isinstance(args, dict) or set(args) != REQUIRED[name]:
                raise V5CycleError(f"{name} requires exact named arguments")
            if not all(isinstance(value, str) and value for value in args.values()):
                raise V5CycleError("component arguments must be nonempty strings")
            if (
                not item.get("run_id")
                or not item.get("as_of")
                or not item.get("config")
            ):
                raise V5CycleError("component requires run_id, as_of, and config")
            if name in {"readiness", "prepare"} and not item.get("run_id"):
                raise V5CycleError("run_id is required")
        else:
            if not item.get("run_id") or not item.get("as_of"):
                raise V5CycleError("ops component requires run_id and as_of")
            if name == "publish" and not item.get("config"):
                raise V5CycleError("publish requires a serving config")
            if name == "close" and not item.get("outcomes_ref_uri"):
                raise V5CycleError("close requires a certified outcomes reference")
        return item

    def pipeline_id(self, component: str) -> str:
        return f"v5-cycle-{self.cycle_id}-{component}"


def _bound_inputs(
    spec: CycleSpec, component: str, item: Mapping[str, Any]
) -> dict[str, Any]:
    if _git_sha() != spec.code_sha:
        raise V5CycleError("code SHA differs from reviewed cycle")
    config_sha = None
    if item.get("config"):
        config = Path(str(item["config"]))
        if not config.is_file():
            raise V5CycleError("component config is missing")
        config_sha = digest(config.read_bytes())
        if config_sha != item.get("config_sha256"):
            raise V5CycleError("component config checksum changed")
    parents = item.get("parents")
    if not isinstance(parents, dict):
        raise V5CycleError("component requires exact parent checksums")
    if component in SCRIPTS:
        uri_args = {
            value for key, value in item["arguments"].items() if key.endswith("-uri")
        }
        if set(parents) != uri_args:
            raise V5CycleError("every parent URI must have one expected checksum")
    elif component == "close" and item["outcomes_ref_uri"] not in parents:
        raise V5CycleError("close must bind its certified outcomes reference")
    storage = get_storage(
        environment=spec.environment if component not in VERIFIERS else "preview"
    )
    for uri, expected in parents.items():
        if not re.fullmatch(r"[0-9a-f]{64}", str(expected)):
            raise V5CycleError("invalid parent checksum")
        if digest(storage.read_bytes(uri)) != expected:
            raise V5CycleError(f"parent checksum changed: {uri}")
    return {
        "schema_version": "v5_cycle_component_v1",
        "cycle_id": spec.cycle_id,
        "component": component,
        "season": spec.season,
        "week": spec.week,
        "environment": spec.environment,
        "code_sha": spec.code_sha,
        "run_id": item["run_id"],
        "as_of": item["as_of"],
        "config": str(item.get("config") or ""),
        "config_sha256": config_sha,
        "arguments": item.get("arguments") or {},
        "parents": parents,
        "outcomes_ref_uri": item.get("outcomes_ref_uri"),
    }


def _verified_result(
    spec: CycleSpec, component: str, item: Mapping[str, Any], output: Mapping[str, Any]
) -> dict[str, Any]:
    if component == "prepare":
        uri = output.get("artifact_uri")
        sha = output.get("artifact_sha256")
        if not uri or not sha:
            raise V5CycleError("prepared run has no immutable artifact identity")
        storage = get_storage(environment=spec.environment)
        if digest(storage.read_bytes(str(uri))) != sha:
            raise V5CycleError("prepared artifact checksum mismatch")
        return {"manifest_uri": None, "artifact_uri": uri, "artifact_sha256": sha}
    manifest_uri = output.get("manifest_uri")
    if not manifest_uri:
        raise V5CycleError("component apply returned no terminal manifest URI")
    storage = get_storage(environment="preview")
    raw_sha = digest(storage.read_bytes(str(manifest_uri)))
    argv = [sys.executable, VERIFIERS[component], "--expected-code-sha", spec.code_sha]
    if component == "forecast":
        argv = _command(spec, component, item, apply=False) + [
            "--verify-manifest-uri",
            str(manifest_uri),
        ]
    else:
        argv += ["--manifest-uri", str(manifest_uri), "--environment", "preview"]
        if component == "repair":
            argv += ["--expected-state", "repaired_live_only"]
        if component == "readiness":
            argv += ["--write-manifest"]
    report = _read_json_output(
        subprocess.run(
            argv,
            check=True,
            capture_output=True,
            text=True,
            env=_runner_env(spec),
        ).stdout
    )
    if report.get("verified") is not True and report.get("status") != "verified":
        raise V5CycleError("independent verifier rejected the component")
    return {
        "manifest_uri": manifest_uri,
        "manifest_sha256": raw_sha,
        "verifier": report,
    }


def _command(
    spec: CycleSpec,
    component: str,
    item: Mapping[str, Any],
    *,
    apply: bool,
    evidence: Path | None = None,
) -> list[str]:
    argv = [sys.executable, SCRIPTS[component]]
    if component == "prepare":
        argv += [
            "--year",
            str(spec.season),
            "--week",
            str(spec.week),
            "--run-id",
            str(item["run_id"]),
            "--run-state",
            "preview",
        ]
        if spec.environment == "production":
            argv.append("--prepare-only")
    else:
        argv += [
            "--run-id",
            str(item["run_id"]),
            "--expected-code-sha",
            spec.code_sha,
            "--environment",
            "preview",
        ]
    argv += ["--as-of", str(item["as_of"]), "--config", str(item["config"])]
    if component == "repair":
        argv += ["--scope", "season_2026"]
    if component == "readiness":
        argv += ["--season", str(spec.season), "--week", str(spec.week), "--replay"]
    for key, value in sorted(item["arguments"].items()):
        argv += [f"--{key}", str(value)]
    if apply:
        argv.append("--upload-artifact" if component == "prepare" else "--apply")
        if component in EVIDENCE_ARGUMENT:
            if evidence is None:
                raise V5CycleError("reviewed preflight evidence is required")
            argv += ["--preflight-evidence", str(evidence)]
    return argv


def preflight(spec: CycleSpec, component: str, evidence_path: Path) -> dict[str, Any]:
    item = spec.component(component)
    bound = _bound_inputs(spec, component, item)
    if component in SCRIPTS:
        result = subprocess.run(
            _command(spec, component, item, apply=False),
            check=True,
            capture_output=True,
            text=True,
            env=_runner_env(spec),
        )
        output = _read_json_output(result.stdout)
    else:
        output = _preflight_ops(spec, component, item)
    evidence = {
        "binding": bound,
        "binding_sha256": digest(_json_bytes(bound)),
        "result": output,
        "result_sha256": digest(_json_bytes(output)),
    }
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True))
    return evidence


def _preflight_ops(
    spec: CycleSpec, component: str, item: Mapping[str, Any]
) -> dict[str, Any]:
    import psycopg

    conn_url = resolve_runtime_target(spec.environment).database_url
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        if component == "publish":
            from cks_picks_cfb.artifacts import (
                prediction_run_manifest_path,
                read_json_artifact,
                read_verified_csv_artifact,
            )
            from cks_picks_cfb.ops.v5_release import require_release_record
            from scripts.pipeline.publish_to_db import (
                _load_provenance,
                prepare_predictions,
                verify_v5_publication_boundary,
            )

            storage = get_storage(environment=spec.environment)
            manifest = read_json_artifact(
                prediction_run_manifest_path(spec.season, spec.week, item["run_id"]),
                storage,
            )
            if manifest.get("evidence_class") != "pending":
                raise V5CycleError("publication requires prospective V5 evidence")
            cfg, system_name, model_id, _ = _load_provenance(Path(str(item["config"])))
            if manifest.get("system_name") != system_name:
                raise V5CycleError("prepared run system name differs from config")
            verify_v5_publication_boundary(
                manifest=manifest,
                config_path=Path(cfg),
                model_id=model_id,
                season=spec.season,
                week=spec.week,
                predictions=prepare_predictions(
                    read_verified_csv_artifact(manifest, storage)
                ),
            )
            if spec.environment == "production":
                require_release_record(
                    cur,
                    manifest=manifest,
                    storage=storage,
                    season=spec.season,
                    week=spec.week,
                )
            return {
                "run_id": item["run_id"],
                "artifact_sha256": manifest["artifact_sha256"],
            }
        cur.execute(
            "SELECT pr.run_id, pr.state, pr.expected_games, pr.predicted_games, "
            "pr.lined_games, pr.evidence_class, "
            "(SELECT MIN(g.start_date) FROM predictions p JOIN games g "
            "ON g.game_id = p.game_id WHERE p.run_id = pr.run_id), NOW() "
            "FROM current_week cw JOIN prediction_runs pr ON pr.run_id = cw.active_run_id "
            "WHERE cw.id = 1 AND cw.season = %s AND cw.week = %s",
            (spec.season, spec.week),
        )
        row = cur.fetchone()
    if row is None or row[0] != item["run_id"]:
        raise V5CycleError("selected run differs from the reviewed component")
    run_id, state, expected, predicted, lined, evidence_class, first_kickoff, now = row
    if component == "freeze":
        if state != "published" or evidence_class != "pending":
            raise V5CycleError("freeze requires a published prospective run")
        if first_kickoff is None or now >= first_kickoff - timedelta(hours=1):
            raise V5CycleError("one-hour freeze boundary has passed")
        if predicted != expected or lined != expected:
            raise V5CycleError("freeze requires complete paired and lined coverage")
    elif component == "close":
        if state != "frozen" or evidence_class != "live":
            raise V5CycleError("close requires the selected live frozen run")
        stabilized = datetime.fromisoformat(
            str(item.get("finals_stabilized_at", "")).replace("Z", "+00:00")
        )
        cutoff = datetime.fromisoformat(str(item["as_of"]).replace("Z", "+00:00"))
        if (
            stabilized.tzinfo is None
            or cutoff.tzinfo is None
            or cutoff < stabilized + timedelta(hours=24)
        ):
            raise V5CycleError("certified finals have not stabilized for 24 hours")
        _check_outcomes_complete(
            spec, item, conn_url=conn_url, prediction_run_id=str(run_id)
        )
    return {
        "run_id": run_id,
        "state": state,
        "expected_games": expected,
        "predicted_games": predicted,
        "lined_games": lined,
    }


def _check_outcomes_complete(
    spec: CycleSpec,
    item: Mapping[str, Any],
    *,
    conn_url: str,
    prediction_run_id: str,
) -> None:
    """Require one certified final for every game in the selected frozen run."""
    import psycopg

    from cks_picks_cfb.data.lake import DatasetRef, read_dataset

    storage = get_storage(environment=spec.environment)
    ref = json.loads(storage.read_bytes(str(item["outcomes_ref_uri"])))
    if ref.get("dataset") != "game_outcomes":
        raise V5CycleError("close source is not Silver game_outcomes")
    dataset_ref = DatasetRef(
        **{
            key: ref[key]
            for key in ("dataset", "version_id", "schema_version", "content_sha", "uri")
        }
    )
    outcomes = read_dataset(storage, dataset_ref)
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT game_id FROM predictions WHERE run_id = %s", (prediction_run_id,)
        )
        game_ids = {int(row[0]) for row in cur.fetchall()}
    observed = outcomes.loc[
        outcomes["season"].eq(spec.season) & outcomes["game_id"].isin(game_ids)
    ]
    if (
        not game_ids
        or set(observed["game_id"].astype(int)) != game_ids
        or observed["game_id"].duplicated().any()
        or not observed["completed"].fillna(False).all()
        or observed[["home_points", "away_points"]].isna().any().any()
    ):
        raise V5CycleError("certified finals do not cover the selected run")


def apply_component(
    spec: CycleSpec, component: str, evidence_path: Path, conn_url: str
) -> OperationContext:
    _clean_committed()
    item = spec.component(component)
    bound = _bound_inputs(spec, component, item)
    evidence = json.loads(evidence_path.read_text())
    if (
        evidence.get("binding_sha256") != digest(_json_bytes(bound))
        or evidence.get("binding") != bound
        or evidence.get("result_sha256")
        != digest(_json_bytes(evidence.get("result") or {}))
    ):
        raise V5CycleError("preflight evidence is for another component identity")
    if component == "readiness" and (
        evidence.get("result", {}).get("readiness_overall") == "blocked"
        or evidence.get("result", {}).get("overall_verdict") == "blocked"
    ):
        raise V5CycleError("blocked readiness cannot advance the cycle")
    index = ORDER.index(component)
    if index:
        prior = ORDER[index - 1]
        if prior not in spec.components:
            raise V5CycleError(f"cycle lacks prerequisite component: {prior}")
        with PostgresStateStore(conn_url) as prerequisite_store:
            receipt = prerequisite_store.successful_steps(spec.pipeline_id(prior))
            if prior not in receipt:
                raise V5CycleError(f"prior component has no verified receipt: {prior}")
    context = OperationContext(
        command=f"v5-cycle-{component}",
        environment=spec.environment,
        season=spec.season,
        week=spec.week,
        as_of=str(item["as_of"]),
        pipeline_run_id=spec.pipeline_id(component),
    )

    if component in {"freeze", "close"}:
        _preflight_ops(spec, component, item)
        argv = [
            sys.executable,
            "-m",
            "cks_picks_cfb.ops",
            "freeze-week" if component == "freeze" else "close-week",
            "--year",
            str(spec.season),
            "--week",
            str(spec.week),
            "--environment",
            spec.environment,
            "--pipeline-run-id",
            spec.pipeline_id(component),
        ]
        if component == "close":
            argv += [
                "--as-of",
                str(item["as_of"]),
                "--outcomes-ref-uri",
                str(item["outcomes_ref_uri"]),
            ]
        subprocess.run(argv, check=True, env=_runner_env(spec))
        return context

    def action(active: OperationContext) -> list[dict[str, Any]]:
        if component == "publish":
            import os

            from cks_picks_cfb.artifacts import (
                prediction_run_manifest_path,
                read_json_artifact,
                read_verified_csv_artifact,
            )
            from scripts.pipeline.publish_to_db import (
                _load_provenance,
                load_market_quotes,
                prepare_predictions,
                publish_week,
                request_site_revalidation,
            )

            storage = get_storage(environment=spec.environment)
            manifest = read_json_artifact(
                prediction_run_manifest_path(spec.season, spec.week, item["run_id"]),
                storage,
            )
            cfg, system_name, model_id, threshold = _load_provenance(
                Path(str(item["config"]))
            )
            previous = {
                key: os.environ.get(key)
                for key in (
                    "CFB_ARTIFACT_ENV",
                    "CFB_PIPELINE_RUN_ID",
                    "CFB_PIPELINE_LEASE_EPOCH",
                )
            }
            os.environ["CFB_ARTIFACT_ENV"] = spec.environment
            os.environ["CFB_PIPELINE_RUN_ID"] = active.pipeline_run_id
            os.environ["CFB_PIPELINE_LEASE_EPOCH"] = str(active.lease_epoch)
            try:
                count = publish_week(
                    prepare_predictions(read_verified_csv_artifact(manifest, storage)),
                    conn_url,
                    season=spec.season,
                    week=spec.week,
                    high_conf_threshold=threshold,
                    source_config=cfg,
                    system_name=system_name,
                    model_id=model_id,
                    update_current=True,
                    run_manifest=manifest,
                    market_quotes=load_market_quotes(manifest),
                )
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
            try:
                request_site_revalidation()
            except requests.RequestException:
                # The existing five-minute ISR remains the serving fallback.
                pass
            return [
                {
                    "binding_sha256": digest(_json_bytes(bound)),
                    "output": {"run_id": item["run_id"], "published_games": count},
                }
            ]
        argv = _command(spec, component, item, apply=True, evidence=evidence_path)
        # Research runners consume their own bare dry-run JSON, not the cycle envelope.
        with tempfile.TemporaryDirectory(prefix="v5-cycle-") as tmp:
            raw_evidence = Path(tmp) / "runner-preflight.json"
            raw_evidence.write_text(json.dumps(evidence["result"], sort_keys=True))
            if component in EVIDENCE_ARGUMENT:
                argv[-1] = str(raw_evidence)
            result = subprocess.run(
                argv,
                check=True,
                capture_output=True,
                text=True,
                env=_runner_env(spec),
            )
        output = _read_json_output(result.stdout)
        if component == "readiness" and output.get("overall_verdict") == "blocked":
            raise V5CycleError("blocked readiness cannot advance the cycle")
        verification = _verified_result(spec, component, item, output)
        return [
            {
                "binding_sha256": digest(_json_bytes(bound)),
                "output": output,
                "verification": verification,
            }
        ]

    def resume_validator(_: OperationContext, outputs: Any) -> bool:
        if not outputs or outputs[0].get("binding_sha256") != digest(
            _json_bytes(bound)
        ):
            raise V5CycleError("stored receipt differs from requested component")
        verification = outputs[0].get("verification") or {}
        if component == "publish":
            return True
        manifest_uri = verification.get("manifest_uri")
        if manifest_uri:
            storage = get_storage(environment="preview")
            if digest(storage.read_bytes(manifest_uri)) != verification.get(
                "manifest_sha256"
            ):
                raise V5CycleError("stored component manifest checksum changed")
        return True

    step = PipelineStep(
        component, action, definition=bound, resume_validator=resume_validator
    )
    with PostgresStateStore(conn_url) as store:
        return StateMachine(store).run(context, [step])
