"""Stage: compare the corrected 2026 statistics with the published Preview tables.

Read-only and Preview-only. The five published tables (the four matchup tables and the
website ``team_season_stats``) are rebuilt from the corrected 2026 frames with the
repository's own builders and compared on values only; provenance columns (manifest
hashes, source versions) must differ and are excluded. Every differing cell is attributed to
a named bucket; a difference outside the expected buckets, or a population difference, is an
unexplained finding.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable, Iterator
from typing import Any

import pandas as pd

from cks_picks_cfb.rebuild import common, parity, published_diff, states_2026
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput
from cks_picks_cfb.rebuild.published import PublishedRun

PREFIX = "rebuild/6a/{run_id}/published_comparison/"
SEASON = 2026
PROVENANCE = {
    "rating_manifest_sha256",
    "measurement_manifest_sha256",
    "source_manifest_sha256",
    "source_versions",
}
SEASON_STATS_COLUMNS = ("value", "n", "games", "rank", "cohort_size")
STATE_FILES = ("observations", "priors", "pregame_roles", "current_roles")


def fetch_table(cur, table: str, columns, jsonb, where: str, params) -> pd.DataFrame:
    select = ", ".join(f"{c}::text" if c in jsonb else c for c in columns)
    cur.execute(f"SELECT {select} FROM {table} WHERE {where}", params)  # noqa: S608
    return pd.DataFrame(cur.fetchall(), columns=list(columns))


def season_stats_frame(
    run: PublishedRun,
    storage,
    pin_file: dict[str, Any],
    fallback_names: set[str],
    weeks: Iterable[int],
) -> tuple[pd.DataFrame, str]:
    """The website table rebuilt from the corrected 2026 Silver, week by week."""
    from cks_picks_cfb.data.lake import read_dataset
    from cks_picks_cfb.data.team_stats import build_team_season_stats

    parents = {p["dataset"]: p for p in pin_file["parents"]}
    games = read_dataset(storage, common.dataset_ref(parents["games"]))
    outcomes = read_dataset(storage, common.dataset_ref(pin_file["game_outcomes"]))
    teams = read_dataset(storage, common.dataset_ref(parents["teams"]))
    byplay = run.dataset_frames("byplay", season_scope="2026")[SEASON]
    drives = run.dataset_frames("drives", season_scope="2026")[SEASON]
    if {"team", "classification"} <= set(teams.columns):
        fbs = set(
            teams.loc[
                teams["classification"].astype(str).str.lower() == "fbs", "team"
            ].astype(str)
        )
        source = "silver.teams.classification"
    else:
        fbs, source = set(fallback_names), "neon.games (fallback)"
    frames = []
    for week in weeks:
        result = build_team_season_stats(
            byplay=byplay,
            drives=drives,
            games=games,
            outcomes=outcomes,
            fbs_teams=fbs,
            season=SEASON,
            as_of_week=week,
        )
        if not result.frame.empty:
            frames.append(result.frame)
    return pd.concat(frames, ignore_index=True), source


def extension_chain(lock: dict[str, Any]) -> list[dict[str, Any]]:
    """The lock's extensions, oldest first (each nests its predecessor)."""
    chain = []
    extension = lock.get("extends")
    while extension:
        chain.append(extension)
        extension = extension.get("previous_extension")
    return chain[::-1]


def _revision(record: dict[str, Any]) -> tuple[int, pd.Timestamp, pd.Timestamp]:
    try:
        game = int(record["game_id"])
        old = pd.Timestamp(record["old_start_date"])
        new = pd.Timestamp(record["new_start_date"])
    except (KeyError, TypeError, ValueError) as error:
        raise GateError(f"malformed kickoff revision {record!r}") from error
    if old.tzinfo is None or new.tzinfo is None or old == new:
        raise GateError(f"kickoff revision of {game} is not an exact UTC change")
    return game, old, new


