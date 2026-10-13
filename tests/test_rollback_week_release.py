"""Week N release rollback: guards, provenance-scoped deletes and before/after state.

An in-memory fake stands in for Postgres; it answers exactly the statements the
rollback and the shared deselect path issue, so no database is touched.
"""

from __future__ import annotations

import json

import pytest

from scripts.pipeline import rollback_week_release as rollback

RUN = "2026w7-test-pending"
PRIOR = "2026w6-test-display"
SHA = "a" * 64
OTHER_SHA = "b" * 64
EARLIER = {str(w): f"2026w{w}-test" for w in range(6)}  # Weeks 0-5 selections
VERSIONS = {"byplay": "bp7", "drives": "dr7", "games": "gm7", "game_outcomes": "go7"}
OLD_VERSIONS = {
    "byplay": "bp6",
    "drives": "dr6",
    "games": "gm6",
    "game_outcomes": "go6",
}


class FakeDb:
    def __init__(self, *, display_only: bool = False, user: str = "neondb_owner"):
        self.user = user
        self.committed = False
        self.rolled_back = False
        self.runs = {
            PRIOR: {
                "season": 2026,
                "week": 6,
                "state": "published",
                "evidence_class": "pending",
                "frozen_at": None,
                "rating_manifest_sha256": OTHER_SHA,
            },
            RUN: {
                "season": 2026,
                "week": 7,
                "state": "published",
                "evidence_class": "pending",
                "frozen_at": None,
                "rating_manifest_sha256": SHA,
                "validation": {"display_only": True} if display_only else {},
            },
        }
        self.grades: dict[str, int] = {}
        self.selections = {(2026, int(w)): r for w, r in EARLIER.items()}
        self.selections.update({(2025, 7): "2025w7-test", (2026, 6): PRIOR})
        self.selections[(2026, 7)] = RUN
        self.writes: list[str] = []  # table of every write, in order
        self.history: list[tuple] = []
        self.current_week = [2026, 7, RUN]
        # 3 rows from this release's Silver versions plus 2 older as-of-7 rows
        # published by someone else (different versions): only the first go.
        self.stats = [
            {"season": 2026, "as_of_week": 7, "source_versions": VERSIONS}
            for _ in range(3)
        ] + [
            {"season": 2026, "as_of_week": 7, "source_versions": OLD_VERSIONS}
            for _ in range(2)
        ]
        self.stats.append(
            {"season": 2026, "as_of_week": 6, "source_versions": OLD_VERSIONS}
        )
        self.snapshots = [
            {"snapshot_id": f"s{i}", "source_manifest_sha256": SHA} for i in range(4)
        ] + [{"snapshot_id": "old", "source_manifest_sha256": OTHER_SHA}]
        self.components: list[str] = []

    def connection(self):
        return FakeConn(self)


