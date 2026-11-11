"""Weekly automation controller: decisions, cutoffs, resume and env isolation."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.ops import weekly_automation as wa

UTC = timezone.utc
NOW = datetime(2026, 11, 1, 17, 7, tzinfo=UTC)
PAST = NOW - timedelta(days=1)
FUTURE = NOW + timedelta(days=2)
PREVIEW_URL = "postgresql://preview-secret-host/db"
PROD_URL = "postgresql://production-secret-host/db"
SECRETS = {
    "CFBD_API_KEY": "cfbd-key-123456",
    "PREVIEW_DATABASE_URL": PREVIEW_URL,
    "PRODUCTION_PIPELINE_DATABASE_URL": PROD_URL,
    "CFB_R2_PREVIEW_BUCKET": "bucket-123456",
    "CFB_R2_PREVIEW_ACCOUNT_ID": "account-123456",
    "CFB_R2_PREVIEW_ACCESS_KEY": "access-123456",
    "CFB_R2_PREVIEW_SECRET_KEY": "secret-123456",
    "THE_ODDS_API_KEY": "odds-key-123456",
}


def games(start: datetime, n: int = 3, final: bool = True) -> list[wa.Game]:
    return [wa.Game(i, start + timedelta(hours=i), final) for i in range(n)]


# ------------------------------------------------------------ pure decisions


def test_close_week_runs_when_completed_final_and_next_not_started():
    d = wa.decide_close_week(
        now=NOW, active_week=9, completed=games(PAST), upcoming=games(FUTURE)
    )
    assert (d.action, d.completed_week, d.upcoming_week) == ("run", 9, 10)


def test_close_week_stops_when_next_kickoff_already_passed():
    d = wa.decide_close_week(
        now=NOW, active_week=9, completed=games(PAST), upcoming=games(PAST)
    )
    assert d.action == "stop"


def test_close_week_stops_when_a_completed_game_has_no_final():
    done = games(PAST) + [wa.Game(99, PAST, False)]
    d = wa.decide_close_week(
        now=NOW, active_week=9, completed=done, upcoming=games(FUTURE)
    )
    assert d.action == "stop"


def test_close_week_skips_when_completed_week_not_started_yet():
    d = wa.decide_close_week(
        now=NOW,
        active_week=10,
        completed=games(FUTURE, final=False),
        upcoming=games(FUTURE),
    )
    assert d.action == "skip"


def test_close_week_skips_past_final_regular_week():
    d = wa.decide_close_week(
        now=NOW,
        active_week=wa.FINAL_REGULAR_WEEK,
        completed=games(PAST),
        upcoming=games(FUTURE),
    )
    assert d.action == "skip"


FINAL = wa.FINAL_REGULAR_WEEK


def final_decision(**kw):
    args = {
        "now": NOW,
        "active_week": FINAL,
        "completed": games(PAST),
        "upcoming": [],
    }
    return wa.decide_close_week(**{**args, **kw})


def test_week_before_final_still_opens_the_final_week():
    d = wa.decide_close_week(
        now=NOW,
        active_week=FINAL - 1,
        completed=games(PAST),
        upcoming=games(FUTURE),
    )
    assert (d.action, d.completed_week, d.upcoming_week, d.final) == (
        "run",
        FINAL - 1,
        FINAL,
        False,
    )


def test_final_week_complete_runs_the_final_close_with_no_next_week():
    d = final_decision()
    assert (d.action, d.completed_week, d.final) == ("run", FINAL, True)


def test_final_week_incomplete_stops():
    d = final_decision(completed=games(PAST) + [wa.Game(99, PAST, False)])
    assert (d.action, d.final) == ("stop", False)
    assert "no final score" in d.reason


def test_final_week_not_started_skips_and_missing_games_stop():
    assert final_decision(completed=games(FUTURE, final=False)).action == "skip"
    assert final_decision(completed=[]).action == "stop"


def test_final_close_already_live_skips_with_a_clear_reason():
    d = final_decision(final_released=True)
    assert (d.action, d.final) == ("skip", False)
    assert "already live" in d.reason


def test_games_past_the_final_week_constant_skip_instead_of_closing():
    d = final_decision(upcoming=games(FUTURE))
    assert (d.action, d.final) == ("skip", False)
    assert "past the final regular-season week" in d.reason


def test_market_refresh_skips_when_fully_lined_unless_forced():
    kw = dict(now=NOW, active_week=10, upcoming=games(FUTURE), lined=56, total=56)
    assert wa.decide_market_refresh(force=False, **kw).action == "skip"
    assert wa.decide_market_refresh(force=True, **kw).action == "run"


def test_market_refresh_runs_when_partly_lined_and_skips_after_kickoff():
    kw = dict(now=NOW, active_week=10, lined=30, total=56, force=False)
    assert wa.decide_market_refresh(upcoming=games(FUTURE), **kw).action == "run"
    assert wa.decide_market_refresh(upcoming=games(PAST), **kw).action == "skip"


def test_pre_week_cutoff_is_last_capture_plus_five_minutes_whole_seconds():
    last = datetime(2026, 11, 1, 17, 10, 3, 999, tzinfo=UTC)
    assert wa.iso_z(wa.pre_week_cutoff(last)) == "2026-11-01T17:15:03Z"


def test_cutoff_must_precede_first_kickoff_and_follow_earlier_kickoffs():
    with pytest.raises(wa.StopRunError):
        wa.check_cutoff_window(
            FUTURE, upcoming_first_kickoff=FUTURE, completed_last_kickoff=None
        )
    with pytest.raises(wa.StopRunError):
        wa.check_cutoff_window(
            NOW,
            upcoming_first_kickoff=FUTURE,
            completed_last_kickoff=NOW - timedelta(hours=1),
        )
    wa.check_cutoff_window(
        NOW, upcoming_first_kickoff=FUTURE, completed_last_kickoff=PAST
    )


def test_week_10_alone_carries_the_week_8_cutoff_correction():
    assert wa.CUTOFF_CORRECTIONS == {10: ("8:pre=2026-10-20T14:39:00Z",)}


# --------------------------------------------------------- env isolation


@pytest.mark.parametrize("role", ["preview", "odds", "git"])
def test_production_url_only_in_production_step_env(role):
    env = wa.child_env(role, SECRETS, {"PATH": "/bin", "HOME": "/h", "OTHER": "x"})
    assert PROD_URL not in env.values()
    assert "OTHER" not in env


def test_production_env_has_prod_database_and_preview_proof_only():
    env = wa.child_env("production", SECRETS, {"PATH": "/bin"})
    assert env["DATABASE_URL"] == PROD_URL
    assert env["PREVIEW_DATABASE_URL"] == PREVIEW_URL
    assert env["CFB_ARTIFACT_ENV"] == "production"
    assert "CFB_RUNTIME_TARGET_RESOLVED" not in env
    assert "THE_ODDS_API_KEY" not in env and "CFBD_API_KEY" not in env


def test_preview_env_uses_preview_url_for_both_variables():
    env = wa.child_env("preview", SECRETS, {"PATH": "/bin"})
    assert env["DATABASE_URL"] == env["PREVIEW_DATABASE_URL"] == PREVIEW_URL
    assert env["CFB_RUNTIME_TARGET_RESOLVED"] == "preview"
    assert env["CFB_ARTIFACT_ENV"] == "preview"
    assert "THE_ODDS_API_KEY" not in env


def test_odds_key_only_in_odds_step_env():
    assert wa.child_env("odds", SECRETS, {})["THE_ODDS_API_KEY"]
    assert "THE_ODDS_API_KEY" not in wa.child_env("preview", SECRETS, {})


def test_redact_hides_secret_values_and_urls():
    text = f"boom {SECRETS['CFBD_API_KEY']} at postgresql://u:p@h/db"
    out = wa.redact(text, SECRETS)
    assert "cfbd-key" not in out and "u:p@h" not in out


# ------------------------------------------------- controller (fake seams)


class Harness:
    def __init__(self, tmp_path: Path, week_games, *, preview_active=None):
        self.root = tmp_path
        self.calls: list[tuple[list[str], dict]] = []
        self.clock = NOW
        self.week_games = week_games
        self.preview_active = preview_active or "preview-season-2026-old"
        self.preview_week = 9
        self.production_week = 9
        self.manifest_sha = "0" * 64
        self.health_week = 10
        # preview release id -> "same" (active, same bytes) | "other" (other bytes)
        self.existing: dict[str, str] = {}
        self.prepares = 0

    def now(self):
        return self.clock

    def sleep(self, seconds):
        self.clock += timedelta(seconds=seconds)

    def run(self, argv, env, timeout):
        argv = list(map(str, argv))
        self.calls.append((argv, env))
        if "scripts/pipeline/build_season_revision.py" in argv:
            week = argv[argv.index("--week") + 1]
            cutoff = wa.iso_z(self.clock + timedelta(minutes=5))
            (self.root / wa.CONF / f"revision_manifest_w{week}_v1.json").write_text(
                json.dumps({"pre_week_cutoffs": {week: cutoff}})
            )
        if "prepare" in argv:
            self.prepares += 1
            rid = self.release_id()
            out = self.root / wa.SEASON_OUTPUT / rid
            out.mkdir(parents=True, exist_ok=True)
            path = out / "run-manifest.json"
            path.write_text(
                json.dumps(
                    {
                        "release_id": rid,
                        "output_refs": {
                            "serving_projections": {
                                "sha256": "a" * 64,
                                "uri": str(out / "serving-projections.json"),
                            }
                        },
                    }
                )
            )
            os.utime(path, (self.prepares, self.prepares))
        return 0, "abc123\n" if "rev-parse" in argv else ""

    def release_id(self):
        return "season-2026-new" + ("" if self.prepares <= 1 else str(self.prepares))

    def query(self, role, sql, params):
        if "run_manifest_sha256 FROM season_releases" in sql:
            kind = self.existing.get(params[0])
            if kind is None:
                return []
            path = self.root / wa.SEASON_OUTPUT / params[0][len("preview-") :]
            same = hashlib.sha256((path / "run-manifest.json").read_bytes()).hexdigest()
            return [("active", same if kind == "same" else "f" * 64)]
        if role == "preview" and "active_week FROM" in sql:
            return [(self.preview_week,)]
        if "active_week FROM" in sql:
            return [("production-season-2026-old", self.production_week)]
        if "count(*)" in sql and "season_release_games" in sql:
            return [(56, 56)]
        if "revision_manifest_sha256" in sql:
            return [(self.manifest_sha,)]
        if "release_id FROM season_releases" in sql:
            old = (
                self.preview_active
                if role == "preview"
                else "production-season-2026-old"
            )
            return [(old,)]
        raise AssertionError(sql)

    def health(self):
        return {
            "activeRelease": {
                "releaseId": f"production-{self.release_id()}",
                "week": self.health_week,
            }
        }

    def controller(self, mode="close-week", **kw):
        deps = wa.Deps(
            now=self.now,
            sleep=self.sleep,
            run=self.run,
            query=self.query,
            games=lambda week: self.week_games[week],
            health=self.health,
            lined_in_manifest=lambda path, week: 56,
        )
        return wa.Controller(
            mode=mode,
            force=False,
            skip_production=kw.get("skip_production", False),
            accept_cutoff_corrections=kw.get("accept_cutoff_corrections", ()),
            secrets=SECRETS,
            deps=deps,
            base_env={"PATH": "/bin"},
            root=self.root,
        )

    def scripts(self):
        return [a for argv, _ in self.calls for a in argv if a.endswith(".py")]


@pytest.fixture
def harness(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    conf = tmp_path / wa.CONF
    conf.mkdir(parents=True)
    (conf / "revision_manifest_w10_v1.json").write_text(
        json.dumps({"pre_week_cutoffs": {"10": wa.iso_z(NOW - timedelta(hours=1))}})
    )
    return Harness(tmp_path, {9: games(PAST), 10: games(FUTURE)})


def test_resume_skips_capture_and_build_and_starts_at_prepare(harness):
    code = harness.controller().run()
    assert code == 0
    scripts = harness.scripts()
    for absent in (
        "scripts/data/ingest_week.py",
        "scripts/data/fetch_odds_api_market_quotes.py",
        "scripts/pipeline/build_season_revision.py",
        "scripts/pipeline/refresh_score_exceptions.py",
    ):
        assert absent not in scripts
    order = [
        s for s in scripts if s.endswith(("run_season.py", "check_release_parity.py"))
    ]
    assert order == [
        "scripts/pipeline/run_season.py",
        "scripts/pipeline/check_release_parity.py",
        "scripts/pipeline/run_season.py",
        "scripts/pipeline/run_season.py",
    ]
    assert not any(c[0][0] == "git" and c[0][1] == "commit" for c in harness.calls)


def test_production_url_appears_only_in_production_release_step(harness):
    assert harness.controller().run() == 0
    holders = [argv for argv, env in harness.calls if PROD_URL in env.values()]
    assert len(holders) == 1
    assert "release" in holders[0] and "production" in holders[0]


def test_skip_production_leaves_production_untouched(harness):
    assert harness.controller(skip_production=True).run() == 0
    assert not any(PROD_URL in env.values() for _, env in harness.calls)


def _releases(h):
    return [
        a[a.index("--environment") + 1]
        for a, _ in h.calls
        if "release" in a and "--environment" in a
    ]


def _commits(h):
    return [a for a, _ in h.calls if a[:2] == ["git", "commit"]]


def test_preview_active_with_same_id_and_same_bytes_skips_preview_release(harness):
    harness.preview_active = "preview-season-2026-new"
    harness.existing["preview-season-2026-new"] = "same"
    assert harness.controller().run() == 0
    assert _releases(harness) == ["production"]
    assert _commits(harness) == []
    assert "scripts/pipeline/check_release_parity.py" not in harness.scripts()


def test_same_id_with_different_bytes_commits_empty_and_reprepares(harness):
    harness.preview_active = "preview-season-2026-new"
    harness.existing["preview-season-2026-new"] = "other"
    harness.preview_week = 10
    assert harness.controller().run() == 0
    assert harness.prepares == 2
    commits = _commits(harness)
    assert len(commits) == 1 and "--allow-empty" in commits[0]
    assert "retry the Week 10 release" in commits[0][-1]
    assert _releases(harness) == ["preview", "production"]
    parity = next(
        a for a, _ in harness.calls if "scripts/pipeline/check_release_parity.py" in a
    )
    assert parity[parity.index("--mode") + 1] == "market-refresh"
    releases = [a for a, _ in harness.calls if "release" in a and "--run-manifest" in a]
    assert all("season-2026-new2" in a[a.index("--run-manifest") + 1] for a in releases)


def test_second_collision_stops_before_any_release(harness):
    harness.existing.update(
        {"preview-season-2026-new": "other", "preview-season-2026-new2": "other"}
    )
    assert harness.controller().run() == 1
    assert harness.prepares == 2
    assert len(_commits(harness)) == 1
    assert _releases(harness) == []


def test_missing_final_stops_before_any_provider_call(harness):
    harness.week_games[9] = games(PAST) + [wa.Game(99, PAST, False)]
    assert harness.controller().run() == 1
    assert harness.calls == []


def _with_preview_login(harness, login):
    harness.query_orig = harness.query

    def query(role, sql, params):
        if "has_table_privilege" in sql:
            return (
                [(login, True, True)]
                if role == "preview"
                else [("cks_prod_pipeline", True)]
            )
        return harness.query_orig(role, sql, params)

    harness.query = query


def test_plan_only_makes_no_calls_or_writes(harness):
    _with_preview_login(harness, "cks_preview_pipeline")
    assert harness.controller(mode="plan-only").run() == 0
    assert harness.calls == []


def test_plan_only_stops_when_preview_secret_is_not_the_pipeline_login(harness):
    _with_preview_login(harness, "neondb_owner")
    assert harness.controller(mode="plan-only").run() == 1
    assert harness.calls == []


def test_missing_secret_stops(harness):
    c = harness.controller()
    c.secrets = {k: v for k, v in SECRETS.items() if k != "THE_ODDS_API_KEY"}
    assert c.run() == 1
    assert harness.calls == []


def _parity_args(h):
    return next(
        a for a, _ in h.calls if "scripts/pipeline/check_release_parity.py" in a
    )


def test_cutoff_correction_reaches_close_week_parity_only_when_set(harness):
    assert harness.controller(accept_cutoff_corrections=(8,)).run() == 0
    parity = _parity_args(harness)
    assert parity[parity.index("--mode") + 1] == "close-week"
    flag = parity.index("--accept-cutoff-correction")
    assert str(parity[flag + 1]) == "8"


def test_no_cutoff_correction_by_default(harness):
    assert harness.controller().run() == 0
    assert "--accept-cutoff-correction" not in _parity_args(harness)


def test_cutoff_correction_dropped_when_parity_falls_back_to_market_refresh(harness):
    harness.preview_active = "preview-season-2026-new"
    harness.existing["preview-season-2026-new"] = "other"
    harness.preview_week = 10
    assert harness.controller(accept_cutoff_corrections=(8,)).run() == 0
    parity = _parity_args(harness)
    assert parity[parity.index("--mode") + 1] == "market-refresh"
    assert "--accept-cutoff-correction" not in parity


def test_cutoff_correction_cli_refuses_other_modes():
    with pytest.raises(SystemExit):
        wa.main(["--mode", "market-refresh", "--accept-cutoff-correction", "8"])


# ------------------------------------------------- Monday catch-up


MONDAY = datetime(2026, 11, 2, 17, 7, tzinfo=UTC)


def _monday(harness):
    harness.clock = MONDAY
    return harness


def test_market_refresh_catches_up_a_kicked_off_unrolled_final_week(harness):
    c = _monday(harness).controller(mode="market-refresh")
    assert c.run() == 0
    assert c.effective_mode == "close-week" and c.mode == "market-refresh"
    assert c.summary["caught_up"] is True
    assert c.summary["effective_mode"] == "close-week"
    assert c.summary["result"] == "released"
    parity = _parity_args(harness)
    assert parity[parity.index("--mode") + 1] == "close-week"


def test_market_refresh_catch_up_fails_red_when_a_game_is_not_final(harness):
    harness.week_games[9] = games(PAST) + [wa.Game(99, PAST, False)]
    c = _monday(harness).controller(mode="market-refresh")
    assert c.run() == 1
    assert c.summary["caught_up"] is True
    assert "no final score" in c.summary["result"]
    assert harness.calls == []


def test_market_refresh_unchanged_when_active_week_not_started(harness):
    harness.week_games[9] = games(FUTURE, final=False)
    c = _monday(harness).controller(mode="market-refresh")
    assert c.run() == 0
    assert c.effective_mode == "market-refresh"
    assert "caught_up" not in c.summary
    assert c.summary["result"].startswith("skipped: week 9 already fully lined")
    assert harness.calls == []


def test_monday_plan_only_catch_up_checks_window_and_changes_nothing(harness):
    _with_preview_login(harness, "cks_preview_pipeline")
    c = _monday(harness).controller(mode="plan-only")
    assert c.run() == 0
    assert c.effective_mode == "close-week"
    assert c.summary["caught_up"] is True
    assert c.summary["result"] == "planned"
    assert harness.calls == []


def test_plan_only_enforces_the_completed_week_kickoff_window(harness):
    _with_preview_login(harness, "cks_preview_pipeline")
    # Last game kicks off 30 minutes before the cutoff would land.
    harness.week_games[9] = [wa.Game(1, NOW + timedelta(minutes=30), True)]
    c = harness.controller(mode="plan-only")
    assert c.run() == 1
    assert "cutoff" in c.summary["result"]
    assert harness.calls == []


# ------------------------------------------------- final regular-season close


def _final_harness(harness):
    harness.production_week = FINAL
    harness.preview_week = FINAL
    harness.health_week = FINAL
    harness.week_games = {FINAL: games(PAST), FINAL + 1: []}
    return harness


def _scripts_args(h, script):
    return [a for a, _ in h.calls if script in a]


def test_final_close_builds_and_releases_without_a_next_week(harness):
    h = _final_harness(harness)
    c = h.controller()
    assert c.run() == 0
    assert c.summary["result"] == "released"
    assert c.summary["decision"]["final"] is True
    # The build ran (no manifest on disk) but only the completed week was captured.
    captures = _scripts_args(h, "scripts/data/ingest_week.py")
    assert [a[a.index("--week") + 1] for a in captures] == [str(FINAL)]
    assert not _scripts_args(h, "scripts/data/fetch_odds_api_market_quotes.py")
    build = _scripts_args(h, "scripts/pipeline/build_season_revision.py")[0]
    assert build[build.index("--week") + 1] == str(FINAL + 1)
    prepare = next(
        a for a in _scripts_args(h, "scripts/pipeline/run_season.py") if "prepare" in a
    )
    assert prepare[prepare.index("--through-week") + 1] == str(FINAL)
    assert "--next-week" not in prepare
    parity = _parity_args(h)
    assert parity[parity.index("--completed-week") + 1] == str(FINAL)
    assert parity[parity.index("--upcoming-week") + 1] == str(FINAL)
    assert parity[parity.index("--mode") + 1] == "close-week"
    commit = next(a for a, _ in h.calls if a[:2] == ["git", "commit"])
    assert "final regular-season revision manifest" in commit[-1]


def test_final_close_waits_for_the_last_game_to_be_final(harness):
    h = _final_harness(harness)
    h.week_games[FINAL] = games(PAST) + [wa.Game(99, PAST, False)]
    c = h.controller()
    assert c.run() == 1
    assert "no final score" in c.summary["result"]
    assert h.calls == []


def test_final_close_resumes_at_prepare_when_its_manifest_is_committed(harness):
    h = _final_harness(harness)
    (h.root / wa.CONF / f"revision_manifest_w{FINAL + 1}_v1.json").write_text(
        json.dumps({"pre_week_cutoffs": {str(FINAL + 1): wa.iso_z(NOW)}})
    )
    assert h.controller().run() == 0
    assert not _scripts_args(h, "scripts/pipeline/build_season_revision.py")
    prepare = next(
        a for a in _scripts_args(h, "scripts/pipeline/run_season.py") if "prepare" in a
    )
    assert "--next-week" not in prepare


def test_scheduled_runs_skip_cleanly_once_the_final_close_is_live(harness):
    h = _final_harness(harness)
    path = h.root / wa.CONF / f"revision_manifest_w{FINAL + 1}_v1.json"
    path.write_text(json.dumps({"pre_week_cutoffs": {str(FINAL + 1): wa.iso_z(NOW)}}))
    h.manifest_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    sunday = h.controller()
    assert sunday.run() == 0
    assert sunday.summary["result"].startswith("skipped: the final regular-season")
    h.clock = MONDAY
    monday = h.controller(mode="market-refresh")
    assert monday.run() == 0
    assert monday.summary["result"].startswith("skipped: the final regular-season")
    assert h.calls == []


def test_final_week_in_progress_still_runs_market_refresh_not_a_close(harness):
    h = _final_harness(harness)
    h.week_games[FINAL] = games(FUTURE, final=False)
    c = h.controller(mode="market-refresh")
    assert c.run() == 0
    assert c.effective_mode == "market-refresh"


def test_final_close_plan_only_makes_no_calls_or_writes(harness):
    h = _final_harness(harness)
    _with_preview_login(h, "cks_preview_pipeline")
    c = h.controller(mode="plan-only")
    assert c.run() == 0
    assert c.summary["result"] == "planned"
    assert c.summary["planned_cutoffs"]["upcoming_first_kickoff"] is None
    assert h.calls == []
