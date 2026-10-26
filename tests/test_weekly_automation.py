"""Weekly automation controller: decisions, cutoffs, resume and env isolation."""

from __future__ import annotations

import json
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

    def now(self):
        return self.clock

    def sleep(self, seconds):
        self.clock += timedelta(seconds=seconds)

    def run(self, argv, env, timeout):
        argv = list(map(str, argv))
        self.calls.append((argv, env))
        if "prepare" in argv:
            out = self.root / wa.SEASON_OUTPUT / "season-2026-new"
            out.mkdir(parents=True, exist_ok=True)
            (out / "run-manifest.json").write_text(
                json.dumps(
                    {
                        "release_id": "season-2026-new",
                        "output_refs": {
                            "serving_projections": {
                                "sha256": "a" * 64,
                                "uri": str(out / "serving-projections.json"),
                            }
                        },
                    }
                )
            )
        return 0, "abc123\n" if "rev-parse" in argv else ""

    def query(self, role, sql, params):
        if "active_week FROM" in sql:
            return [("production-season-2026-old", 9)]
        if "count(*)" in sql and "season_release_games" in sql:
            return [(56, 56)]
        if "revision_manifest_sha256" in sql:
            return [("0" * 64,)]
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
            "activeRelease": {"releaseId": "production-season-2026-new", "week": 10}
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


def test_already_released_preview_skips_parity_and_preview_release(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    conf = tmp_path / wa.CONF
    conf.mkdir(parents=True)
    (conf / "revision_manifest_w10_v1.json").write_text(
        json.dumps({"pre_week_cutoffs": {"10": wa.iso_z(NOW - timedelta(hours=1))}})
    )
    h = Harness(
        tmp_path,
        {9: games(PAST), 10: games(FUTURE)},
        preview_active="preview-season-2026-new",
    )
    assert h.controller().run() == 0
    assert "scripts/pipeline/check_release_parity.py" not in h.scripts()
    releases = [a for a, _ in h.calls if "release" in a and "--environment" in a]
    assert [a[a.index("--environment") + 1] for a in releases] == ["production"]


def test_missing_final_stops_before_any_provider_call(harness):
    harness.week_games[9] = games(PAST) + [wa.Game(99, PAST, False)]
    assert harness.controller().run() == 1
    assert harness.calls == []


def test_plan_only_makes_no_calls_or_writes(harness, monkeypatch):
    harness.query_orig = harness.query

    def query(role, sql, params):
        if "has_table_privilege" in sql:
            return (
                [("cks_pipeline_login", True, True)][:1]
                if role == "preview"
                else [("cks_prod_pipeline", True)]
            )
        return harness.query_orig(role, sql, params)

    harness.query = query
    assert harness.controller(mode="plan-only").run() == 0
    assert harness.calls == []


def test_missing_secret_stops(harness):
    c = harness.controller()
    c.secrets = {k: v for k, v in SECRETS.items() if k != "THE_ODDS_API_KEY"}
    assert c.run() == 1
    assert harness.calls == []