class FakeConn:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self):
        return FakeCursor(self.db)

    def commit(self):
        self.db.committed = True

    def rollback(self):
        self.db.rolled_back = True


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self._rows: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def execute(self, sql, params=()):  # noqa: C901 - one branch per statement
        db, s = self.db, " ".join(sql.split())
        rows: list[tuple] = []
        if s == "SELECT current_user":
            rows = [(db.user,)]
        elif s.startswith("SELECT pg_advisory_xact_lock"):
            rows = [(None,)]
        elif s.startswith("SELECT state, evidence_class, frozen_at"):
            run = db.runs.get(params[0])
            if run and (run["season"], run["week"]) == params[1:]:
                rows = [
                    (
                        run["state"],
                        run["evidence_class"],
                        run["frozen_at"],
                        run["rating_manifest_sha256"],
                    )
                ]
        elif s.startswith("SELECT count(*) FROM prediction_grades"):
            rows = [(db.grades.get(params[0], 0),)]
        elif s.startswith("SELECT run_id FROM site_week_selections"):
            run = db.selections.get(tuple(params))
            rows = [(run,)] if run else []
        elif s.startswith("SELECT run_id FROM prediction_runs WHERE rating_manifest"):
            rows = [
                (rid,)
                for rid, r in sorted(db.runs.items())
                if r["rating_manifest_sha256"] == params[0] and rid != params[1]
            ]
        elif s.startswith("SELECT count(*) FROM team_rating_components"):
            ids = {
                x["snapshot_id"]
                for x in db.snapshots
                if x["source_manifest_sha256"] == params[0]
            }
            rows = [(sum(1 for c in db.components if c in ids),)]
        elif s.startswith("SELECT season, week, active_run_id FROM current_week"):
            rows = [tuple(db.current_week)]
        elif s.startswith("SELECT week, run_id FROM site_week_selections"):
            rows = [
                (w, r)
                for (se, w), r in sorted(db.selections.items())
                if se == params[0]
            ]
        elif s.startswith("SELECT count(*) FROM team_season_stats"):
            rows = [(len(self._stats(params)),)]
        elif s.startswith("SELECT count(*) FROM v5_rating_snapshots"):
            rows = [
                (
                    sum(
                        1
                        for x in db.snapshots
                        if x["source_manifest_sha256"] == params[0]
                    ),
                )
            ]
        elif s.startswith("INSERT INTO site_week_selection_history"):
            db.history.append(tuple(params))
        elif s.startswith("DELETE FROM site_week_selections"):
            if db.user.endswith("_pipeline"):
                raise PermissionError("pipeline role cannot delete selections")
            db.selections.pop(tuple(params), None)
        elif s.startswith("UPDATE current_week"):
            db.current_week = list(params)
        elif s.startswith("DELETE FROM team_season_stats"):
            doomed = self._stats(params)
            db.stats = [x for x in db.stats if not any(x is d for d in doomed)]
        elif s.startswith("DELETE FROM v5_rating_snapshots"):
            db.snapshots = [
                x for x in db.snapshots if x["source_manifest_sha256"] != params[0]
            ]
        else:  # pragma: no cover - an unknown statement is a test bug
            raise AssertionError(f"unexpected SQL: {s}")
        verb, *words = s.split()
        if verb in {"INSERT", "DELETE"}:  # INSERT INTO t / DELETE FROM t
            db.writes.append(words[1])
        elif verb == "UPDATE":
            db.writes.append(words[0])
        self._rows = rows

    def _stats(self, params):
        season, week, *versions = params
        return [
            x
            for x in self.db.stats
            if x["season"] == season
            and x["as_of_week"] == week
            and (not versions or x["source_versions"] == json.loads(versions[0]))
        ]


def _receipt(**published):
    return {
        "schema_version": rollback.RECEIPT_SCHEMA,
        "environment": "preview",
        "run_id": RUN,
        "season": 2026,
        "week": 7,
        "published": published
        or {
            "team_season_stats": {"as_of_week": 7, "source_versions": VERSIONS},
            "v5_rating_snapshots": {"source_manifest_sha256": SHA},
        },
    }


def _run_cli(monkeypatch, tmp_path, db, *extra, receipt=None):
    monkeypatch.setattr(rollback.psycopg, "connect", lambda _url: db.connection())
    argv = [
        "--environment",
        "preview",
        "--week",
        "7",
        "--run-id",
        RUN,
        "--reason",
        "test rollback",
        "--database-url",
        "postgresql://fake",
        *extra,
    ]
    if receipt is not None:
        path = tmp_path / "receipt.json"
        path.write_text(json.dumps(receipt))
        argv += ["--release-receipt", str(path)]
    return rollback.main(argv)


def _states(out):
    states = {}
    for line in out.splitlines():
        label, sep, payload = line.partition(": ")
        if sep and label in {"before", "after", "after (planned)"}:
            states[label] = json.loads(payload)
    return states


@pytest.mark.parametrize("display_only", [True, False])
def test_apply_restores_prior_week_and_removes_release_rows(
    monkeypatch, tmp_path, capsys, display_only
):
    db = FakeDb(display_only=display_only)
    code = _run_cli(monkeypatch, tmp_path, db, "--apply", receipt=_receipt())
    states = _states(capsys.readouterr().out)

    assert code == 0 and db.committed and not db.rolled_back
    assert states["before"] == {
        "current_week": [2026, 7, RUN],
        "selections": {**EARLIER, "6": PRIOR, "7": RUN},
        "team_season_stats_as_of_week": 5,
        "team_season_stats_release_rows": 3,
        "v5_rating_snapshots_run_manifest": 4,
    }
    assert states["after"] == {
        "current_week": [2026, 6, PRIOR],
        "selections": {**EARLIER, "6": PRIOR, "7": None},
        "team_season_stats_as_of_week": 2,
        "team_season_stats_release_rows": 0,
        "v5_rating_snapshots_run_manifest": 0,
    }
    # Other publishers' rows and the prior week's snapshots survive.
    assert [x["source_versions"] for x in db.stats if x["as_of_week"] == 7] == [
        OLD_VERSIONS,
        OLD_VERSIONS,
    ]
    assert [x["snapshot_id"] for x in db.snapshots] == ["old"]
    assert db.history == [(2026, 7, RUN, RUN, "DESELECTED: test rollback")]


