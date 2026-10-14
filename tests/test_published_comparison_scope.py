"""What a lock extension adds to the published comparison, and what it must not hide."""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

from cks_picks_cfb.data import matchup_data as md
from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.rebuild import published_comparison as pc
from cks_picks_cfb.rebuild import published_diff as pd_
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.lock_extension import rows_sha256
from cks_picks_cfb.rebuild.plan import RebuildPlan

COLUMNS = ["week", "game_id", "start_date", "home_team", "away_team"]
ROWS_BASE = [
    [1, 1, "2026-09-05T16:00:00Z", "A", "B"],
    [1, 2, "2026-09-05T19:00:00Z", "C", "D"],
]
ROWS_W2 = [
    *ROWS_BASE,
    [2, 10, "2026-09-12T16:00:00Z", "A", "C"],
    [2, 11, "2026-10-03T15:00:00Z", "B", "D"],
]
ROWS_W3 = [*ROWS_W2, [3, 20, "2026-09-19T16:00:00Z", "A", "D"]]
REVISION_11 = {
    "game_id": 11,
    "old_start_date": "2026-10-03T19:30:00Z",
    "new_start_date": "2026-10-03T15:00:00Z",
}


def chained_lock() -> dict:
    """Base through post-week 1; post-week 2 adds games 10 and 11 (11 revised); 3 adds 20."""
    week2 = {
        "added_post_week": 2,
        "added_cutoff": "2026-09-14T00:00:00Z",
        "newly_final_game_ids": [10, 11],
        "completed_games_before": 2,
        "completed_games_after": 4,
        "base_game_rows_sha256": rows_sha256(ROWS_BASE),
        "game_rows_sha256": rows_sha256(ROWS_W2),
        "kickoff_revisions": [dict(REVISION_11)],
    }
    week3 = {
        "added_post_week": 3,
        "added_cutoff": "2026-09-21T00:00:00Z",
        "newly_final_game_ids": [20],
        "completed_games_before": 4,
        "completed_games_after": 5,
        "base_game_rows_sha256": rows_sha256(ROWS_W2),
        "game_rows_sha256": rows_sha256(ROWS_W3),
        "kickoff_revisions": [],
        "previous_extension": week2,
    }
    return {
        "post_week_cutoffs": {
            "0": "2026-09-01T00:00:00Z",
            "1": "2026-09-07T00:00:00Z",
            "2": "2026-09-14T00:00:00Z",
            "3": "2026-09-21T00:00:00Z",
        },
        "game_rows_sha256": rows_sha256(ROWS_BASE),
        "games": {"columns": COLUMNS, "rows": copy.deepcopy(ROWS_W3)},
        "extends": week3,
    }


def coverage(games_through: int, weeks_through: int) -> dict:
    return {
        "published_coverage": {
            "team_game_measurements": games_through,
            **dict.fromkeys(pc.WEEK_TABLES, weeks_through),
        }
    }


def test_an_unextended_lock_adds_nothing():
    scope = pc.lock_scope({"post_week_cutoffs": {"0": "2026-09-01T00:00:00Z"}})
    assert scope["added"] == {} and scope["revisions"] == {}
    assert pc.game_scope(scope) is None and pc.week_scope(scope) is None
    additions = pc.table_additions(coverage(0, 0), scope)
    assert all(pc.addition_scope(table, additions) is None for table in additions)


def test_the_chain_is_followed_to_every_extension_and_revision():
    scope = pc.lock_scope(chained_lock())
    assert scope["added"] == {2: {10, 11}, 3: {20}}
    assert (scope["base_post_week"], scope["latest_post_week"]) == (1, 3)
    assert list(scope["revisions"]) == [11]  # recorded by the older extension


def test_each_table_takes_its_own_coverage():
    scope = pc.lock_scope(chained_lock())
    additions = pc.table_additions(coverage(1, 2), scope)
    games = pc.addition_scope("team_game_measurements", additions)
    frame = pd.DataFrame({"game_id": [2, 10, 11, 20]})
    assert games(frame).tolist() == [False, True, True, True]
    assert additions["team_game_measurements"]["first_as_of_week"] is None
    weeks = pc.addition_scope("team_rating_components", additions)
    assert weeks(pd.DataFrame({"as_of_week": [3, 4]})).tolist() == [False, True]
    current = pc.table_additions(coverage(3, 3), scope)
    assert all(pc.addition_scope(t, current) is None for t in current)