def lock_scope(lock: dict[str, Any]) -> dict[str, Any]:
    """Every game and kickoff revision the lock's chained extensions added.

    Each extension must continue the one before it (post-week, completed-game count and
    game-rows hash), add exactly as many games as its counts say, and add no game twice;
    the newest must hash to the lock's own game rows. A game revised twice must carry the
    same revision, and every revision must name a locked game at its new kickoff.
    """
    from cks_picks_cfb.rebuild.lock_extension import rows_sha256

    try:
        cutoffs = {
            int(w): pd.Timestamp(c) for w, c in lock["post_week_cutoffs"].items()
        }
        latest = max(cutoffs)
        chain = extension_chain(lock)
        rows = lock["games"]["rows"] if chain else []
        columns = lock["games"]["columns"] if chain else []
    except (KeyError, TypeError, ValueError) as error:
        raise GateError(f"malformed source lock: {error!r}") from error
    if set(cutoffs) != set(range(latest + 1)):
        raise GateError(f"lock post-week cutoffs are not contiguous: {sorted(cutoffs)}")
    starts = {}
    if chain:
        index = {name: i for i, name in enumerate(columns)}
        starts = {
            int(r[index["game_id"]]): pd.Timestamp(r[index["start_date"]]) for r in rows
        }
    base = latest - len(chain)
    added: dict[int, frozenset[int]] = {}
    revisions: dict[int, tuple[pd.Timestamp, pd.Timestamp]] = {}
    previous = {
        "game_rows_sha256": lock.get("game_rows_sha256"),
        "completed_games_after": None,
    }
    for offset, extension in enumerate(chain, start=1):
        try:
            week = int(extension["added_post_week"])
            games = [int(g) for g in extension["newly_final_game_ids"]]
            before = int(extension["completed_games_before"])
            after = int(extension["completed_games_after"])
            cutoff = pd.Timestamp(extension["added_cutoff"])
            links = (extension["base_game_rows_sha256"], extension["game_rows_sha256"])
        except (KeyError, TypeError, ValueError) as error:
            raise GateError(f"malformed lock extension: {error!r}") from error
        if week != base + offset or cutoffs.get(week) != cutoff:
            raise GateError(f"extension post-week {week} does not continue the chain")
        if links[0] != previous["game_rows_sha256"] or previous[
            "completed_games_after"
        ] not in (None, before):
            raise GateError(f"extension post-week {week} does not follow its parent")
        if len(set(games)) != len(games) or len(games) != after - before:
            raise GateError(f"extension post-week {week}: game count is inconsistent")
        if seen := set(games) & set().union(*added.values()):
            raise GateError(f"games added twice: {sorted(seen)}")
        if missing := set(games) - set(starts):
            raise GateError(f"added games missing from the lock: {sorted(missing)}")
        added[week] = frozenset(games)
        for record in extension.get("kickoff_revisions") or []:
            game, old, new = _revision(record)
            if revisions.get(game, (old, new)) != (old, new):
                raise GateError(f"conflicting kickoff revisions of game {game}")
            if starts.get(game) != new:
                raise GateError(f"revised game {game} is not locked at its new kickoff")
            revisions[game] = (old, new)
        previous = {"game_rows_sha256": links[1], "completed_games_after": after}
    if chain and (
        previous["game_rows_sha256"] != rows_sha256(rows)
        or previous["completed_games_after"] != len(rows)
    ):
        raise GateError("the newest extension does not describe the lock's game rows")
    return {
        "base_post_week": base,
        "latest_post_week": latest,
        "added": added,
        "revisions": revisions,
        # The newest extension alone, for callers that compare against the lock it extends.
        "games": added.get(latest, frozenset()),
        "first_as_of_week": latest + 1 if chain else None,
    }


GAME_TABLES = ("team_game_measurements",)
WEEK_TABLES = (
    "team_possession_stats",
    "team_possession_adjusted",
    "team_rating_components",
    "team_season_stats",
)


