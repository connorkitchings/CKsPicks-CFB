#!/usr/bin/env python3
"""Build the weekly season revision manifest from registered Preview captures.

For ``--week N`` (the week to forecast) the completed history is Weeks 0..N-1:

1. Refresh Silver ``games``, ``game_outcomes``, ``plays`` and ``team_game_stats``
   through the ops controller's ``prepare-week`` source and Silver steps (the
   ``fetch-source``/``build-silver`` machinery) under ``--pipeline-run-id``.
2. Derive ``byplay``, ``drives`` and ``source_reconciliation`` from those parents.
3. Build one content-addressed cumulative ``market_quotes`` version from every
   registered season CFBD betting-lines and The Odds API capture.
4. Write ``conf/season/<season>/revision_manifest_w<N>_v1.json``. ``observations``
   and ``scoring_events`` are omitted: ``season.inputs`` recomputes them.

``--dry-run`` fetches nothing: it reads the existing Silver refs of
``--pipeline-run-id``, builds the derived and market versions in a temporary
directory, validates and prints the manifest, and uploads, registers and
writes nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import register_dataset_version
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    read_dataset,
)
from cks_picks_cfb.data.reconciliation import (
    exclude_games_after_cutoff,
    reconcile_completed_games,
    stream_points_by_team_game,
)
from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.silver import SILVER_CONTRACTS, build_silver_version
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.data.storage.local import LocalStorage
from cks_picks_cfb.features.pipeline import build_preaggregation_pipeline
from cks_picks_cfb.season.manifest import validate_revision
from scripts.pipeline.build_week_market_snapshot import (
    capture_records,
    market_captures,
)

#: Controller refs written by ``prepare-week`` under ``pipeline-runs/<run_id>/``.
CONTROLLER_REFS = {
    "games": "games_ref.json",
    "game_outcomes": "game_outcomes_ref.json",
    "plays": "plays_ref.json",
    "team_game_stats": "team_game_stats_ref.json",
}
LAST_CONTROLLER_STEP = "build_team_game_stats"
DERIVED_PARENTS = ("plays", "games", "teams", "team_game_stats")
#: Same configuration identity as the 2026 Silver derivation that built Week 7.
DERIVED_CONFIG = {
    "corrections_dataset": None,
    "nullable_ppa": True,
    "pipeline": "team_game_pipeline_v1",
    "scope": "season_2026",
    "stream_score_reconciliation": True,
}
#: Revision inputs carried unchanged from the previous week's manifest.
CARRIED_INPUTS = ("venues", "teams")


def _code_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _utc(value: str) -> datetime:
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError(f"timestamp must be timezone-aware: {value}")
    return stamp.astimezone(timezone.utc)


def _iso(stamp: datetime) -> str:
    return stamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _input(ref: DatasetRef) -> dict[str, str]:
    return {"uri": ref.uri, "sha256": ref.content_sha}


def _ref_from_input(dataset: str, entry: dict) -> DatasetRef:
    version = entry["uri"].split("version=", 1)[1].split("/", 1)[0]
    return DatasetRef(
        dataset=dataset,
        version_id=version,
        schema_version=SILVER_CONTRACTS[dataset].schema_version,
        content_sha=entry["sha256"],
        uri=entry["uri"],
    )


def refresh_controller_silver(
    conn_url: str, *, season: int, week: int, as_of: str, run_id: str
) -> None:
    """Fetch Weeks 0..week-1 and rebuild their Silver via the ops controller."""
    from cks_picks_cfb.ops.__main__ import build_steps
    from cks_picks_cfb.ops.state_machine import (
        PostgresStateStore,
        StateMachine,
        WebhookFailureNotifier,
        new_context,
    )

    os.environ["DATABASE_URL"] = conn_url
    os.environ["CFB_ARTIFACT_ENV"] = "preview"
    os.environ["CFB_RUNTIME_TARGET_RESOLVED"] = "preview"
    context = new_context(
        command="prepare-week",
        environment="preview",
        season=season,
        week=week,
        as_of=as_of,
        pipeline_run_id=run_id,
    )
    steps = build_steps(context, conn_url=conn_url)
    steps = steps[: [step.name for step in steps].index(LAST_CONTROLLER_STEP) + 1]
    with PostgresStateStore(conn_url) as store:
        StateMachine(store, notifier=WebhookFailureNotifier.from_env()).run(
            context, steps
        )


def controller_refs(storage, run_id: str) -> dict[str, DatasetRef]:
    prefix = f"artifacts/preview/pipeline-runs/{run_id}"
    refs = {}
    for dataset, name in CONTROLLER_REFS.items():
        uri = f"{prefix}/{name}"
        if not storage.exists(uri):
            raise FileNotFoundError(
                f"Controller run {run_id} has no {dataset} ref at {uri}"
            )
        refs[dataset] = DatasetRef(**json.loads(storage.read_bytes(uri)))
    return refs


def source_capture_ids(storage, refs: list[DatasetRef]) -> list[str]:
    """Bronze captures behind Silver versions, from their sealed manifests."""
    ids: list[str] = []
    for ref in refs:
        manifest_uri = ref.uri.rsplit("/", 1)[0] + "/manifest.json"
        ids.extend(json.loads(storage.read_bytes(manifest_uri))["source_capture_ids"])
    return ids


def latest_capture_time(conn_url: str, capture_ids: list[str]) -> datetime:
    with psycopg.connect(conn_url) as conn:
        (latest,) = conn.execute(
            "SELECT max(captured_at) FROM catalog.source_captures "
            "WHERE capture_id = ANY(%s)",
            (list(capture_ids),),
        ).fetchone()
    if latest is None:
        raise LookupError("No registered capture behind the revision inputs")
    return latest


def season_market_capture_ids(
    conn_url: str, season: int, cutoff: datetime
) -> list[str]:
    """Every registered season CFBD betting-lines and Odds API capture by ``cutoff``.

    CFBD captures carry their season in the request; Odds API captures carry only
    their capture time, so they belong to the calendar year of the season.
    """
    with psycopg.connect(conn_url) as conn:
        rows = conn.execute(
            "SELECT capture_id FROM catalog.source_captures "
            "WHERE state = 'registered' AND captured_at <= %s AND ("
            "(provider = 'cfbd' AND entity = 'betting_lines' "
            "AND request->'parameters'->>'year' = %s) "
            "OR (provider = 'the_odds_api' AND entity = 'market_quotes' "
            "AND EXTRACT(YEAR FROM captured_at AT TIME ZONE 'UTC') = %s)) "
            "ORDER BY captured_at, capture_id",
            (cutoff, str(season), season),
        ).fetchall()
    return [str(row[0]) for row in rows]


def build_market_quotes(source, sink, *, captures, games: pd.DataFrame, code_sha: str):
    """One content-addressed cumulative quotes version over every given capture.

    Its as-of is the latest capture time, so an unchanged capture set rebuilds
    the identical version.
    """
    if not captures:
        raise LookupError("No registered market captures for the season")
    return build_silver_version(
        sink,
        dataset="market_quotes",
        records=capture_records(source, captures),
        source_captures=captures,
        as_of=max(capture.captured_at for capture in captures),
        code_sha=code_sha,
        config_sha=hashlib.sha256(
            b"season-market-quotes:all_registered_captures_v1"
        ).hexdigest(),
        context={"games": games},
    )


def build_derived(
    source, sink, *, parents: dict[str, DatasetRef], as_of: datetime, code_sha: str
):
    """Derive byplay, drives and source reconciliation from pinned Silver parents."""
    frames = {name: read_dataset(source, parents[name]) for name in DERIVED_PARENTS}
    games = frames["games"].rename(columns={"kickoff_utc": "start_date"})
    byplay, drives, team_game, _ = build_preaggregation_pipeline(
        frames["plays"],
        games_df=games,
        teams_df=frames["teams"],
        nullable_ppa=DERIVED_CONFIG["nullable_ppa"],
    )
    # Completed games not yet available at the cutoff are outside this dataset.
    reconcile_games, _ = exclude_games_after_cutoff(games, as_of)
    reconciliation = reconcile_completed_games(
        reconcile_games,
        team_game.merge(
            stream_points_by_team_game(byplay), on=["game_id", "team"], how="left"
        ),
        frames["team_game_stats"],
        declared_incomplete_game_ids=None,
    )
    config_sha = hashlib.sha256(
        json.dumps(DERIVED_CONFIG, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    built = {}
    for dataset, frame in (
        ("byplay", byplay),
        ("drives", drives),
        ("source_reconciliation", reconciliation),
    ):
        schema_version = SILVER_CONTRACTS[dataset].schema_version
        validate_frame(frame, schema_for(dataset, schema_version))
        built[dataset] = build_dataset_version(
            sink,
            build=BuildRequest(
                dataset=dataset,
                parent_refs=tuple(parents[name] for name in DERIVED_PARENTS),
                code_sha=code_sha,
                config_sha=config_sha,
                as_of=as_of,
                schema_version=schema_version,
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
    return built


def revision_manifest(
    previous: dict,
    *,
    week: int,
    as_of: datetime,
    pre_week_cutoff: datetime,
    captured_at: datetime,
    refs: dict[str, DatasetRef],
) -> dict:
    """The Week ``week`` revision: fresh Silver inputs, carried venues and teams."""
    manifest = {
        "schema_version": "season_revision_v1",
        "season": previous["season"],
        "revision_id": f"season-{previous['season']}-w{week}-preview-r1",
        "captured_at": _iso(captured_at),
        "pre_week_cutoffs": {
            **previous["pre_week_cutoffs"],
            str(week): _iso(pre_week_cutoff),
        },
        "post_week_cutoffs": {
            **previous.get("post_week_cutoffs", {}),
            str(week - 1): _iso(as_of),
        },
        "inputs": {
            "schedule": _input(refs["games"]),
            "finals": _input(refs["game_outcomes"]),
            "byplay": _input(refs["byplay"]),
            "drives": _input(refs["drives"]),
            "reconciliation": _input(refs["source_reconciliation"]),
            "market_quotes": _input(refs["market_quotes"]),
            "venue_games": _input(refs["games"]),
            **{name: previous["inputs"][name] for name in CARRIED_INPUTS},
        },
    }
    if "score_reconciliation_exceptions" in previous:
        manifest["score_reconciliation_exceptions"] = previous[
            "score_reconciliation_exceptions"
        ]
    validate_revision(manifest)
    return manifest


def build_revision(
    *,
    conn_url: str,
    source,
    sink,
    previous: dict,
    week: int,
    as_of: datetime,
    pre_week_cutoff: datetime,
    run_id: str,
    now: datetime,
    code_sha: str,
) -> tuple[dict, list[tuple[DatasetRef, object]]]:
    """Compute every input into ``sink``; returns the manifest and new versions."""
    season = previous["season"]
    refs = controller_refs(source, run_id)
    refs["teams"] = _ref_from_input("teams", previous["inputs"]["teams"])
    derived = build_derived(source, sink, parents=refs, as_of=as_of, code_sha=code_sha)
    captures = market_captures(
        conn_url, season_market_capture_ids(conn_url, season, now)
    )
    quotes = build_market_quotes(
        source,
        sink,
        captures=captures,
        games=read_dataset(source, refs["games"]),
        code_sha=code_sha,
    )
    built = {**derived, "market_quotes": quotes}
    refs.update({name: ref for name, (ref, _) in built.items()})
    capture_ids = source_capture_ids(
        source, [refs[name] for name in CONTROLLER_REFS]
    ) + [capture.capture_id for capture in captures]
    manifest = revision_manifest(
        previous,
        week=week,
        as_of=as_of,
        pre_week_cutoff=pre_week_cutoff,
        captured_at=latest_capture_time(conn_url, capture_ids),
        refs=refs,
    )
    return manifest, list(built.values())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--season", type=int, choices=(2026,), required=True)
    parser.add_argument(
        "--week", type=int, required=True, help="Week to forecast (N >= 1)."
    )
    parser.add_argument("--environment", choices=("preview",), required=True)
    parser.add_argument(
        "--as-of",
        required=True,
        help="Silver as-of and post-week cutoff of the completed week N-1.",
    )
    parser.add_argument(
        "--pre-week-cutoff", required=True, help="Pre-week cutoff of week N."
    )
    parser.add_argument(
        "--pipeline-run-id",
        required=True,
        help="Ops controller run that captures and builds the completed-week Silver.",
    )
    parser.add_argument(
        "--previous-manifest",
        help="Defaults to conf/season/<season>/revision_manifest_w<N-1>_v1.json.",
    )
    parser.add_argument(
        "--output",
        help="Defaults to conf/season/<season>/revision_manifest_w<N>_v1.json.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.week < 1:
        parser.error("--week must be at least 1")
    return args


def main() -> None:
    load_dotenv()
    args = parse_args()
    conf = Path(f"conf/season/{args.season}")
    previous_path = Path(
        args.previous_manifest or conf / f"revision_manifest_w{args.week - 1}_v1.json"
    )
    output = Path(args.output or conf / f"revision_manifest_w{args.week}_v1.json")
    if not args.dry_run and output.exists():
        raise SystemExit(f"Refusing to overwrite {output}")
    previous = json.loads(previous_path.read_text())
    if previous.get("season") != args.season:
        raise SystemExit(f"{previous_path} is not a {args.season} revision")
    as_of, pre_week_cutoff = _utc(args.as_of), _utc(args.pre_week_cutoff)
    conn_url = resolve_runtime_target(args.environment).database_url
    source = get_storage(environment=args.environment)
    if not args.dry_run:
        refresh_controller_silver(
            conn_url,
            season=args.season,
            week=args.week,
            as_of=_iso(as_of),
            run_id=args.pipeline_run_id,
        )
    with tempfile.TemporaryDirectory(prefix="season-revision-") as scratch:
        sink = LocalStorage(scratch) if args.dry_run else source
        manifest, built = build_revision(
            conn_url=conn_url,
            source=source,
            sink=sink,
            previous=previous,
            week=args.week,
            as_of=as_of,
            pre_week_cutoff=pre_week_cutoff,
            run_id=args.pipeline_run_id,
            now=datetime.now(timezone.utc),
            code_sha=_code_sha(),
        )
    payload = json.dumps(manifest, indent=2) + "\n"
    if args.dry_run:
        print(payload, end="")
        return
    for ref, dataset_manifest in built:
        register_dataset_version(conn_url, ref, dataset_manifest)
    output.write_text(payload)
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