@pytest.mark.parametrize(
    "policies",
    [
        coverage(0, 2),  # before the chain's base: those additions cannot be enumerated
        coverage(1, 4),  # past the lock
        {"published_coverage": {"team_game_measurements": 1}},  # tables left out
        {},
    ],
)
def test_coverage_outside_the_chain_or_incomplete_is_refused(policies):
    with pytest.raises(GateError, match="published_coverage"):
        pc.table_additions(policies, pc.lock_scope(chained_lock()))


def _week2(lock):
    return lock["extends"]["previous_extension"]


@pytest.mark.parametrize(
    ("mutate", "word"),
    [
        (lambda lock: _week2(lock).update(completed_games_after=5), "game count"),
        (
            lambda lock: lock["extends"].update(
                completed_games_before=3, completed_games_after=4
            ),
            "follow",
        ),
        (lambda lock: _week2(lock).update(base_game_rows_sha256="0" * 64), "follow"),
        (lambda lock: lock["extends"].update(newly_final_game_ids=[11]), "twice"),
        (lambda lock: lock["extends"].update(newly_final_game_ids=[21]), "missing"),
        (lambda lock: lock["extends"].update(added_post_week=4), "continue"),
        (
            lambda lock: lock["extends"].update(added_cutoff="2026-09-22T00:00:00Z"),
            "continue",
        ),
        (lambda lock: lock["extends"].pop("completed_games_before"), "malformed"),
        (lambda lock: lock["games"]["rows"][0].__setitem__(4, "Z"), "game rows"),
        (lambda lock: lock.pop("post_week_cutoffs"), "malformed"),
    ],
)
def test_malformed_or_inconsistent_history_is_refused(mutate, word):
    lock = chained_lock()
    mutate(lock)
    with pytest.raises(GateError, match=word):
        pc.lock_scope(lock)


def test_conflicting_or_unlocked_revisions_are_refused():
    lock = chained_lock()
    lock["extends"]["kickoff_revisions"] = [
        {**REVISION_11, "new_start_date": "2026-10-03T16:00:00Z"}
    ]
    with pytest.raises(GateError, match="conflicting"):
        pc.lock_scope(lock)
    lock = chained_lock()
    lock["extends"]["kickoff_revisions"] = [
        {
            "game_id": 20,
            "old_start_date": "2026-09-19T19:00:00Z",
            "new_start_date": "2026-09-19T17:00:00Z",
        }
    ]
    with pytest.raises(GateError, match="new kickoff"):
        pc.lock_scope(lock)


def test_the_week6_lock_and_plan_enumerate_the_week5_and_week6_additions():
    plan = yaml.safe_load(Path("conf/rebuild/6a_task4_w6_v2.yaml").read_text())
    lock = json.loads(Path("conf/rebuild/source_lock_2026_w6_v1.json").read_text())
    scope = pc.lock_scope(lock)
    assert {week: len(games) for week, games in scope["added"].items()} == {
        5: 56,
        6: 58,
    }
    assert list(scope["revisions"]) == [401862787]
    additions = pc.table_additions(plan["policies"], scope)
    assert len(additions["team_game_measurements"]["games"]) == 114
    assert {additions[t]["first_as_of_week"] for t in pc.WEEK_TABLES} == {7}


def _components(weeks):
    return pd.DataFrame(
        {
            "component_id": [f"c{w}" for w in weeks],
            "as_of_week": weeks,
            "rating_mean": [1.0] * len(weeks),
        }
    )


def _diff(built, published, additions):
    return pd_.diff_frames(
        built,
        published,
        keys=["component_id"],
        columns=["as_of_week", "rating_mean"],
        metric_of=lambda row: None,
        added_scope=pc.addition_scope("team_rating_components", additions),
    )