def table_additions(
    policies: dict[str, Any], scope: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Each table's additions, from the plan's ``published_coverage`` policy.

    The policy names, per compared table, the last post-week its published rows cover.
    Everything the lock chain added after it is that table's addition scope: the added
    games for the game log, the as-of weeks past it (post-week W is as-of week W + 1)
    for the weekly tables. Coverage before the chain's base cannot be enumerated.
    """
    raw = policies.get("published_coverage") or {}
    if set(raw) != {*GAME_TABLES, *WEEK_TABLES}:
        raise GateError(
            f"published_coverage must name exactly {sorted({*GAME_TABLES, *WEEK_TABLES})}"
        )
    additions = {}
    for table, through in raw.items():
        through = int(through)
        if not scope["base_post_week"] <= through <= scope["latest_post_week"]:
            raise GateError(
                f"published_coverage {table}: post-week {through} is outside the lock "
                f"chain ({scope['base_post_week']}..{scope['latest_post_week']})"
            )
        games = frozenset().union(
            *(g for week, g in scope["added"].items() if week > through)
        )
        additions[table] = {
            "through_post_week": through,
            "games": games if table in GAME_TABLES else frozenset(),
            "first_as_of_week": (
                through + 2
                if table in WEEK_TABLES and through < scope["latest_post_week"]
                else None
            ),
        }
    return additions


# Both scopes take a table's additions or ``lock_scope()`` itself (its newest extension).
def game_scope(additions: dict[str, Any]):
    """Rows of games completed after the published rows were written."""
    if not additions["games"]:
        return None
    return lambda frame: frame["game_id"].astype(int).isin(additions["games"])


def week_scope(additions: dict[str, Any]):
    """Rows of as-of weeks that did not exist when the published rows were written."""
    if additions["first_as_of_week"] is None:
        return None
    return (
        lambda frame: frame["as_of_week"].astype(int) >= additions["first_as_of_week"]
    )


def addition_scope(table: str, additions: dict[str, dict[str, Any]]):
    return (game_scope if table in GAME_TABLES else week_scope)(additions[table])


def kickoff_revision(scope: dict[str, Any]):
    """Name a ``cutoff_utc`` difference only when it is a recorded kickoff revision."""

    def override(row: pd.Series, column: str) -> str | None:
        if column != "cutoff_utc" or not scope["revisions"]:
            return None
        game = row.get("game_id_built")
        if pd.isna(game) or int(game) not in scope["revisions"]:
            return None
        old, new = scope["revisions"][int(game)]
        built, published = (
            pd.Timestamp(row["cutoff_utc_built"]),
            pd.Timestamp(row["cutoff_utc_pub"]),
        )
        if built.tzinfo is None or published.tzinfo is None:
            return None
        return "kickoff_revision" if (built, published) == (new, old) else None

    return override


def published_rating_runs(policies: dict[str, Any]) -> dict[int, str]:
    """The plan's ``published_rating_runs`` policy as as-of week -> rating run id.

    Preview publishes each as-of week's components under the rating run that projected
    them, so component and snapshot ids carry that run's id; the plan names every run and
    its weeks, and no week may belong to two runs.
    """
    raw = policies.get("published_rating_runs")
    if not raw:
        raise GateError("plan policy published_rating_runs is missing or empty")
    week_runs: dict[int, str] = {}
    for run_id, weeks in raw.items():
        if not weeks:
            raise GateError(f"published_rating_runs: {run_id} has no weeks")
        for week in weeks:
            if int(week) in week_runs:
                raise GateError(f"published_rating_runs: week {week} names two runs")
            week_runs[int(week)] = str(run_id)
    return week_runs


def check_published_runs(found: Iterable[str], week_runs: dict[int, str]) -> None:
    """Refuse unless the published components name exactly the planned runs."""
    found, planned = set(found), set(week_runs.values())
    if found != planned:
        raise GateError(
            f"published components name runs {sorted(found)}; the plan expects "
            f"{sorted(planned)} (unexpected {sorted(found - planned)}, "
            f"missing {sorted(planned - found)})"
        )


def build_frames(
    artifacts, week_runs: dict[int, str], build
) -> dict[str, pd.DataFrame]:
    """The payload frames, each as-of week's components under the run that published it.

    Only component and snapshot ids carry the run id, so the other tables come from the
    newest run's build. Weeks past the plan (the lock extension's added scope) also take the
    newest run's ids; outside the added scope they would be population findings.
    """
    newest = week_runs[max(week_runs)]
    builds = {
        run_id: build(dataclasses.replace(artifacts, run_id=run_id)).payload.frames
        for run_id in sorted(set(week_runs.values()))
    }
    frames = dict(builds[newest])
    parts = []
    for run_id, built in builds.items():
        components = built["team_rating_components"]
        owner = components["as_of_week"].astype(int).map(week_runs).fillna(newest)
        parts.append(components[owner.eq(run_id)])
    frames["team_rating_components"] = pd.concat(parts, ignore_index=True)
    return frames


def baseline_history_control(
    context,
    run,
    storage,
    pin_file,
    lock,
    states,
    artifacts,
    game_names,
    published,
    mp,
    md,
    scope: dict[str, Any],
    additions: dict[str, dict[str, Any]],
    week_runs: dict[int, str],
) -> dict[str, Any]:
    """2026 states rebuilt from the SERVED terminal: must equal the published components."""
    from cks_picks_cfb.data.lake import read_dataset
    from cks_picks_cfb.ratings.possession_intended_update import IntendedUpdate
    from cks_picks_cfb.ratings.possession_live_replay import _priors
    from contracts.teams import TEAM_LOGO_MAP

    parents = {p["dataset"]: p for p in pin_file["parents"]}
    games = read_dataset(storage, common.dataset_ref(parents["games"]))
    schedule = states_2026.locked_schedule(games, lock)
    served = json.loads(context.read_input("r9_measurement_manifest"))["output_refs"]
    r9_terminal = parity.partitioned_frame(storage, served["terminal"])
    priors, _ = _priors(schedule, r9_terminal)
    engine = IntendedUpdate(
        schedule=schedule,
        observations=states["observations"],
        priors=priors,
        historical_terminal=r9_terminal,
    )
    pregame = engine.pregame()
    current = pd.concat(
        [
            engine.current(post_week=int(week), cutoff_utc=str(cutoff)).rating_states
            for week, cutoff in sorted(
                lock["post_week_cutoffs"].items(), key=lambda i: int(i[0])
            )
        ],
        ignore_index=True,
    )
    control_artifacts = dataclasses.replace(
        artifacts,
        priors=priors,
        pregame_roles=pregame.rating_states,
        current_roles=current,
    )
    built = build_frames(
        control_artifacts,
        week_runs,
        lambda a: mp.build_payload(
            a, season=SEASON, game_names=game_names, alias_map=TEAM_LOGO_MAP
        ),
    )
    columns, keys, jsonb = md.TABLES["team_rating_components"]
    values = [c for c in columns if c not in keys and c not in PROVENANCE]
    report = published_diff.diff_frames(
        built["team_rating_components"],
        published["team_rating_components"],
        keys=keys,
        columns=values,
        metric_of=lambda row: None,
        jsonb=[c for c in jsonb if c in values],
        expected={"kickoff_revision"},
        added_scope=addition_scope("team_rating_components", additions),
        bucket_override=kickoff_revision(scope),
    )
    return {
        "method": "priors and scale from the served r9 terminal; same 2026 observations",
        "team_rating_components": report,
        # Only recorded kickoff revisions may differ; the diff already refuses anything else.
        "matches_published": not report["unexplained"],
    }


def build(context: StageContext) -> StageOutput:
    import psycopg

    from cks_picks_cfb.data import matchup_data as md
    from cks_picks_cfb.data import matchup_publish as mp
    from cks_picks_cfb.data.runtime import resolve_runtime_target
    from cks_picks_cfb.rebuild.targets import assert_preview_database
    from contracts.teams import TEAM_LOGO_MAP

    run = PublishedRun(context)
    storage = run.storage
    pin_file = json.loads(context.read_input("silver_2026_parents"))
    lock = json.loads(context.read_input("source_lock_2026"))
    states = {name: run.frame(f"states_2026/{name}.parquet") for name in STATE_FILES}
    cutoffs = {int(w): pd.Timestamp(c) for w, c in lock["post_week_cutoffs"].items()}
    root_sha = run.root["manifest_sha256"]
    scope = lock_scope(lock)
    additions = table_additions(dict(context.plan.policies), scope)
    week_runs = published_rating_runs(dict(context.plan.policies))

    url = resolve_runtime_target("preview").database_url
    published: dict[str, pd.DataFrame] = {}
    with psycopg.connect(url) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            assert_preview_database(cur)
            game_names = mp.season_game_names(cur, SEASON)
            cur.execute(
                "SELECT DISTINCT split_part(v5_snapshot_id, ':', 1) "
                "FROM team_rating_components WHERE season = %s",
                (SEASON,),
            )
            check_published_runs((row[0] for row in cur.fetchall()), week_runs)
            for table, (columns, _keys, jsonb) in md.TABLES.items():
                published[table] = fetch_table(
                    cur, table, columns, jsonb, "season = %s", (SEASON,)
                )
            published["team_season_stats"] = fetch_table(
                cur,
                "team_season_stats",
                (
                    "season",
                    "as_of_week",
                    "team",
                    "role",
                    "metric",
                    *SEASON_STATS_COLUMNS,
                ),
                (),
                "season = %s",
                (SEASON,),
            )
            cur.execute(
                "SELECT publication_id, payload_sha256, as_of_weeks, row_counts "
                "FROM matchup_data_publications WHERE season = %s",
                (SEASON,),
            )
            publication = [list(map(str, row)) for row in cur.fetchall()]

    artifacts = mp.Artifacts(
        lineage="intended_update",
        run_id=week_runs[max(week_runs)],
        candidate_id=str(states["pregame_roles"]["candidate_id"].iloc[0]),
        rating_manifest={},
        rating_sha256=root_sha,
        rating_uri="",
        measurement_manifest={},
        measurement_sha256=root_sha,
        measurement_uri="",
        observations=states["observations"],
        observations_records_sha="corrected",
        observations_version_id="corrected",
        priors=states["priors"],
        pregame_roles=states["pregame_roles"],
        current_roles=states["current_roles"],
        post_week_cutoffs=cutoffs,
    )
    rebuilt = build_frames(
        artifacts,
        week_runs,
        lambda a: mp.build_payload(
            a, season=SEASON, game_names=game_names, alias_map=TEAM_LOGO_MAP
        ),
    )
    tables = {}
    control = baseline_history_control(
        context,
        run,
        storage,
        pin_file,
        lock,
        states,
        artifacts,
        game_names,
        published,
        mp,
        md,
        scope,
        additions,
        week_runs,
    )
    components_expected = (
        published_diff.EXPECTED_TO_DIFFER
        | {"kickoff_revision"}
        | ({"history_correction"} if control["matches_published"] else set())
    )
    metric_column = {
        "team_game_measurements": "measurement_id",
        "team_possession_stats": "metric",
        "team_possession_adjusted": "measurement_id",
        "team_rating_components": None,
    }
    for table, (columns, keys, jsonb) in md.TABLES.items():
        values = [c for c in columns if c not in keys and c not in PROVENANCE]
        column = metric_column[table]
        components = table == "team_rating_components"
        tables[table] = published_diff.diff_frames(
            rebuilt[table],
            published[table],
            keys=keys,
            columns=values,
            metric_of=(
                (lambda row: "history_correction")
                if components
                else (lambda row, c=column: row[c])
            ),
            jsonb=[c for c in jsonb if c in values],
            expected=components_expected if components else None,
            added_scope=addition_scope(table, additions),
            bucket_override=kickoff_revision(scope) if components else None,
        )
    stats, fbs_source = season_stats_frame(
        run, storage, pin_file, game_names, range(1, scope["latest_post_week"] + 2)
    )
    tables["team_season_stats"] = published_diff.diff_frames(
        stats,
        published["team_season_stats"],
        keys=["as_of_week", "team", "role", "metric"],
        columns=list(SEASON_STATS_COLUMNS),
        metric_of=lambda row: row["metric"],
        added_scope=addition_scope("team_season_stats", additions),
    )
    report = {
        "season": SEASON,
        "database_role": "cks_preview_pipeline (read-only transaction)",
        "published_rating_runs": {str(w): r for w, r in sorted(week_runs.items())},
        "publication": publication,
        "fbs_source": fbs_source,
        "tables": tables,
        "scope": {
            "lock_post_weeks": [scope["base_post_week"], scope["latest_post_week"]],
            "extension_games": {
                str(week): len(games) for week, games in sorted(scope["added"].items())
            },
            "additions": {
                table: {
                    "published_through_post_week": a["through_post_week"],
                    "added_game_ids": sorted(a["games"]),
                    "first_added_as_of_week": a["first_as_of_week"],
                }
                for table, a in sorted(additions.items())
            },
            "kickoff_revisions": {
                str(g): [old.isoformat(), new.isoformat()]
                for g, (old, new) in sorted(scope["revisions"].items())
            },
        },
        "control_baseline_history": control,
        "summary": published_diff.summarize(tables),
        "explanations": {
            "missing_ppa": "nullable PPA no longer fills missing provider values with zero",
            "punt": "returned punts are tagged special teams (documented punt fix)",
            "scoring": "2026 scoring is unchanged, so no difference is expected",
            "added_scope": (
                "rows of games completed, or as-of weeks added, after the published rows "
                "were written (the lock extension); set aside and counted, never compared"
            ),
            "kickoff_revision": (
                "a provider kickoff revision recorded in the lock extension; only a "
                "cutoff_utc difference on a listed game, from the old to the new kickoff"
            ),
            "history_correction": (
                "2026 priors and the rating scale come from the corrected 2025 terminal; "
                "proven by the control below, which reproduces the published components "
                "exactly from the served terminal"
            ),
        },
        "not_compared": "v5_rating_snapshots: covered through team_rating_components.rating_mean",
    }
    prefix = PREFIX.format(run_id=context.plan.run_id)

    def artifacts_out() -> Iterator[tuple[str, bytes]]:
        yield (
            f"{prefix}report.json",
            json.dumps(report, indent=2, sort_keys=True, default=str).encode(),
        )

    return StageOutput(artifacts=artifacts_out(), metrics=report["summary"])


def verify(context: StageContext) -> list[str]:
    stage = context.stage.name
    prefix = PREFIX.format(run_id=context.plan.run_id)
    report = json.loads(context.read_artifact(stage, prefix + "report.json"))
    problems: list[str] = []
    expected = {
        "team_game_measurements",
        "team_possession_stats",
        "team_possession_adjusted",
        "team_rating_components",
        "team_season_stats",
    }
    if set(report["tables"]) != expected:
        problems.append(f"compared tables {sorted(report['tables'])}")
    for name, table in report["tables"].items():
        if table["rows_built"] == 0 or table["rows_published"] == 0:
            problems.append(
                f"{name}: empty side ({table['rows_built']}/{table['rows_published']})"
            )
        if table["unexplained"]:
            problems.append(
                f"{name}: unexplained difference {table['unexplained_buckets']} {table['population']}"
            )
    control = report.get("control_baseline_history", {})
    if not control.get("matches_published"):
        problems.append(
            "the baseline-history control does not reproduce the published components"
        )
    return problems
