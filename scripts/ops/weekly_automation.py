#!/usr/bin/env python3
"""Unattended weekly season update (GitHub Actions controller).

Mirrors the manual path in docs/ops/weekly_runbook.md (``make season-close-week``,
``season-market-revision``, ``season-prepare``, ``season-release``) without zsh or
the macOS Keychain: credentials come from the environment and every child process
gets an explicitly built environment (no inheritance across roles).

Modes
  close-week      Sunday: capture lines, build the next week's revision, refresh
                  score exceptions, commit+push to ``dev``, prepare, check parity,
                  release Preview then Production, probe live health.
  market-refresh  Monday: refresh the active week's lines only, same release tail.
  plan-only       Week detection, credential presence, read-only role checks and
                  cutoff arithmetic. No captures, no writes.

Exit codes: 0 done or nothing to do, 1 stopped (a human is needed), 2 bad setup.
The repository is public: this module prints only IDs, hashes and counts. Child
output is shown (redacted, tail only) only when a step fails.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

SEASON = 2026
FINAL_REGULAR_WEEK = 15
CONF = Path(f"conf/season/{SEASON}")
EXCEPTIONS_FILE = CONF / "score_reconciliation_exceptions.json"
MODEL_MANIFEST = CONF / "model_manifest_v1.json"
SEASON_OUTPUT = Path(f"artifacts/season/{SEASON}/preview")
RECEIPT_DIR = Path(f"artifacts/season/{SEASON}/weekly-automation")
HEALTH_URL = "https://c-ks-picks-cfb.vercel.app/api/health"
CUTOFF_MARGIN = timedelta(minutes=5)
EARLIER_KICKOFF_MARGIN = timedelta(hours=6)
MAX_CUTOFF_WAIT = timedelta(minutes=20)
HEALTH_TIMEOUT_S = 600
HEALTH_POLL_S = 20

# Explicit stale-cutoff corrections for one specific build. The Week 9 manifests
# carry pre_week_cutoffs["8"]=2026-10-20T18:00:00Z while the certified w8_v3 has
# 14:39:00Z (no numeric effect; last Week 8 capture was 14:33:30Z). The Week 10
# build corrects it; no other week passes a correction.
CUTOFF_CORRECTIONS: dict[int, tuple[str, ...]] = {
    10: ("8:pre=2026-10-20T14:39:00Z",),
}

PREVIEW_R2 = (
    "CFB_R2_PREVIEW_BUCKET",
    "CFB_R2_PREVIEW_ACCOUNT_ID",
    "CFB_R2_PREVIEW_ACCESS_KEY",
    "CFB_R2_PREVIEW_SECRET_KEY",
)
REQUIRED_SECRETS = (
    "CFBD_API_KEY",
    "PREVIEW_DATABASE_URL",
    "PRODUCTION_PIPELINE_DATABASE_URL",
    *PREVIEW_R2,
)
PASSTHROUGH = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "TMPDIR",
    "UV_CACHE_DIR",
    "UV_PROJECT_ENVIRONMENT",
    "VIRTUAL_ENV",
    "XDG_CACHE_HOME",
    "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE",
)


class StopRunError(Exception):
    """A human is needed; the run ends with a failing exit code."""


class SkipRunError(Exception):
    """Nothing to do; the run ends successfully."""


# ---------------------------------------------------------------- pure logic


@dataclass(frozen=True)
class Game:
    game_id: int
    start: datetime | None
    final: bool


@dataclass(frozen=True)
class Decision:
    action: str  # run | skip | stop
    reason: str
    completed_week: int
    upcoming_week: int


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_z(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def first_kickoff(games: Sequence[Game]) -> datetime | None:
    starts = [g.start for g in games if g.start]
    return min(starts) if starts else None


def last_kickoff(games: Sequence[Game]) -> datetime | None:
    starts = [g.start for g in games if g.start]
    return max(starts) if starts else None


def decide_close_week(
    *,
    now: datetime,
    active_week: int,
    completed: Sequence[Game],
    upcoming: Sequence[Game],
    final_week: int = FINAL_REGULAR_WEEK,
) -> Decision:
    done, nxt = active_week, active_week + 1

    def d(action: str, reason: str) -> Decision:
        return Decision(action, reason, done, nxt)

    if nxt > final_week:
        return d("skip", f"week {nxt} is past the final regular-season week")
    if not completed:
        return d("stop", f"no games found for completed week {done}")
    missing = [g for g in completed if not g.final]
    if missing:
        kick = first_kickoff(completed)
        if kick is not None and kick > now:
            return d("skip", f"week {done} has not started (already rolled over)")
        return d("stop", f"{len(missing)} week {done} game(s) have no final score")
    if not upcoming:
        return d("skip", f"week {nxt} has no scheduled games")
    kick = first_kickoff(upcoming)
    if kick is None:
        return d("stop", f"week {nxt} has no kickoff times")
    if kick <= now:
        return d("stop", f"week {nxt} first kickoff {iso_z(kick)} already passed")
    return d("run", "completed week final; upcoming week not started")


def decide_market_refresh(
    *,
    now: datetime,
    active_week: int,
    upcoming: Sequence[Game],
    lined: int,
    total: int,
    force: bool,
) -> Decision:
    def d(action: str, reason: str) -> Decision:
        return Decision(action, reason, active_week - 1, active_week)

    kick = first_kickoff(upcoming)
    if kick is None:
        return d("skip", f"week {active_week} has no scheduled games")
    if kick <= now:
        return d("skip", f"week {active_week} first kickoff already passed")
    if total and lined >= total and not force:
        return d("skip", f"week {active_week} already fully lined ({lined}/{total})")
    return d("run", f"week {active_week} lined {lined}/{total}")


def pre_week_cutoff(last_capture_end: datetime) -> datetime:
    """Last capture plus five minutes, truncated to whole seconds."""
    return (last_capture_end + CUTOFF_MARGIN).replace(microsecond=0)


def check_cutoff_window(
    cutoff: datetime,
    *,
    upcoming_first_kickoff: datetime,
    completed_last_kickoff: datetime | None,
) -> None:
    if cutoff >= upcoming_first_kickoff:
        raise StopRunError(f"cutoff {iso_z(cutoff)} is not before the first kickoff")
    if (
        completed_last_kickoff is not None
        and cutoff < completed_last_kickoff + EARLIER_KICKOFF_MARGIN
    ):
        raise StopRunError(
            f"cutoff {iso_z(cutoff)} is under 6h after the last earlier kickoff"
        )


def manifest_versions(conf: Path, week: int) -> dict[int, Path]:
    pattern = re.compile(rf"revision_manifest_w{week}_v(\d+)\.json")
    found = {}
    for path in conf.glob(f"revision_manifest_w{week}_v*.json"):
        match = pattern.fullmatch(path.name)
        if match:
            found[int(match.group(1))] = path
    return found


def lined_improved(new_lined: int, active_lined: int) -> bool:
    return new_lined > active_lined


def child_env(
    role: str, secrets: dict[str, str], base: dict[str, str]
) -> dict[str, str]:
    """Environment for one subprocess, built from scratch.

    ``role``: ``preview`` (capture, build, prepare, Preview release, parity),
    ``odds`` (preview plus the Odds API key), ``production`` (Production release),
    ``git`` (no credentials).
    """
    env = {k: base[k] for k in PASSTHROUGH if k in base}
    if role == "git":
        return env
    env["PYTHONPATH"] = "src:."
    env["CFB_STORAGE_BACKEND"] = "r2"
    preview_url = secrets["PREVIEW_DATABASE_URL"]
    if role in ("preview", "odds"):
        env.update({k: secrets[k] for k in PREVIEW_R2})
        env["CFBD_API_KEY"] = secrets["CFBD_API_KEY"]
        env["CFB_ARTIFACT_ENV"] = "preview"
        env["PREVIEW_DATABASE_URL"] = preview_url
        env["DATABASE_URL"] = preview_url
        env["CFB_RUNTIME_TARGET_RESOLVED"] = "preview"
        if role == "odds":
            env["THE_ODDS_API_KEY"] = secrets["THE_ODDS_API_KEY"]
        return env
    if role == "production":
        # Same bucket under both prefixes (runbook, Environments); the release
        # reads only local files, this just satisfies storage resolution.
        for key in PREVIEW_R2:
            env[key] = secrets[key]
            env[key.replace("CFB_R2_PREVIEW_", "CFB_R2_")] = secrets[key]
        env["CFB_ARTIFACT_ENV"] = "production"
        env["DATABASE_URL"] = secrets["PRODUCTION_PIPELINE_DATABASE_URL"]
        env["PREVIEW_DATABASE_URL"] = preview_url
        return env
    raise ValueError(f"unknown role {role}")


def redact(text: str, secrets: dict[str, str]) -> str:
    for value in secrets.values():
        if value and len(value) >= 6:
            text = text.replace(value, "***")
    return re.sub(r"postgres(ql)?://\S+", "postgres://***", text)


# --------------------------------------------------------------------- seams


@dataclass
class Deps:
    """Everything touching the clock, subprocesses, databases and the network."""

    now: Callable[[], datetime]
    sleep: Callable[[float], None]
    run: Callable[[Sequence[str], dict[str, str], int], tuple[int, str]]
    query: Callable[[str, str, tuple], list[tuple]]  # (role, sql, params)
    games: Callable[[int], list[Game]]
    health: Callable[[], dict | None]
    lined_in_manifest: Callable[[Path, int], int]


def default_deps(secrets: dict[str, str]) -> Deps:
    def run(argv, env, timeout):
        proc = subprocess.run(
            list(argv),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout

    def query(role, sql, params):
        import psycopg

        url = secrets[
            "PRODUCTION_PIPELINE_DATABASE_URL"
            if role == "production"
            else "PREVIEW_DATABASE_URL"
        ]
        with psycopg.connect(url, options="-c default_transaction_read_only=on") as c:
            return [tuple(r) for r in c.execute(sql, params).fetchall()]

    def games(week):
        import cfbd

        from cks_picks_cfb.data.base import BaseIngester

        api = cfbd.GamesApi(
            cfbd.ApiClient(cfbd.Configuration(access_token=secrets["CFBD_API_KEY"]))
        )
        out = []
        for g in api.get_games(
            year=SEASON, week=week, season_type="regular", classification="fbs"
        ):
            r = BaseIngester.provider_value(g)
            start = r.get("startDate", r.get("start_date"))
            if isinstance(start, str):
                start = parse_z(start)
            pts = (
                r.get("homePoints", r.get("home_points")),
                r.get("awayPoints", r.get("away_points")),
            )
            final = bool(r.get("completed")) and None not in pts
            out.append(Game(int(r["id"]), start, final))
        return out

    def health():
        import requests

        try:
            resp = requests.get(HEALTH_URL, timeout=15)
            return resp.json() if resp.status_code == 200 else None
        except (requests.RequestException, ValueError):
            return None

    def lined_in_manifest(manifest_path, week):
        from cks_picks_cfb.data.storage import get_storage
        from cks_picks_cfb.season.inputs import frame

        manifest = json.loads(manifest_path.read_text())
        store = get_storage(environment="preview")
        schedule = frame(store, manifest["inputs"]["schedule"])
        quotes = frame(store, manifest["inputs"]["market_quotes"])
        ids = set(schedule.loc[schedule.week == week, "game_id"])
        q = quotes[quotes.game_id.isin(ids)]
        both = q.groupby("game_id").agg(s=("spread", "count"), t=("total", "count"))
        return int(((both.s > 0) & (both.t > 0)).sum())

    return Deps(
        now=lambda: datetime.now(timezone.utc),
        sleep=time.sleep,
        run=run,
        query=query,
        games=games,
        health=health,
        lined_in_manifest=lined_in_manifest,
    )


# ---------------------------------------------------------------- controller


@dataclass
class Controller:
    mode: str
    force: bool
    skip_production: bool
    secrets: dict[str, str]
    deps: Deps
    base_env: dict[str, str]
    root: Path = Path(".")
    summary: dict[str, Any] = field(default_factory=dict)

    # -- plumbing
    def log(self, message: str) -> None:
        print(message, flush=True)

    def conf(self) -> Path:
        return self.root / CONF

    def step(
        self, name: str, argv: Sequence[str], role: str, timeout: int = 1800
    ) -> str:
        env = child_env(role, self.secrets, self.base_env)
        started = self.deps.now()
        code, output = self.deps.run(argv, env, timeout)
        seconds = int((self.deps.now() - started).total_seconds())
        self.summary.setdefault("steps", []).append(
            {"step": name, "exit": code, "seconds": seconds}
        )
        if code != 0:
            tail = "\n".join(redact(output, self.secrets).splitlines()[-40:])
            self.log(f"step {name} failed (exit {code}); output tail:\n{tail}")
            raise StopRunError(f"step {name} failed")
        self.log(f"step {name} ok ({seconds}s)")
        return output

    def py(self, script: str, *args: str) -> list[str]:
        return ["uv", "run", "--frozen", "python", script, *map(str, args)]

    def git(self, *args: str) -> str:
        return self.step(f"git {args[0]}", ["git", *args], "git", timeout=300)

    # -- database facts
    def active_production(self) -> tuple[str, int]:
        rows = self.deps.query(
            "production",
            "SELECT release_id, active_week FROM season_releases "
            "WHERE environment = 'production' AND season = %s AND status = 'active'",
            (SEASON,),
        )
        if len(rows) != 1:
            raise StopRunError(
                f"expected one active Production release, found {len(rows)}"
            )
        return rows[0][0], int(rows[0][1])

    def active_release(self, role: str) -> str | None:
        env = "production" if role == "production" else "preview"
        rows = self.deps.query(
            role,
            "SELECT release_id FROM season_releases "
            "WHERE environment = %s AND season = %s AND status = 'active'",
            (env, SEASON),
        )
        return rows[0][0] if rows else None

    def production_coverage(self, release_id: str, week: int) -> tuple[int, int]:
        rows = self.deps.query(
            "production",
            "SELECT count(*), count(*) FILTER (WHERE home_team_spread_line IS NOT NULL "
            "AND total_line IS NOT NULL) FROM season_release_games "
            "WHERE release_id = %s AND week = %s",
            (release_id, week),
        )
        return int(rows[0][1]), int(rows[0][0])

    def active_manifest_sha(self, release_id: str) -> str | None:
        rows = self.deps.query(
            "production",
            "SELECT revision_manifest_sha256 FROM season_releases WHERE release_id = %s",
            (release_id,),
        )
        return rows[0][0] if rows else None

    # -- checks
    def check_secrets(self, need_odds: bool) -> dict[str, bool]:
        names = (*REQUIRED_SECRETS, "THE_ODDS_API_KEY")
        present = {n: bool(self.secrets.get(n)) for n in names}
        missing = [n for n in REQUIRED_SECRETS if not present[n]]
        if need_odds and not present["THE_ODDS_API_KEY"]:
            missing.append("THE_ODDS_API_KEY")
        self.summary["secrets_present"] = present
        if missing:
            raise StopRunError("missing credentials: " + ", ".join(missing))
        return present

    def check_roles(self) -> None:
        prev = self.deps.query(
            "preview",
            "SELECT current_user, has_table_privilege(current_user, "
            "'catalog.source_captures', 'INSERT'), has_table_privilege(current_user, "
            "'season_releases', 'INSERT')",
            (),
        )[0]
        prod = self.deps.query(
            "production",
            "SELECT current_user, has_table_privilege(current_user, "
            "'season_releases', 'SELECT')",
            (),
        )[0]
        self.summary["roles"] = {
            "preview_login": prev[0],
            "preview_source_captures_insert": bool(prev[1]),
            "preview_season_releases_insert": bool(prev[2]),
            "production_login": prod[0],
            "production_season_releases_select": bool(prod[1]),
        }
        if not (prev[1] and prev[2] and prod[1]):
            raise StopRunError("database role grants are insufficient")

    # -- entry
    def run(self) -> int:
        try:
            self.summary.update({"mode": self.mode, "force": self.force})
            started = self.deps.now()
            self.summary["started_at"] = iso_z(started)
            self.check_secrets(need_odds=self.mode != "plan-only")
            release_id, active_week = self.active_production()
            self.summary.update(
                {"active_production_release": release_id, "active_week": active_week}
            )
            decision = self.detect(started, release_id, active_week)
            self.summary["decision"] = decision.__dict__
            self.log(f"decision: {decision.action} - {decision.reason}")
            if decision.action == "skip":
                raise SkipRunError(decision.reason)
            if decision.action == "stop":
                raise StopRunError(decision.reason)
            if self.mode == "plan-only":
                self.check_roles()
                self.plan_cutoffs(decision)
                self.summary["result"] = "planned"
                return 0
            if self.mode == "close-week":
                self.close_week(decision, started)
            else:
                self.market_refresh(decision, release_id)
            self.summary["result"] = "released"
            return 0
        except SkipRunError as exc:
            self.summary["result"] = f"skipped: {exc}"
            return 0
        except StopRunError as exc:
            self.summary["result"] = f"stopped: {exc}"
            self.log(f"STOP: {exc}")
            return 1
        finally:
            self.write_receipt()

    def detect(self, now: datetime, release_id: str, active_week: int) -> Decision:
        if self.mode == "market-refresh" or (
            self.mode == "plan-only" and now.weekday() == 0
        ):
            upcoming = self.deps.games(active_week)
            lined, total = self.production_coverage(release_id, active_week)
            self.summary["coverage"] = {"lined": lined, "total": total}
            return decide_market_refresh(
                now=now,
                active_week=active_week,
                upcoming=upcoming,
                lined=lined,
                total=total,
                force=self.force,
            )
        completed = self.deps.games(active_week)
        upcoming = self.deps.games(active_week + 1)
        self.summary["games"] = {
            "completed": len(completed),
            "completed_final": sum(g.final for g in completed),
            "upcoming": len(upcoming),
        }
        return decide_close_week(
            now=now, active_week=active_week, completed=completed, upcoming=upcoming
        )

    def plan_cutoffs(self, decision: Decision) -> None:
        now = self.deps.now()
        upcoming = self.deps.games(decision.upcoming_week)
        completed = self.deps.games(decision.completed_week)
        cutoff = pre_week_cutoff(now)
        check_cutoff_window(
            cutoff,
            upcoming_first_kickoff=first_kickoff(upcoming),
            completed_last_kickoff=last_kickoff(completed)
            if self.mode == "close-week"
            else None,
        )
        self.summary["planned_cutoffs"] = {
            "post_week": iso_z(now),
            "pre_week_if_captured_now": iso_z(cutoff),
            "upcoming_first_kickoff": iso_z(first_kickoff(upcoming)),
        }

    # -- close-week
    def close_week(self, decision: Decision, started: datetime) -> None:
        done, nxt = decision.completed_week, decision.upcoming_week
        manifest = self.conf() / f"revision_manifest_w{nxt}_v1.json"
        if manifest.exists():
            self.log(f"manifest for week {nxt} exists on dev; resuming at prepare")
            self.summary["resumed"] = True
        else:
            self.build_close_week(done, nxt, started, manifest)
        self.prepare_and_release(manifest, nxt, "close-week", done)

    def capture(self, week: int, odds: bool = True) -> datetime:
        self.step(
            f"capture cfbd lines w{week}",
            self.py(
                "scripts/data/ingest_week.py",
                "--year",
                SEASON,
                "--week",
                week,
                "--entities",
                "betting_lines",
            ),
            "preview",
        )
        end = self.deps.now()
        return end

    def capture_odds(self, week: int) -> datetime:
        self.step(
            f"capture odds quotes w{week}",
            self.py(
                "scripts/data/fetch_odds_api_market_quotes.py",
                "--year",
                SEASON,
                "--week",
                week,
                "--confirm",
            ),
            "odds",
        )
        return self.deps.now()

    def build_close_week(
        self, done: int, nxt: int, started: datetime, manifest: Path
    ) -> None:
        self.capture(done)
        self.capture(nxt)
        last = self.capture_odds(nxt)
        cutoff = pre_week_cutoff(last)
        check_cutoff_window(
            cutoff,
            upcoming_first_kickoff=first_kickoff(self.deps.games(nxt)),
            completed_last_kickoff=last_kickoff(self.deps.games(done)),
        )
        post = iso_z(started)
        self.summary["cutoffs"] = {"post_week": post, "pre_week": iso_z(cutoff)}
        run_id = f"w{nxt}-revision-{started.strftime('%Y%m%d%H%M')}"
        build = self.py(
            "scripts/pipeline/build_season_revision.py",
            "--season", SEASON, "--week", nxt, "--environment", "preview",
            "--incremental", "--as-of", post, "--pre-week-cutoff", iso_z(cutoff),
            "--pipeline-run-id", run_id,
        )  # fmt: skip
        for correction in CUTOFF_CORRECTIONS.get(nxt, ()):
            build += ["--correct-cutoff", correction]
        self.step("build revision", build, "preview", timeout=3000)
        report = self.receipts() / "score-exceptions.json"
        self.step(
            "refresh score exceptions",
            self.py(
                "scripts/pipeline/refresh_score_exceptions.py",
                "--season", SEASON, "--environment", "preview",
                "--revision-manifest", manifest, "--exceptions", EXCEPTIONS_FILE,
                "--completed-week", done, "--report", report,
            ),
            "preview",
        )  # fmt: skip
        self.commit_push(
            [manifest, EXCEPTIONS_FILE],
            f"chore(season): add the Week {nxt} revision manifest",
        )

    def commit_push(self, paths: list[Path], message: str) -> None:
        rel = [str(p) for p in paths]
        self.git("add", "--", *rel)
        self.git("commit", "-m", message)
        self.git("push", "origin", "HEAD:dev")
        if self.git("status", "--porcelain").strip():
            raise StopRunError("working tree is dirty after commit")
        self.summary["commit"] = self.git("rev-parse", "HEAD").strip()

    def receipts(self) -> Path:
        path = self.root / RECEIPT_DIR
        path.mkdir(parents=True, exist_ok=True)
        return path

    # -- market refresh
    def market_refresh(self, decision: Decision, release_id: str) -> None:
        week = decision.upcoming_week
        versions = manifest_versions(self.conf(), week)
        if not versions:
            raise StopRunError(f"no revision manifest for week {week} on dev")
        top = max(versions)
        top_path = versions[top]
        live_sha = self.active_manifest_sha(release_id)
        import hashlib

        top_sha = hashlib.sha256(top_path.read_bytes()).hexdigest()
        if live_sha != top_sha:
            self.log(f"{top_path.name} is committed but not live; resuming at prepare")
            self.summary["resumed"] = True
            self.prepare_and_release(top_path, week, "market-refresh", week - 1)
            return
        self.capture(week)
        last = self.capture_odds(week)
        cutoff = pre_week_cutoff(last)
        check_cutoff_window(
            cutoff,
            upcoming_first_kickoff=first_kickoff(self.deps.games(week)),
            completed_last_kickoff=None,
        )
        new_path = self.conf() / f"revision_manifest_w{week}_v{top + 1}.json"
        self.step(
            "build market revision",
            self.py(
                "-m", "scripts.pipeline.build_market_revision",
                "--from-manifest", top_path, "--to-manifest", new_path,
                "--revision-id", f"season-{SEASON}-w{week}-preview-r{top + 1}",
                "--cutoff", iso_z(cutoff), "--target-week", week,
            ),
            "preview",
        )  # fmt: skip
        active_lined, _ = self.production_coverage(release_id, week)
        new_lined = self.deps.lined_in_manifest(new_path, week)
        self.summary["market_coverage"] = {"active": active_lined, "new": new_lined}
        if not lined_improved(new_lined, active_lined):
            new_path.unlink(missing_ok=True)
            raise SkipRunError(
                f"line coverage did not improve ({new_lined} vs {active_lined})"
            )
        self.commit_push(
            [new_path], f"chore(season): add the Week {week} market-refresh revision"
        )
        self.prepare_and_release(new_path, week, "market-refresh", week - 1)

    # -- shared tail
    def prepare_and_release(
        self, manifest: Path, nxt: int, parity_mode: str, done: int
    ) -> None:
        revision = json.loads(manifest.read_text())
        as_of = parse_z(revision["pre_week_cutoffs"][str(nxt)])
        wait = as_of - self.deps.now()
        if wait > MAX_CUTOFF_WAIT:
            raise StopRunError(
                f"cutoff {iso_z(as_of)} is too far in the future to wait"
            )
        if wait.total_seconds() > 0:
            self.deps.sleep(wait.total_seconds() + 5)
        self.step(
            "prepare candidate",
            self.py(
                "scripts/pipeline/run_season.py", "prepare",
                "--model-manifest", MODEL_MANIFEST,
                "--revision-manifest", manifest,
                "--through-week", nxt - 1, "--next-week", nxt,
                "--as-of", iso_z(as_of), "--output", SEASON_OUTPUT,
                "--environment", "preview",
            ),
            "preview",
            timeout=2400,
        )  # fmt: skip
        candidate = self.read_candidate()
        self.summary["candidate"] = candidate
        release_id, sha = candidate["release_id"], candidate["projection_sha256"]
        run_manifest = candidate["run_manifest"]
        preview_active = self.active_release("preview")
        production_active = self.active_release("production")
        if production_active == f"production-{release_id}":
            raise SkipRunError("candidate is already active in Production")
        if preview_active != f"preview-{release_id}":
            self.step(
                "check release parity",
                self.py(
                    "scripts/pipeline/check_release_parity.py",
                    "--candidate-dir", Path(candidate["candidate_dir"]),
                    "--mode", parity_mode, "--completed-week", done,
                    "--upcoming-week", nxt,
                    "--report", self.receipts() / "parity.json",
                ),
                "preview",
            )  # fmt: skip
            self.step(
                "release preview",
                self.release_args("preview", preview_active, run_manifest, sha),
                "preview",
            )
        if self.skip_production:
            raise SkipRunError(
                "skip_production set; Preview released, Production untouched"
            )
        self.step(
            "release production",
            self.release_args("production", production_active, run_manifest, sha),
            "production",
        )
        self.probe_health(release_id, nxt)

    def release_args(
        self, environment: str, expected: str | None, run_manifest: str, sha: str
    ) -> list[str]:
        previous = (
            ["--expected-previous-release-id", expected] if expected else ["--initial"]
        )
        return self.py(
            "scripts/pipeline/run_season.py", "release",
            "--environment", environment, *previous,
            "--run-manifest", run_manifest, "--projection-payload-sha256", sha,
        )  # fmt: skip

    def read_candidate(self) -> dict[str, str]:
        root = self.root / SEASON_OUTPUT
        manifests = sorted(
            root.glob("*/run-manifest.json"), key=lambda p: p.stat().st_mtime
        )
        if not manifests:
            raise StopRunError("prepare produced no run manifest")
        path = manifests[-1]
        data = json.loads(path.read_text())
        ref = data["output_refs"]["serving_projections"]
        (self.receipts() / "run-manifest.json").write_text(path.read_text())
        return {
            "release_id": data["release_id"],
            "projection_sha256": ref["sha256"],
            "run_manifest": str(path),
            "candidate_dir": str(Path(ref["uri"]).parent),
        }

    def probe_health(self, release_id: str, week: int) -> None:
        deadline = self.deps.now() + timedelta(seconds=HEALTH_TIMEOUT_S)
        while self.deps.now() < deadline:
            body = self.deps.health() or {}
            active = body.get("activeRelease") or {}
            if str(active.get("releaseId", "")).endswith(release_id):
                self.summary["live_health"] = {
                    "release_id": active.get("releaseId"),
                    "week": active.get("week"),
                    "coverage": body.get("coverage"),
                }
                if active.get("week") != week:
                    raise StopRunError(
                        "live health reports the release at an unexpected week"
                    )
                return
            self.deps.sleep(HEALTH_POLL_S)
        raise StopRunError("live health did not report the new release in time")

    # -- receipts
    def write_receipt(self) -> None:
        try:
            out = self.receipts()
            (out / "summary.json").write_text(
                json.dumps(self.summary, indent=2, sort_keys=True, default=str) + "\n"
            )
            lines = [f"## Weekly season update ({self.mode})", ""]
            lines.append(f"Result: `{self.summary.get('result', 'unknown')}`")
            for key in (
                "active_week",
                "decision",
                "commit",
                "candidate",
                "live_health",
            ):
                if key in self.summary:
                    lines.append(
                        f"- {key}: `{json.dumps(self.summary[key], default=str)}`"
                    )
            (out / "summary.md").write_text("\n".join(lines) + "\n")
        except OSError as exc:  # receipts must never mask the real result
            print(f"could not write receipt: {exc}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("close-week", "market-refresh", "plan-only"), required=True
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-production", action="store_true")
    args = parser.parse_args(argv)
    secrets = {
        k: os.environ[k]
        for k in (*REQUIRED_SECRETS, "THE_ODDS_API_KEY")
        if os.environ.get(k)
    }
    controller = Controller(
        mode=args.mode,
        force=args.force,
        skip_production=args.skip_production,
        secrets=secrets,
        deps=default_deps(secrets),
        base_env=dict(os.environ),
    )
    return controller.run()


if __name__ == "__main__":
    raise SystemExit(main())