def test_additions_never_hide_a_missing_published_row_or_cover_a_published_one():
    additions = pc.table_additions(coverage(1, 2), pc.lock_scope(chained_lock()))
    clean = _diff(_components([2, 3, 4]), _components([2, 3]), additions)
    assert not clean["unexplained"] and clean["added_scope"]["rows"] == 1
    missing = _diff(_components([2, 4]), _components([2, 3]), additions)
    assert missing["unexplained"] and missing["population"]["only_published"] == 1
    covered = _diff(_components([2, 3, 4]), _components([2, 3, 4]), additions)
    assert covered["unexplained"]
    assert covered["added_scope"]["published_rows_in_scope"] == 1


def _row(game, built, published):
    return pd.Series(
        {"game_id_built": game, "cutoff_utc_built": built, "cutoff_utc_pub": published}
    )


def test_only_the_recorded_revision_is_named():
    override = pc.kickoff_revision(pc.lock_scope(chained_lock()))
    new, old = (
        pd.Timestamp("2026-10-03T15:00:00Z"),
        pd.Timestamp("2026-10-03T19:30:00Z"),
    )
    assert override(_row(11, new, old), "cutoff_utc") == "kickoff_revision"
    assert override(_row(11, new, old), "rating_mean") is None
    assert override(_row(12, new, old), "cutoff_utc") is None
    # A different new value, or the direction reversed, is not the recorded revision.
    other = pd.Timestamp("2026-10-03T16:00:00Z")
    assert override(_row(11, other, old), "cutoff_utc") is None
    assert override(_row(11, old, new), "cutoff_utc") is None


def test_the_revision_makes_a_cutoff_difference_explained_but_not_a_rating_change():
    override = pc.kickoff_revision(pc.lock_scope(chained_lock()))
    old, new = "2026-10-03T19:30:00+00:00", "2026-10-03T15:00:00+00:00"

    def frame(cutoff, rating):
        return pd.DataFrame(
            {
                "component_id": ["a"],
                "game_id": [11],
                "cutoff_utc": pd.to_datetime([cutoff], utc=True),
                "rating_mean": [rating],
            }
        )

    def run(built):
        return pd_.diff_frames(
            built,
            frame(old, 1.0),
            keys=["component_id"],
            columns=["game_id", "cutoff_utc", "rating_mean"],
            metric_of=lambda row: None,
            expected={"kickoff_revision"},
            bucket_override=override,
        )

    assert not run(frame(new, 1.0))["unexplained"]
    changed = run(frame(new, 1.5))
    assert changed["unexplained"] and "ratings" in changed["unexplained_buckets"]


RATINGS_V1 = "v5-intended-update-2026-ratings-v1"
W6LIVE = "v5-intended-update-2026-corrected-w6live-r1"
POLICY = {"published_rating_runs": {RATINGS_V1: [0, 1, 2, 3, 4, 5], W6LIVE: [6]}}


@pytest.mark.parametrize("path", ["6a_task4_w6_v1.yaml", "6a_task4_w6_v2.yaml"])
def test_the_week6_plans_map_weeks_0_to_5_and_week_6_to_their_runs(path):
    plan = yaml.safe_load((Path("conf/rebuild") / path).read_text())
    week_runs = pc.published_rating_runs(plan["policies"])
    assert week_runs == {**dict.fromkeys(range(6), RATINGS_V1), 6: W6LIVE}


def test_a_missing_or_overlapping_policy_is_refused():
    with pytest.raises(GateError, match="missing"):
        pc.published_rating_runs({})
    with pytest.raises(GateError, match="two runs"):
        pc.published_rating_runs({"published_rating_runs": {"a": [5], "b": [5, 6]}})


def test_exactly_the_planned_runs_are_accepted():
    week_runs = pc.published_rating_runs(POLICY)
    pc.check_published_runs([W6LIVE, RATINGS_V1], week_runs)
    for found, word in [
        ([RATINGS_V1], "missing"),
        ([RATINGS_V1, W6LIVE, "other-run"], "unexpected"),
        ([RATINGS_V1, "other-run"], "unexpected"),
        ([], "missing"),
    ]:
        with pytest.raises(GateError, match=word):
            pc.check_published_runs(found, week_runs)