@pytest.mark.parametrize("display_only", [True, False])
def test_dry_run_prints_planned_after_and_writes_nothing(
    monkeypatch, tmp_path, capsys, display_only
):
    db = FakeDb(display_only=display_only)
    code = _run_cli(monkeypatch, tmp_path, db, receipt=_receipt())
    states = _states(capsys.readouterr().out)

    assert code == 0 and not db.committed
    assert states["before"]["current_week"] == [2026, 7, RUN]
    assert states["after (planned)"]["current_week"] == [2026, 6, PRIOR]
    assert states["after (planned)"]["selections"] == {
        **EARLIER,
        "6": PRIOR,
        "7": None,
    }
    assert db.selections[(2026, 7)] == RUN and db.current_week == [2026, 7, RUN]
    assert len(db.stats) == 6 and len(db.snapshots) == 5 and not db.history


def test_without_receipt_only_selection_and_pointer_change(
    monkeypatch, tmp_path, capsys
):
    db = FakeDb()
    assert _run_cli(monkeypatch, tmp_path, db, "--apply") == 0
    out = capsys.readouterr().out
    assert "no release receipt" in out
    assert db.current_week == [2026, 6, PRIOR] and (2026, 7) not in db.selections
    assert len(db.stats) == 6 and len(db.snapshots) == 5


def test_snapshots_shared_with_another_run_are_kept(monkeypatch, tmp_path, capsys):
    db = FakeDb()
    db.runs[PRIOR]["rating_manifest_sha256"] = SHA
    assert _run_cli(monkeypatch, tmp_path, db, "--apply", receipt=_receipt()) == 0
    assert "manifest also used by ['2026w6-test-display']" in capsys.readouterr().out
    assert len(db.snapshots) == 5
    assert sum(1 for x in db.stats if x["as_of_week"] == 7) == 2


def _refused(monkeypatch, tmp_path, capsys, db, *extra, receipt=None):
    code = _run_cli(monkeypatch, tmp_path, db, *extra, receipt=receipt)
    err = capsys.readouterr().err
    assert code == 3 and not db.committed
    assert db.selections[(2026, 7)] == RUN and db.current_week == [2026, 7, RUN]
    assert len(db.stats) == 6 and len(db.snapshots) == 5
    return err


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda r: r.update(state="frozen"), "run is frozen"),
        (lambda r: r.update(frozen_at="2026-10-17T21:00:00Z"), "never rolled back"),
        (lambda r: r.update(state="scored"), "run is scored"),
        (lambda r: r.update(state="preview"), "only a published pending run"),
        (lambda r: r.update(evidence_class="live"), "only a published pending run"),
        (lambda r: r.update(evidence_class="replay"), "only a published pending run"),
    ],
)
def test_refuses_runs_that_are_not_published_pending_unfrozen(
    monkeypatch, tmp_path, capsys, mutate, message
):
    db = FakeDb()
    mutate(db.runs[RUN])
    assert message in _refused(
        monkeypatch, tmp_path, capsys, db, "--apply", receipt=_receipt()
    )


def test_refuses_a_graded_run(monkeypatch, tmp_path, capsys):
    db = FakeDb()
    db.grades[RUN] = 110
    assert "110 grade(s)" in _refused(monkeypatch, tmp_path, capsys, db, "--apply")


@pytest.mark.parametrize("dry_run", [True, False])
def test_refuses_the_pipeline_login_on_apply(monkeypatch, tmp_path, capsys, dry_run):
    db = FakeDb(user="cks_prod_pipeline")
    if dry_run:  # the read-only dry run mirrors the Week 6 tool: any role may run it
        assert _run_cli(monkeypatch, tmp_path, db, receipt=_receipt()) == 0
        return
    err = _refused(monkeypatch, tmp_path, capsys, db, "--apply", receipt=_receipt())
    assert "restricted pipeline role cks_prod_pipeline" in err


