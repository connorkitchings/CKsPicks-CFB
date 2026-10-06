"""Exercise the actual twelve-stage DAG with immutable fixture R2 and Preview DB.

The historical population keeps the library's sealed 8,936/8,935 counts. No
measurement, rating, offset, inference, market, or lake computation is mocked.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.data.data_first_possession_v1 import build_population
from cks_picks_cfb.data.data_first_repair_v2 import reconcile_population
from cks_picks_cfb.forecast.heads import FEATURES
from cks_picks_cfb.forecast.live import DEVELOPMENT_SEASONS
from cks_picks_cfb.forecast.offsets import build_offsets
from cks_picks_cfb.ratings import possession_measurements as pm
from cks_picks_cfb.ratings.possession_intended_update import IntendedUpdate
from cks_picks_cfb.rebuild import (
    common,
    recon_forecast,
    recon_foundation,
    recon_offsets,
    recon_receipt,
    recon_states,
)
from cks_picks_cfb.rebuild.catalog_publish import collect_entries
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.legacy import _profit, spread_result, total_result
from cks_picks_cfb.rebuild.orchestrator import Orchestrator
from cks_picks_cfb.rebuild.plan import RebuildPlan
from cks_picks_cfb.rebuild.recon_common import (
    EXPECTED_COUNTS,
    WEEK_AS_OF,
    json_data,
    original_run_id,
    parquet_data,
)
from cks_picks_cfb.rebuild.stages import get_stages
from cks_picks_cfb.rebuild.targets import GuardedStore, InMemoryStore

REPO = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Remote:
    def __init__(self):
        self.objects = {}
        self.identity = "memory:preview"

    def read_bytes(self, key):
        return self.objects[key]

    def read(self, key):
        return self.read_bytes(key)

    def exists(self, key):
        return key in self.objects


@pytest.fixture(scope="module")
def corpus():
    remote = Remote()

    def put(uri, data):
        remote.objects[uri] = data
        return {"uri": uri, "content_sha": sha(data)}

    def dataset(name, frame, version, season):
        ref = {
            "dataset": name,
            "version_id": version,
            "schema_version": name + "_v1",
            **put(
                f"lake/silver/dataset={name}/version={version}/data.parquet",
                parquet_data(frame),
            ),
        }
        manifest = {
            **ref,
            "tier": "silver",
            "row_count": len(frame),
            "partitions": {"seasons": [season]},
        }
        put(
            f"lake/silver/dataset={name}/version={version}/manifest.json",
            json_data(manifest),
        )
        return ref

    schedule_rows = []
    plays = []
    gid = 1000
    dates = [
        "2026-08-29T12:00:00Z",
        "2026-09-05T12:00:00Z",
        "2026-09-12T12:00:00Z",
        "2026-09-19T12:00:00Z",
        "2026-09-26T12:00:00Z",
        "2026-10-02T12:00:00Z",
    ]
    for w, count in EXPECTED_COUNTS.items():
        for i in range(count):
            gid += 1
            game = 401856811 if w == 3 and i == 0 else gid
            home, away = f"Team{2 * i}", f"Team{2 * i + 1}"
            schedule_rows.append(
                dict(
                    season=2026,
                    week=w,
                    game_id=game,
                    kickoff_utc=pd.Timestamp(dates[w]),
                    home_team=home,
                    away_team=away,
                    home_points=7 if w < 5 else None,
                    away_points=3 if w < 5 else None,
                )
            )
            if w == 5:
                continue
            for drive, offense, defense, a, d in (
                (1, home, away, 7, 0),
                (2, away, home, 3, 7),
            ):
                for n in (1, 2):
                    plays.append(
                        dict(
                            season=2026,
                            week=w,
                            game_id=game,
                            drive_number=drive,
                            play_number=n,
                            offense=offense,
                            defense=defense,
                            st=0,
                            penalty=0,
                            twopoint=0,
                            play_type="Rush" if drive == 1 or n == 1 else "Field Goal",
                            garbage=0,
                            ppa=0.2,
                            quarter=1,
                            offense_score=0 if n == 1 else a,
                            defense_score=d,
                        )
                    )
    schedule = pd.DataFrame(schedule_rows)
    outcomes = schedule[["season", "game_id", "home_points", "away_points"]].copy()
    outcomes["completed"] = outcomes.home_points.notna()
    rec = schedule[["season", "game_id"]].assign(classification="exact")
    completed = schedule[schedule.week.lt(5)].assign(completed=True)
    pop, _ = reconcile_population(
        schedule=completed,
        outcomes=outcomes,
        observed_games=completed[["season", "game_id"]],
        reconciliation=rec,
        omissions={},
        scope="season_2026",
    )
    population = build_population(
        pop, scope="season_2026", expected_rows=215, expected_eligible=215
    )
    result = pm.build_measurements(
        byplay=pd.DataFrame(plays),
        population=population,
        outcomes=outcomes,
        scope="season_2026",
    )
    dataset("byplay", pd.DataFrame(plays), "byplay", 2026)
    dataset("source_reconciliation", rec, "rec", 2026)
    outcomes_ref = dataset("game_outcomes", outcomes, "outcomes", 2026)
    final_outcomes = outcomes.assign(home_points=7, away_points=3, completed=True)
    final_ref = dataset("game_outcomes", final_outcomes, "finals", 2026)
    teams = sorted(set(schedule.home_team) | set(schedule.away_team))
    priors = pd.DataFrame(
        [
            dict(
                season=2026,
                team=t,
                unit_role=r,
                prior_mean=0.1 * (i % 5),
                prior_variance=1.0,
            )
            for i, t in enumerate(teams)
            for r in ("offense", "defense")
        ]
    )
    terminal = pd.DataFrame(
        [
            dict(
                season=2025,
                team=t,
                measurement_id="ppp",
                unit_role=r,
                adjusted_value=1.0 + i * 0.01,
                primary_exposure=8.0,
            )
            for i, t in enumerate(teams)
            for r in ("offense", "defense")
        ]
    )
    engine = IntendedUpdate(
        schedule=schedule,
        observations=result.observations,
        priors=priors,
        historical_terminal=terminal,
    )
    pregame = engine.pregame().team_states
    # Full sealed historical population; tied kickoffs keep fixture evidence simple.
    hist = []
    for i in range(8936):
        season = DEVELOPMENT_SEASONS[i % len(DEVELOPMENT_SEASONS)]
        eligible = i < 8935
        hist.append(
            dict(
                season=season,
                week=1,
                game_id=500000 + i,
                kickoff_utc=pd.Timestamp(f"{season}-09-01T12:00:00Z"),
                home_team="Team0",
                away_team="Team1",
                schedule_completed=eligible,
                outcome_valid=eligible,
                forecast_eligible=eligible,
                measurement_usable=eligible,
                missing_reason=None if eligible else "incomplete",
                disposition="eligible_with_measurements"
                if eligible
                else "unscorable_incomplete_or_invalid_outcome",
                timing_class="historically_reconstructed",
            )
        )
    hist_raw = pd.DataFrame(hist)
    hist_pop = build_population(hist_raw, scope="historical")
    events = pd.DataFrame(
        [
            dict(
                season=int(row.season),
                game_id=int(row.game_id),
                team="Team0",
                period_class="regulation",
                scoring_category="regulation_non_offense",
                score_increment=3.0,
                admission="baseline_unchanged",
            )
            for row in hist_pop.drop_duplicates("season").itertuples()
        ]
    )
    offsets = build_offsets(
        hist_pop, events, development_seasons=DEVELOPMENT_SEASONS
    ).offsets
    bundle = dict(
        schema_version="v5_inference_bundle_v1",
        feature_order=list(FEATURES),
        development_seasons=list(DEVELOPMENT_SEASONS),
        targets={
            target: dict(
                feature_names=["home_offense"],
                coefficients=[1.0],
                center={"home_offense": 0.0},
                scale={"home_offense": 1.0},
                intercept=4.0 if target == "margin" else 10.0,
                calibration_variance=4.0,
                head="reference",
                alpha=10.0,
            )
            for target in ("margin", "total")
        },
    )
    root_prefix = "rebuild/6a/fixture/"
    for rel, frame in (
        ("states_2026/observations.parquet", result.observations),
        ("states_2026/priors.parquet", priors),
        ("states_2026/pregame_teams.parquet", pregame),
        ("ratings/terminal.parquet", terminal),
        ("forecast/offsets.parquet", offsets),
        ("comparison/admitted_events.parquet", events),
        ("eligibility/population_raw.parquet", hist_raw),
    ):
        put(root_prefix + rel, parquet_data(frame))
    put(root_prefix + "forecast/bundle.json", json_data(bundle))
    root = signed_payload(
        dict(
            kind="rebuild_root_v1",
            run_id="fixture",
            objects={k: sha(v) for k, v in remote.objects.items()},
        )
    )
    put(root_prefix + "root-manifest.json", json_data(root))
    receipt = signed_payload(
        dict(
            inputs_for_6b=dict(
                artifacts={
                    k: v
                    for k, v in root["objects"].items()
                    if k.startswith(root_prefix)
                },
                cutoff_2026="2026-09-30T12:34:06Z",
                selected_design="ppp__rho_0_60__exposure",
            )
        )
    )
    task_prefix = "rebuild/6a/task4/"
    put(task_prefix + "receipt/receipt.json", json_data(receipt))
    taskroot = signed_payload(
        dict(
            kind="rebuild_root_v1",
            run_id="task4",
            objects={task_prefix + "receipt/receipt.json": sha(json_data(receipt))},
        )
    )
    put(task_prefix + "root-manifest.json", json_data(taskroot))
    columns = [
        "week",
        "game_id",
        "start_date",
        "home_team",
        "away_team",
        "home_points",
        "away_points",
    ]
    rows = [
        [
            r.week,
            r.game_id,
            str(r.kickoff_utc),
            r.home_team,
            r.away_team,
            None if pd.isna(r.home_points) else r.home_points,
            None if pd.isna(r.away_points) else r.away_points,
        ]
        for r in schedule.itertuples()
    ]
    lock = dict(
        games=dict(columns=columns, rows=rows),
        research_2026_prediction_keys=dict(completed_games=215),
        market_sources={str(w): dict(as_of=WEEK_AS_OF[w]) for w in range(5)},
    )
    refs = dict(
        schema_version="reconstruction_source_refs_v1",
        weeks={},
        week5_outcomes=final_ref,
    )
    # Original CSVs have known lines/grades; fixture Preview returns these exact keys.
    db_grades = []
    for w in range(6):
        snaps = []
        quotes = []
        csv = []
        for r in schedule[schedule.week.eq(w)].itertuples():
            gap = int(r.game_id) == 401856811
            snap = f"snap-{r.game_id}"
            snaps.append(
                dict(
                    market_snapshot_id=snap,
                    season=2026,
                    week=w,
                    game_id=r.game_id,
                    spread_line=-3.0,
                    total_line=None if gap else 10.0,
                    market_captured_at=WEEK_AS_OF[w],
                    market_policy_version="model_side_best_quote_v2",
                )
            )
            row = {
                "market_snapshot_id": snap,
                "game_id": r.game_id,
                "Spread Prediction": 4.0,
                "Total Prediction": 10.0,
                "Spread Bet": "Home",
                "Total Bet": None if gap else "Under",
                "home_team_spread_line": -3.0,
                "total_line": None if gap else 10.0,
            }
            for target, point, side in (
                ("spread", -3.0, "home"),
                ("total", 10.0, "under"),
            ):
                if target == "total" and gap:
                    continue
                quote = f"quote-{r.game_id}-{target}"
                quotes.append(
                    dict(
                        snapshot_id=snap,
                        quote_id=quote,
                        game_id=r.game_id,
                        spread=point if target == "spread" else None,
                        total=point if target == "total" else None,
                        home_spread_price=-110.0,
                        away_spread_price=-110.0,
                        over_price=-110.0,
                        under_price=-110.0,
                        captured_at=WEEK_AS_OF[w],
                        provider="Fixture",
                    )
                )
                row[f"{target}_market_snapshot_id"] = snap
                row[f"{target}_market_quote_id"] = quote
                row[f"{target}_market_quote_price"] = -110.0
                res = (spread_result if target == "spread" else total_result)(
                    7.0, 3.0, point, side
                )
                row[f"{target.title()} Bet Result"] = res.title()
                db_grades.append(
                    (
                        original_run_id(w),
                        r.game_id,
                        target,
                        side,
                        point,
                        -110.0,
                        res,
                        round(_profit(res, -110.0), 4),
                        snap,
                        quote,
                        snap,
                        quote,
                        side,
                    )
                )
            if gap:
                for suffix in ("snapshot_id", "quote_id", "quote_price"):
                    row[f"total_market_{suffix}"] = None
                row["Total Bet Result"] = None
            csv.append(row)
        snapref = dataset("market_snapshots", pd.DataFrame(snaps), f"snap{w}", 2026)
        quoteref = dataset("market_quotes", pd.DataFrame(quotes), f"quote{w}", 2026)
        frame = pd.DataFrame(csv)
        preduri = f"artifacts/preview/predictions/week={w}/predictions.csv"
        scoreuri = f"artifacts/preview/scored/week={w}/scored.csv"
        raw = frame.to_csv(index=False).encode()
        put(preduri, raw)
        put(scoreuri, raw)
        m = dict(
            run_id=original_run_id(w),
            season=2026,
            week=w,
            data_as_of=WEEK_AS_OF[w],
            input_dataset_refs=[snapref, quoteref],
            artifact_uri=preduri,
            artifact_sha256=sha(raw),
        )
        sm = dict(
            run_id=original_run_id(w),
            season=2026,
            week=w,
            artifact_uri=scoreuri,
            artifact_sha256=sha(raw),
        )
        put(f"original_predictions_w{w}", json_data(m))
        put(f"original_scored_w{w}", json_data(sm))
        refs["weeks"][str(w)] = dict(
            as_of=WEEK_AS_OF[w],
            market_sources={"market_snapshots": snapref, "market_quotes": quoteref},
            source_manifest={
                "uri": f"original_predictions_w{w}",
                "sha256": sha(json_data(m)),
            },
        )
    values = dict(
        root_manifest_6a=json_data(root),
        root_manifest_task4=json_data(taskroot),
        task4_receipt=json_data(receipt),
        source_lock_2026=json_data(lock),
        bets_config=(
            REPO / "conf/weekly_bets/v5_intended_update_2026.yaml"
        ).read_bytes(),
        silver_2026_parents=json_data(dict(game_outcomes=outcomes_ref)),
        reconstruction_source_refs=json_data(refs),
    )
    values.update(
        {
            f"original_{kind}_w{w}": remote.objects[f"original_{kind}_w{w}"]
            for w in range(6)
            for kind in ("predictions", "scored")
        }
    )
    planvalue = yaml.safe_load((REPO / "conf/rebuild/6b_v1.yaml").read_text())
    planvalue["storage_identity"] = remote.identity
    planvalue["inputs"] = [
        dict(name=k, kind="r2_object", uri=k, sha256=sha(v)) for k, v in values.items()
    ]
    remote.objects.update(values)
    return SimpleNamespace(
        remote=remote,
        plan=RebuildPlan.from_dict(planvalue),
        schedule=schedule,
        receipt=receipt,
        db_grades=db_grades,
    )


def make_harness(corpus, monkeypatch):
    remote = copy.deepcopy(corpus.remote)
    monkeypatch.setattr(common, "preview_storage", lambda context: remote)
    monkeypatch.setattr(
        recon_foundation, "EXPECTED_6A_RECEIPT_SHA", corpus.receipt["manifest_sha256"]
    )
    monkeypatch.setattr(
        recon_receipt, "EXPECTED_6A_RECEIPT_SHA", corpus.receipt["manifest_sha256"]
    )
    monkeypatch.setenv("PREVIEW_DATABASE_URL", "fixture://preview")

    db = SimpleNamespace(
        grades=list(corpus.db_grades),
        finals=[(int(r.game_id), 7, 3) for r in corpus.schedule.itertuples()],
    )

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def execute(self, query, params=None):
            assert not query.lstrip().lower().startswith(("insert", "update", "delete"))
            if "session_user" in query:
                self.rows = [
                    ("cks_preview_pipeline", "cks_preview_pipeline", "preview")
                ]
            elif "FROM game_results" in query:
                self.rows = list(db.finals)
            elif "JOIN prediction_grades" in query:
                self.rows = list(db.grades)
            else:
                raise AssertionError(query)

        def fetchone(self):
            return self.rows[0]

        def fetchall(self):
            return self.rows

    class Conn:
        read_only = False

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def cursor(self):
            assert self.read_only
            return Cursor()

    import psycopg

    monkeypatch.setattr(psycopg, "connect", lambda url: Conn())
    staging = InMemoryStore()

    def fresh():
        return Orchestrator(
            corpus.plan,
            get_stages(corpus.plan),
            staging=staging,
            code_sha="a" * 40,
            repo_root=REPO,
            read_remote=remote.read,
        )

    runner = fresh()
    runner.preflight(
        repo_root=REPO,
        config_sha="b" * 64,
        worktree_clean=True,
        guard=GuardedStore(
            InMemoryStore(remote.identity),
            run_id=corpus.plan.run_id,
            expected_identity=remote.identity,
            run_namespace="rebuild/6b/",
        ),
        read_remote=remote.read,
    )
    return SimpleNamespace(
        runner=runner, fresh=fresh, staging=staging, remote=remote, corpus=corpus, db=db
    )


@pytest.fixture(scope="module")
def persisted(corpus):
    patch = pytest.MonkeyPatch()
    h = make_harness(corpus, patch)
    try:
        for stage in corpus.plan.stages:
            h.runner.build([stage.name])
        yield copy.deepcopy(h.staging.objects)
    finally:
        patch.undo()


@pytest.fixture
def harness(corpus, monkeypatch, persisted):
    h = make_harness(corpus, monkeypatch)
    h.staging.objects = copy.deepcopy(persisted)
    return h


def test_actual_twelve_stage_build_and_fresh_persisted_verify(harness):
    h = harness
    for stage in h.corpus.plan.stages:
        h.runner.build([stage.name])
        verdict = h.runner.verify([stage.name])
        assert verdict["passed"], verdict["stages"]
    verdict = h.fresh().verify()
    assert verdict["passed"], verdict["stages"]
    before = copy.deepcopy(h.staging.objects)
    h.fresh().build()
    assert h.staging.objects == before
    artifacts = {}
    for stage in h.corpus.plan.stages:
        m = h.runner._load_manifest(stage.name)
        artifacts.update(m["artifacts"])

    def read(key):
        stage = next(
            s.name
            for s in h.corpus.plan.stages
            if key in h.runner._load_manifest(s.name)["artifacts"]
        )
        return h.staging.read(h.runner._artifact_key(stage, key))

    entries = collect_entries(artifacts, read)
    assert len(entries) == 5
    assert all(e.dataset.startswith("reconstruction_") and e.parents for e in entries)


def context(h, name):
    return h.runner._context(
        h.runner.stages[name], h.runner._preflight()["resolved_inputs"]
    )


def alter_artifact(h, stage, key, mutate):
    storage_key = h.runner._artifact_key(stage, key)
    raw = h.staging.objects[storage_key]
    h.staging.objects[storage_key] = mutate(raw)


@pytest.mark.parametrize(
    "input_name", ["task4_receipt", "source_lock_2026", "reconstruction_source_refs"]
)
def test_changed_pinned_input_fails(harness, input_name):
    h = harness
    h.remote.objects[input_name] += b" "
    with pytest.raises(GateError, match="changed after preflight"):
        h.runner.stages["foundation"].build(context(h, "foundation"))


@pytest.mark.parametrize(
    "kind", ["market_quotes", "market_snapshots", "week5_outcomes"]
)
def test_changed_unpinned_child_bytes_fail_hash_check(harness, kind):
    h = harness
    refs = json.loads(h.remote.objects["reconstruction_source_refs"])
    ref = (
        refs["week5_outcomes"]
        if kind == "week5_outcomes"
        else refs["weeks"]["5"]["market_sources"][kind]
    )
    h.remote.objects[ref["uri"]] += b"changed"
    name = "finals" if kind == "week5_outcomes" else "markets"
    with pytest.raises(GateError, match="source hash mismatch"):
        h.runner.stages[name].build(context(h, name))


@pytest.mark.parametrize("fault", ["missing", "duplicate", "wrong_score"])
def test_complete_preview_finals_required(harness, fault):
    h = harness
    if fault == "missing":
        h.db.finals.pop()
    elif fault == "duplicate":
        h.db.finals[-1] = h.db.finals[0]
    else:
        h.db.finals[0] = (h.db.finals[0][0], 99, 3)
    with pytest.raises(GateError, match="coverage|differ"):
        h.runner.stages["finals"].build(context(h, "finals"))


@pytest.mark.parametrize(
    "fault", ["missing", "duplicate", "wrong_grade", "wrong_quote", "wrong_profit"]
)
def test_original_grade_population_and_identity_required(harness, fault):
    h = harness
    if fault == "missing":
        h.db.grades.pop()
    elif fault == "duplicate":
        h.db.grades[-1] = h.db.grades[0]
    else:
        row = list(h.db.grades[0])
        index = {"wrong_grade": 6, "wrong_quote": 9, "wrong_profit": 7}[fault]
        row[index] = 9.0 if fault == "wrong_profit" else "tampered"
        h.db.grades[0] = tuple(row)
    with pytest.raises(GateError, match="keys|mismatch"):
        h.runner.stages["old_grade_reproduction"].build(
            context(h, "old_grade_reproduction")
        )


def test_new_grading_requires_both_original_grade_checks(harness):
    h = harness
    key = h.corpus.plan.run_prefix() + "old_grade_reproduction/summary.json"

    def remove(raw):
        value = json.loads(raw)
        value.pop("csv_grades_checked")
        return json_data(value)

    alter_artifact(h, "old_grade_reproduction", key, remove)
    with pytest.raises(GateError, match="complete original grade reproduction"):
        h.runner.stages["retrospective_grades"].build(
            context(h, "retrospective_grades")
        )


def test_late_state_fails_before_predictions(harness):
    h = harness
    key = h.corpus.plan.run_prefix() + "states_at_cutoff/team_states.parquet"

    def late(raw):
        frame = pd.read_parquet(io.BytesIO(raw))
        frame.loc[frame.target_week.eq(0), "cutoff_utc"] = pd.Timestamp(
            "2026-08-24T12:00:00Z"
        )
        return parquet_data(frame)

    alter_artifact(h, "states_at_cutoff", key, late)
    with pytest.raises(GateError, match="state cutoff exceeds"):
        h.runner.stages["predictions"].build(context(h, "predictions"))


def test_late_offset_evidence_fails_before_predictions(harness):
    h = harness
    key = h.corpus.plan.run_prefix() + "foundation/schedule.parquet"

    def late(raw):
        frame = pd.read_parquet(io.BytesIO(raw))
        frame.loc[frame.week.eq(0), "kickoff_utc"] = pd.Timestamp(WEEK_AS_OF[1])
        return parquet_data(frame)

    alter_artifact(h, "foundation", key, late)
    with pytest.raises(GateError, match="offset evidence kicked off"):
        h.runner.stages["predictions"].build(context(h, "predictions"))


def test_incompatible_bridge_bundle_stops_predictions(harness, monkeypatch):
    h = harness
    original_read = recon_forecast.PublishedRun.read

    def incompatible_bundle(run, uri):
        raw = original_read(run, uri)
        if uri == run.run_key("forecast/bundle.json"):
            bundle = json.loads(raw)
            bundle["schema_version"] = "unsupported_bundle_v99"
            return json_data(bundle)
        return raw

    monkeypatch.setattr(recon_forecast.PublishedRun, "read", incompatible_bundle)
    with pytest.raises(GateError, match="bundle schema version"):
        h.runner.stages["predictions"].build(context(h, "predictions"))


def test_state_identity_disagreement_stops_states_stage(harness, monkeypatch):
    h = harness
    original_frame = recon_states.PublishedRun.frame

    def mismatched_pregame(run, relative):
        frame = original_frame(run, relative)
        if relative == "states_2026/pregame_teams.parquet":
            frame = frame.copy()
            frame.loc[frame.index[0], "offense_rating"] += 0.5
        return frame

    monkeypatch.setattr(recon_states.PublishedRun, "frame", mismatched_pregame)
    with pytest.raises(GateError, match="states-at-cutoff gate failed"):
        h.runner.stages["states_at_cutoff"].build(context(h, "states_at_cutoff"))


def test_offset_freeze_disagreement_stops_offsets_stage(harness, monkeypatch):
    h = harness
    original_build_offsets = recon_offsets.build_offsets
    calls = 0

    def mismatched_weekly_offset(*args, **kwargs):
        nonlocal calls
        result = original_build_offsets(*args, **kwargs)
        calls += 1
        if calls == 2:  # global kickoff-order result is call one; week 0 is call two
            target_index = result.offsets.index[
                result.offsets.season.eq(2026) & result.offsets.week.eq(0)
            ][0]
            result.offsets.loc[target_index, "offset_margin"] += 0.5
        return result

    monkeypatch.setattr(recon_offsets, "build_offsets", mismatched_weekly_offset)
    with pytest.raises(GateError, match="offset-freeze gate failed"):
        h.runner.stages["offsets_2026"].build(context(h, "offsets_2026"))


@pytest.mark.parametrize(
    "fault", ["missing_gate", "false_gate", "same_length_nonclaims", "csv_changed"]
)
def test_receipt_tampering_fails(harness, fault):
    h = harness
    key = h.corpus.plan.run_prefix() + "receipt/receipt.json"
    value = json.loads(h.staging.read(h.runner._artifact_key("receipt", key)))
    if fault == "missing_gate":
        value["validation"].pop("offset_freeze_passed")
    elif fault == "false_gate":
        value["validation"]["states_identity_passed"] = False
    elif fault == "same_length_nonclaims":
        value["non_claims"][0] = "altered claim"
    else:
        csv = value["weeks"]["0"]["artifacts"]["predictions_csv"]["uri"]
        alter_artifact(h, "receipt", csv, lambda raw: raw + b"tampered")
    if fault != "csv_changed":
        value.pop("manifest_sha256", None)
        alter_artifact(h, "receipt", key, lambda raw: json_data(signed_payload(value)))
    problems = recon_receipt.verify_receipt(context(h, "receipt"))
    assert problems


def test_undeclared_parent_cannot_be_read(harness):
    h = harness
    with pytest.raises(GateError, match="did not declare parent"):
        context(h, "foundation").read_artifact("markets", "some-key")


def test_gold_rows_equal_stage_rows(harness):
    from cks_picks_cfb.rebuild.recon_common import load_partitioned_gold

    h = harness
    for name, file in (
        ("offsets_2026", "offsets"),
        ("application_frames", "frames"),
        ("predictions", "predictions"),
        ("markets", "selections"),
        ("retrospective_grades", "grades"),
    ):
        c = context(h, name)
        summary = json.loads(
            c.read_artifact(name, f"{h.corpus.plan.run_prefix()}{name}/summary.json")
        )
        lake = load_partitioned_gold(c, name, summary["lake_gold"])
        stage = pd.read_parquet(
            io.BytesIO(
                c.read_artifact(
                    name, f"{h.corpus.plan.run_prefix()}{name}/{file}.parquet"
                )
            )
        )
        keys = ["season", "week", "game_id"] + (["target"] if "target" in stage else [])
        pd.testing.assert_frame_equal(
            lake.sort_values(keys).reset_index(drop=True),
            stage.sort_values(keys).reset_index(drop=True),
            check_dtype=False,
        )