def test_a_single_run_is_accepted_only_when_the_plan_names_one():
    single = pc.published_rating_runs({"published_rating_runs": {RATINGS_V1: [0, 1]}})
    pc.check_published_runs([RATINGS_V1], single)
    with pytest.raises(GateError):
        pc.check_published_runs([RATINGS_V1], pc.published_rating_runs(POLICY))


def test_each_week_carries_its_runs_ids():
    @dataclasses.dataclass
    class Artifacts:
        run_id: str

    def build(artifacts):
        weeks = [0, 5, 6, 7]
        frames = {
            "team_rating_components": pd.DataFrame(
                {
                    "component_id": [f"{artifacts.run_id}:{w}" for w in weeks],
                    "as_of_week": weeks,
                }
            ),
            "team_game_measurements": pd.DataFrame({"run": [artifacts.run_id]}),
        }
        return SimpleNamespace(payload=SimpleNamespace(frames=frames))

    frames = pc.build_frames(Artifacts("x"), pc.published_rating_runs(POLICY), build)
    components = frames["team_rating_components"].sort_values("as_of_week")
    assert components["component_id"].tolist() == [
        f"{RATINGS_V1}:0",
        f"{RATINGS_V1}:5",
        f"{W6LIVE}:6",
        f"{W6LIVE}:7",  # past the plan: the newest run's ids (lock-extension scope)
    ]
    assert frames["team_game_measurements"]["run"].tolist() == [W6LIVE]


# ---- two-lineage rating controls ------------------------------------------------------

V2_PLAN = RebuildPlan.from_dict(
    yaml.safe_load(Path("conf/rebuild/6a_task4_w6_v2.yaml").read_text())
)
PINS = {pin.name: pin for pin in V2_PLAN.inputs}
V1_SHA = PINS["ratings_v1_rating_manifest"].sha256
W6_SHA = PINS["w6live_rating_manifest"].sha256
W4_MEASUREMENT = (
    "artifacts/.../possession-v1-measurements-20260927-w4/m.json",
    "c4" * 32,
)
W5_ROOT = ("rebuild/6a/6a-rebuild-w5-20261007-r2/root-manifest.json", "78" * 32)


def _publication(pin, measurement, publication_id):
    return {
        "publication_id": publication_id,
        "rating_manifest_uri": PINS[pin].uri,
        "rating_manifest_sha256": PINS[pin].sha256,
        "measurement_manifest_uri": measurement[0],
        "measurement_manifest_sha256": measurement[1],
    }


PUBLICATIONS = [
    _publication("ratings_v1_rating_manifest", W4_MEASUREMENT, "2026:a"),
    _publication("w6live_rating_manifest", W5_ROOT, "2026:b"),
]


def _controls(policies=None, publications=PUBLICATIONS):
    policies = dict(V2_PLAN.policies) if policies is None else policies
    week_runs = pc.published_rating_runs(policies)
    return pc.bind_publications(
        pc.rating_controls(policies, PINS, week_runs), publications
    )


def test_the_v2_plan_binds_each_run_to_its_own_lineage():
    controls = _controls()
    assert {r: (c["method"], c["weeks"]) for r, c in controls.items()} == {
        RATINGS_V1: (pc.SERVED_R9_REPLAY, [0, 1, 2, 3, 4, 5]),
        W6LIVE: (pc.SIX_A_BRIDGE, [6]),
    }
    assert controls[W6LIVE]["measurement_uri"] == W5_ROOT[0]
    assert controls[RATINGS_V1]["sha256"] == V1_SHA


def _policies(**controls):
    policies = copy.deepcopy(dict(V2_PLAN.policies))
    policies["rating_controls"].update(controls)
    return policies