def test_apply_rollback_itself_refuses_the_pipeline_login():
    db = FakeDb(user="cks_preview_pipeline")
    cur = FakeCursor(db)
    plan = rollback.plan_rollback(cur, season=2026, week=7, run_id=RUN, receipt=None)
    with pytest.raises(rollback.WeekRollbackError, match="pipeline role"):
        rollback.apply_rollback(cur, plan, reason="x")
    assert db.selections[(2026, 7)] == RUN


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda db: db.selections.update({(2026, 7): "someone-else"}), "points at"),
        (lambda db: db.current_week.__setitem__(2, PRIOR), "current_week is"),
        (lambda db: db.current_week.__setitem__(1, 6), "current_week is"),
        (lambda db: db.selections.pop((2026, 6)), "no selected run to restore"),
        (lambda db: db.runs.pop(RUN), "not present"),
        (lambda db: db.components.append("s0"), "restore the prior matchup payload"),
    ],
)
def test_refuses_state_that_is_not_this_release(
    monkeypatch, tmp_path, capsys, mutate, message
):
    db = FakeDb()
    mutate(db)
    code = _run_cli(monkeypatch, tmp_path, db, "--apply", receipt=_receipt())
    assert code == 3 and not db.committed
    assert message in capsys.readouterr().err
    assert len(db.stats) == 6 and len(db.snapshots) == 5


@pytest.mark.parametrize(
    "receipt, message",
    [
        ({**_receipt(), "run_id": "other"}, "another environment, run or week"),
        ({**_receipt(), "environment": "production"}, "another environment"),
        ({**_receipt(), "schema_version": "v0"}, "receipt schema"),
        (
            _receipt(team_season_stats={"as_of_week": 6, "source_versions": VERSIONS}),
            "as-of this week",
        ),
        (
            _receipt(v5_rating_snapshots={"source_manifest_sha256": OTHER_SHA}),
            "differs from the run's own manifest",
        ),
    ],
)
def test_refuses_a_receipt_that_does_not_match_the_run(
    monkeypatch, tmp_path, capsys, receipt, message
):
    db = FakeDb()
    assert message in _refused(
        monkeypatch, tmp_path, capsys, db, "--apply", receipt=receipt
    )


def test_apply_writes_only_restored_tables_and_receipt_scopes(monkeypatch, tmp_path):
    # Retained by design: approvals, catalog, schedule/venues, matchup rows and the
    # run row itself. The fake rejects any statement it does not know, so this list
    # is every write the tool can make.
    db = FakeDb()
    assert _run_cli(monkeypatch, tmp_path, db, "--apply", receipt=_receipt()) == 0
    assert db.writes == [
        "site_week_selection_history",
        "site_week_selections",
        "current_week",
        "team_season_stats",
        "v5_rating_snapshots",
    ]
    assert db.runs[RUN]["state"] == "published" and db.runs[RUN]["frozen_at"] is None
    assert RUN not in db.selections.values() and RUN not in db.current_week
    assert db.selections[(2025, 7)] == "2025w7-test"


@pytest.mark.parametrize(
    "published, stats_left, snapshots_left",
    [
        ({"team_season_stats": {"as_of_week": 7, "source_versions": VERSIONS}}, 2, 5),
        ({"v5_rating_snapshots": {"source_manifest_sha256": SHA}}, 5, 1),
    ],
)
def test_only_scopes_the_receipt_declares_are_removed(
    monkeypatch, tmp_path, published, stats_left, snapshots_left
):
    db = FakeDb()
    if "v5_rating_snapshots" not in published:
        db.components.append("s0")  # matchup rows on kept snapshots stay, inert
    receipt = _receipt(**published)
    assert _run_cli(monkeypatch, tmp_path, db, "--apply", receipt=receipt) == 0
    assert sum(1 for x in db.stats if x["as_of_week"] == 7) == stats_left
    assert len(db.snapshots) == snapshots_left
    assert db.current_week == [2026, 6, PRIOR] and (2026, 7) not in db.selections


def test_read_back_fails_when_an_earlier_week_selection_changes(
    monkeypatch, tmp_path, capsys
):
    deselect = rollback.deselect_week_run

    def deselect_and_touch_week_5(cur, **kwargs):
        cur.db.selections[(2026, 5)] = "intruder"
        return deselect(cur, **kwargs)

    monkeypatch.setattr(rollback, "deselect_week_run", deselect_and_touch_week_5)
    db = FakeDb()
    assert _run_cli(monkeypatch, tmp_path, db, "--apply", receipt=_receipt()) == 3
    assert db.rolled_back and not db.committed
    assert "VERIFY FAIL" in capsys.readouterr().err