@pytest.mark.parametrize(
    ("policies", "word"),
    [
        (_policies(**{"other-run": {"method": pc.SIX_A_BRIDGE}}), "published runs"),
        (
            _policies(**{W6LIVE: {"method": "guess", "rating_manifest": "x"}}),
            "unknown method",
        ),
        (
            _policies(
                **{
                    W6LIVE: {
                        "method": pc.SIX_A_BRIDGE,
                        "rating_manifest": "ratings_v1_rating_manifest",
                    }
                }
            ),
            "no pinned manifest",
        ),
    ],
)
def test_unknown_runs_and_wrong_manifest_bindings_are_refused(policies, word):
    with pytest.raises(GateError, match=word):
        _controls(policies)


@pytest.mark.parametrize(
    ("publications", "word"),
    [
        (PUBLICATIONS[:1], "no publication"),
        (
            [PUBLICATIONS[0], {**PUBLICATIONS[1], "rating_manifest_sha256": "0" * 64}],
            "different rating manifest",
        ),
        (
            [
                *PUBLICATIONS,
                {**PUBLICATIONS[1], "measurement_manifest_sha256": "1" * 64},
            ],
            "measurement parents",
        ),
    ],
)
def test_the_publication_metadata_must_record_the_pinned_manifests(publications, word):
    with pytest.raises(GateError, match=word):
        _controls(publications=publications)


def test_a_rating_manifest_must_be_its_runs_over_the_published_parent():
    manifest = signed_payload(
        {
            "identity": {"run_id": W6LIVE},
            "parents": {"measurement_manifest_sha256": W5_ROOT[1]},
        }
    )
    pc.check_rating_manifest(manifest, W6LIVE, W5_ROOT[1])
    with pytest.raises(GateError, match="not"):
        pc.check_rating_manifest(manifest, RATINGS_V1, W5_ROOT[1])
    with pytest.raises(GateError, match="parent"):
        pc.check_rating_manifest(manifest, W6LIVE, W4_MEASUREMENT[1])
    with pytest.raises(Exception, match="checksum"):
        pc.check_rating_manifest({**manifest, "state": "edited"}, W6LIVE, W5_ROOT[1])


def _published_components(rows):
    """Component rows (run, sha, week, rating) with every published column filled."""
    frame = pd.DataFrame(
        [
            {
                **dict.fromkeys(md.COMPONENT_COLUMNS, 0.0),
                "component_id": f"{run}:pregame:T{i}:{week}:offense",
                "v5_snapshot_id": f"{run}:pregame:T{i}:{week}",
                "source_manifest_sha256": sha,
                "as_of_week": week,
                "game_id": 100 + i,
                "cutoff_utc": pd.Timestamp("2026-10-10T20:00:00Z"),
                "rating_mean": rating,
                "evidence": "{}",
                "excluded_observations": "[]",
                "prior_detail": "{}",
                "fallback_reason": None,
            }
            for i, (run, sha, week, rating) in enumerate(rows)
        ]
    )
    return frame


BOTH = [
    (RATINGS_V1, V1_SHA, 0, 1.0),
    (RATINGS_V1, V1_SHA, 5, 2.0),
    (W6LIVE, W6_SHA, 6, 3.0),
    (W6LIVE, W6_SHA, 6, 4.0),
]


def test_both_lineages_partition_every_published_component():
    parts = pc.partition_components(_published_components(BOTH), _controls())
    assert {run: len(part) for run, part in parts.items()} == {
        RATINGS_V1: 2,
        W6LIVE: 2,
    }


@pytest.mark.parametrize(
    ("rows", "word"),
    [
        ([*BOTH, (W6LIVE, "f" * 64, 6, 1.0)], "unknown rating manifests"),
        ([*BOTH, (RATINGS_V1, W6_SHA, 6, 1.0)], "run other than"),  # wrong binding
        (BOTH[:2], f"no published components of {W6LIVE}"),
        ([*BOTH, (W6LIVE, W6_SHA, 5, 1.0)], "outside its weeks"),  # overlaps ratings-v1
    ],
)
def test_unknown_mismatched_missing_or_overlapping_partitions_are_refused(rows, word):
    with pytest.raises(GateError, match=word):
        pc.partition_components(_published_components(rows), _controls())


def test_a_control_reproduces_its_partition_and_an_altered_week6_value_fails():
    parts = pc.partition_components(_published_components(BOTH), _controls())
    reports = {
        run: {"team_rating_components": pc.control_diff(part, part, md, None)}
        for run, part in parts.items()
    }
    assert pc.summarize_controls(reports)["matches_published"]
    altered = parts[W6LIVE].copy()
    altered.loc[altered.index[0], "rating_mean"] += 0.01
    reports[W6LIVE] = {
        "team_rating_components": pc.control_diff(altered, parts[W6LIVE], md, None)
    }
    summary = pc.summarize_controls(reports)
    assert not summary["matches_published"]
    assert summary["team_rating_components"]["rows_with_a_difference"] == 1
    assert summary["team_rating_components"]["rows_published"] == 4


# ---- kickoff-revision evidence ---------------------------------------------------------

LOCK_PATH = Path("conf/rebuild/source_lock_2026_w6_v1.json")
EVIDENCE_PATH = Path("conf/rebuild/task4_w6_kickoff_revisions_v1.json")
GAMES = {401862787, 401862797, 401856827, 401856808}


def _evidence_inputs():
    raw = LOCK_PATH.read_bytes()
    lock = json.loads(raw)
    return (
        json.loads(EVIDENCE_PATH.read_text()),
        lock,
        hashlib.sha256(raw).hexdigest(),
        pc.lock_scope(lock),
        _controls(),
    )


def test_the_pinned_evidence_binds_four_games_to_the_lock_and_the_controls():
    assert PINS["kickoff_revision_evidence"].sha256 == (
        hashlib.sha256(EVIDENCE_PATH.read_bytes()).hexdigest()
    )
    evidence, *rest = _evidence_inputs()
    revisions = pc.kickoff_evidence(evidence, *rest)
    assert set(revisions) == GAMES and evidence["expected_cutoff_cells"] == 16
    # The Week 5 revision is the one the lock chain recorded.
    assert revisions[401862787] == rest[2]["revisions"][401862787]


def _mutated(edit):
    evidence, *rest = _evidence_inputs()
    edit(evidence)
    return evidence, *rest


@pytest.mark.parametrize(
    ("edit", "word"),
    [
        (
            lambda e: e["revisions"][0].update(built_utc="2026-10-03T16:00:00Z"),
            "does not hold",
        ),
        (  # conflicts with the revision the lock chain recorded
            lambda e: e["revisions"][0].update(published_utc="2026-10-03T19:00:00Z"),
            "conflicts",
        ),
        (lambda e: e["revisions"].pop(0), "conflicts"),
        (lambda e: e["revisions"].append(dict(e["revisions"][1])), "twice"),
        (lambda e: e["built_source"].update(sha256="0" * 64), "different source lock"),
        (
            lambda e: e["published_sources"][W6LIVE].update(
                rating_manifest_sha256=V1_SHA
            ),
            "not its pinned",
        ),
        (lambda e: e["revisions"][1].update(published_run="other"), "unbound"),
        (
            lambda e: e["revisions"][1].update(published_utc="2026-10-10T17:00:00Z"),
            "not an exact",
        ),
        (lambda e: e.update(expected_cutoff_cells=12), "expected cells"),
    ],
)
def test_conflicting_or_unbound_evidence_is_refused(edit, word):
    with pytest.raises(GateError, match=word):
        pc.kickoff_evidence(*_mutated(edit))


def _cutoff_frames(cutoffs, rating=1.0):
    """Four components per game, one frame per side, from ``{game: utc}``."""
    rows = [
        {
            "component_id": f"{game}:{team}:{role}",
            "game_id": game,
            "cutoff_utc": pd.Timestamp(utc),
            "rating_mean": rating,
        }
        for game, utc in cutoffs.items()
        for team in ("home", "away")
        for role in ("offense", "defense")
    ]
    return pd.DataFrame(rows)


def _evidenced_diff(built, published, metric):
    revisions = pc.kickoff_evidence(*_evidence_inputs())
    return pd_.diff_frames(
        built,
        published,
        keys=["component_id"],
        columns=["game_id", "cutoff_utc", "rating_mean"],
        metric_of=lambda row: metric,
        expected={"kickoff_revision", "history_correction"},
        bucket_override=pc.kickoff_revision({"revisions": revisions}, strict=True),
    )


EVIDENCE = json.loads(EVIDENCE_PATH.read_text())["revisions"]
PUBLISHED = {r["game_id"]: r["published_utc"] for r in EVIDENCE}
BUILT = {r["game_id"]: r["built_utc"] for r in EVIDENCE}


def test_exactly_the_sixteen_evidenced_cells_are_explained():
    report = _evidenced_diff(
        _cutoff_frames(BUILT), _cutoff_frames(PUBLISHED), "history_correction"
    )
    assert report["differences_by_bucket"] == {"kickoff_revision": {"cutoff_utc": 16}}
    assert not report["unexplained"]


@pytest.mark.parametrize(
    ("built", "published"),
    [
        (PUBLISHED, BUILT),  # reversed
        (BUILT | {401862797: "2026-10-10T18:00:00Z"}, PUBLISHED),  # altered
        ({999: "2026-10-10T18:00:00Z"}, {999: "2026-10-10T17:00:00Z"}),  # unlisted
    ],
)
def test_a_reversed_altered_or_unlisted_cutoff_is_never_absorbed(built, published):
    # Even where the history correction is expected, an unevidenced cutoff stays a finding.
    report = _evidenced_diff(
        _cutoff_frames(built), _cutoff_frames(published), "history_correction"
    )
    assert report["unexplained"]
    assert pc.UNEVIDENCED_CUTOFF in report["unexplained_buckets"]


def test_numeric_drift_alongside_a_valid_revision_is_still_unexplained():
    # Controls attribute no rating change (metric None -> "ratings").
    report = _evidenced_diff(
        _cutoff_frames(BUILT, rating=1.5), _cutoff_frames(PUBLISHED), None
    )
    assert report["differences_by_bucket"]["kickoff_revision"] == {"cutoff_utc": 16}
    assert report["unexplained_buckets"] == {"ratings": {"rating_mean": 16}}


def test_task4_r3_only_updates_stats_coverage_and_preserves_pins():
    previous = yaml.safe_load(Path("conf/rebuild/6a_task4_w6_v2.yaml").read_text())
    current = yaml.safe_load(Path("conf/rebuild/6a_task4_w6_v3.yaml").read_text())
    expected = copy.deepcopy(previous)
    expected["run_id"] = "6a-task4-w6-r3"
    expected["policies"]["published_coverage"]["team_season_stats"] = 6
    for stage in expected["stages"]:
        stage["outputs"] = [
            prefix.replace("6a-task4-w6-r2", "6a-task4-w6-r3")
            for prefix in stage["outputs"]
        ]
    assert current == expected
    plan = RebuildPlan.from_dict(current)
    plan.validate()
    for pin in plan.inputs:
        if pin.kind == "git_file":
            assert hashlib.sha256(Path(pin.uri).read_bytes()).hexdigest() == pin.sha256


def test_task4_r3_compares_existing_asof7_stats_and_retains_other_additions():
    previous = yaml.safe_load(Path("conf/rebuild/6a_task4_w6_v2.yaml").read_text())
    current = yaml.safe_load(Path("conf/rebuild/6a_task4_w6_v3.yaml").read_text())
    lock = json.loads(Path("conf/rebuild/source_lock_2026_w6_v1.json").read_text())
    scope = pc.lock_scope(lock)
    old = pc.table_additions(previous["policies"], scope)
    new = pc.table_additions(current["policies"], scope)
    assert new["team_season_stats"]["first_as_of_week"] is None
    assert len(new["team_game_measurements"]["games"]) == 114
    for table in set(new) - {"team_season_stats"}:
        assert new[table] == old[table]
    frame = pd.DataFrame(
        {"as_of_week": [6, 7], "team": ["A", "A"], "value": [1.0, 2.0]}
    )
    report = pd_.diff_frames(
        frame,
        frame,
        keys=["as_of_week", "team"],
        columns=["value"],
        metric_of=lambda _: None,
        added_scope=pc.addition_scope("team_season_stats", new),
    )
    assert report["rows_compared"] == 2
    assert "added_scope" not in report
    assert not report["unexplained"]
