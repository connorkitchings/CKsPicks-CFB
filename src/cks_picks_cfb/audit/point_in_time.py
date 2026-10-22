"""Point-in-time audit of the 2026 record (pure checkers; no I/O).

The public 2026 record is admitted game by game on strict point-in-time inputs. This module
restates the rules independently of every producer (like the rest of ``cks_picks_cfb.audit``)
and checks them over plain frames, so the audit cannot mirror a producer defect into
agreement. Loading the frames from published artifacts is the caller's job.

Every rule is on **event time**. A replay is generated after the games by definition, so
"generated before kickoff" is never the test; the test is that every input was available at
the forecast ``as_of`` and that the ``as_of`` is not after kickoff.

Rules (see ``docs/modeling/record_methodology.md``):

a. rating inputs: each source observation became available (source kickoff + 6 h) at or
   before the forecast ``as_of``, and comes from an earlier week than the target game;
b. rating state: the state's cutoff is at or before the forecast ``as_of``;
c. forecast time: the forecast ``as_of`` is at or before the game's kickoff;
d. quote time: the selected quote was captured before kickoff and no later than the market
   cutoff, or it is on the declared accepted-late list (CFBD, ``betting_lines``);
e. model parameters: the inference bundle was developed without 2026 or 2020, and the run's
   bundle hash is the bundle file's hash;
f. team stats: displayed matchup statistics use ``as_of_week`` no later than the game's week;
g. cutoff coherence: both cutoffs of a run are recorded, and a run that forecasts a whole
   slate was cut off no later than the slate's first kickoff.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import pandas as pd

from cks_picks_cfb.data.data_first_phase2d import signed_payload

SCHEMA = "point_in_time_audit_receipt_v1"
AVAILABILITY_HOURS = 6  # a finished game's data is usable 6 h after its kickoff
RULES = (
    "a_rating_inputs",
    "b_rating_state",
    "c_forecast_time",
    "d_quote_time",
    "e_model_parameters",
    "f_team_stats",
    "g_cutoff_coherence",
)
ACCEPTED_LATE_REASON = "cfbd_pregame_consensus_fetched_post_kickoff"
ACCEPTED_LATE_PROVIDER = "cfbd"
ACCEPTED_LATE_ENTITY = "betting_lines"
ASSUMPTIONS = (
    "CFBD's lines endpoint returns pregame lines only; a CFBD line fetched after kickoff is "
    "the game's pregame consensus line (supported by the CFBD re-fetch comparison, not by "
    "provider documentation)",
    "capture times are fetch times; the audit shows a line was fetched before kickoff, not "
    "when the book posted it",
    "later provider corrections to past weeks were adopted (event-time cutoffs hold)",
)


class AuditInputError(ValueError):
    """The frames given to the audit are malformed (distinct from a rule violation)."""


def _utc(value: Any) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _require(frame: pd.DataFrame, columns: Iterable[str], name: str) -> None:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise AuditInputError(f"{name} lacks columns: {missing}")


def violation(rule: str, game_id: Any, week: Any, detail: str) -> dict[str, Any]:
    return {
        "rule": rule,
        "game_id": None if game_id is None else int(game_id),
        "week": None if week is None else int(week),
        "detail": detail,
    }


def check_rating_inputs(
    games: pd.DataFrame, forecasts: pd.DataFrame, history: pd.DataFrame
) -> list[dict[str, Any]]:
    """Rule a. ``history``: one row per source observation behind a target game's states."""
    _require(games, ("game_id", "week"), "games")
    _require(forecasts, ("game_id", "forecast_as_of"), "forecasts")
    _require(
        history,
        ("game_id", "team", "source_game_id", "source_week", "source_kickoff_utc"),
        "history",
    )
    week = games.set_index("game_id")["week"]
    as_of = forecasts.set_index("game_id")["forecast_as_of"]
    out: list[dict[str, Any]] = []
    for row in history.itertuples(index=False):
        target = int(row.game_id)
        if target not in week.index or target not in as_of.index:
            out.append(
                violation(
                    "a_rating_inputs", target, None, "history for an unknown game"
                )
            )
            continue
        available = _utc(row.source_kickoff_utc) + pd.Timedelta(
            hours=AVAILABILITY_HOURS
        )
        if available > _utc(as_of[target]):
            out.append(
                violation(
                    "a_rating_inputs",
                    target,
                    week[target],
                    f"{row.team}: source game {int(row.source_game_id)} was available "
                    f"{available.isoformat()}, after the forecast as_of "
                    f"{_utc(as_of[target]).isoformat()}",
                )
            )
        if int(row.source_week) >= int(week[target]):
            out.append(
                violation(
                    "a_rating_inputs",
                    target,
                    week[target],
                    f"{row.team}: source game {int(row.source_game_id)} is from week "
                    f"{int(row.source_week)}, not an earlier week",
                )
            )
    return out


def check_rating_state(
    games: pd.DataFrame, forecasts: pd.DataFrame, states: pd.DataFrame
) -> list[dict[str, Any]]:
    """Rule b. ``states``: the rating-state cutoff used for each target game and team."""
    _require(states, ("game_id", "team", "state_cutoff_utc"), "states")
    week = games.set_index("game_id")["week"]
    as_of = forecasts.set_index("game_id")["forecast_as_of"]
    out = []
    for row in states.itertuples(index=False):
        target = int(row.game_id)
        if target in as_of.index and _utc(row.state_cutoff_utc) > _utc(as_of[target]):
            out.append(
                violation(
                    "b_rating_state",
                    target,
                    week.get(target),
                    f"{row.team}: state cutoff {_utc(row.state_cutoff_utc).isoformat()} "
                    f"is after the forecast as_of {_utc(as_of[target]).isoformat()}",
                )
            )
    return out


def check_forecast_time(
    games: pd.DataFrame, forecasts: pd.DataFrame
) -> list[dict[str, Any]]:
    """Rule c. Every forecast ``as_of`` is at or before its game's kickoff."""
    _require(games, ("game_id", "week", "kickoff_utc"), "games")
    merged = games.merge(forecasts, on="game_id", how="left", suffixes=("", "_f"))
    out = []
    for row in merged.itertuples(index=False):
        if pd.isna(row.forecast_as_of):
            out.append(
                violation("c_forecast_time", row.game_id, row.week, "no forecast")
            )
        elif _utc(row.forecast_as_of) > _utc(row.kickoff_utc):
            out.append(
                violation(
                    "c_forecast_time",
                    row.game_id,
                    row.week,
                    f"forecast as_of {_utc(row.forecast_as_of).isoformat()} is after "
                    f"kickoff {_utc(row.kickoff_utc).isoformat()}",
                )
            )
    return out


def check_quote_time(
    games: pd.DataFrame,
    forecasts: pd.DataFrame,
    quotes: pd.DataFrame,
    accepted_late: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rule d. Returns (violations, accepted-late entries that were actually used).

    ``quotes``: one row per selected quote (``game_id``, ``target``, ``quote_id``,
    ``captured_at``, ``provider``, ``entity``).
    """
    _require(
        quotes,
        ("game_id", "target", "quote_id", "captured_at", "provider", "entity"),
        "quotes",
    )
    kickoff = games.set_index("game_id")["kickoff_utc"]
    week = games.set_index("game_id")["week"]
    market = (
        forecasts.set_index("game_id")["market_as_of"]
        if "market_as_of" in forecasts.columns
        else forecasts.set_index("game_id")["forecast_as_of"]
    )
    allowed = {
        (int(item["game_id"]), str(item["target"]), str(item["quote_id"])): dict(item)
        for item in accepted_late
    }
    used: list[dict[str, Any]] = []
    out = []
    for row in quotes.itertuples(index=False):
        game = int(row.game_id)
        if game not in kickoff.index or game not in market.index:
            out.append(
                violation(
                    "d_quote_time",
                    game,
                    None,
                    "quote for a game with no schedule or forecast",
                )
            )
            continue
        captured = _utc(row.captured_at)
        on_time = captured < _utc(kickoff[game]) and captured <= _utc(market[game])
        if on_time:
            continue
        entry = allowed.get((game, str(row.target), str(row.quote_id)))
        reason_ok = (
            entry is not None
            and entry.get("reason") == ACCEPTED_LATE_REASON
            and str(row.provider) == ACCEPTED_LATE_PROVIDER
            and str(row.entity) == ACCEPTED_LATE_ENTITY
            and str(entry.get("provider")) == ACCEPTED_LATE_PROVIDER
            and str(entry.get("entity")) == ACCEPTED_LATE_ENTITY
            and captured >= _utc(kickoff[game])
            and captured <= _utc(market[game])
        )
        if reason_ok:
            used.append(entry)
            continue
        out.append(
            violation(
                "d_quote_time",
                game,
                week[game],
                f"{row.target} quote {row.quote_id} captured {captured.isoformat()} "
                f"(kickoff {_utc(kickoff[game]).isoformat()}, market cutoff "
                f"{_utc(market[game]).isoformat()}) is not on the accepted-late list "
                f"as a CFBD betting_lines quote",
            )
        )
    return out, used


def check_model_parameters(
    bundle: Mapping[str, Any], *, declared_sha256: str, file_sha256: str
) -> list[dict[str, Any]]:
    """Rule e. The bundle never saw 2026 or 2020 and is the file the run names."""
    seasons = bundle.get("development_seasons")
    if not isinstance(seasons, list) or not seasons:
        return [
            violation(
                "e_model_parameters", None, None, "bundle lists no development seasons"
            )
        ]
    out = []
    allowed = set(range(2015, 2020)) | set(range(2021, 2026))
    banned = sorted({int(s) for s in seasons} - allowed)
    if banned:
        out.append(
            violation(
                "e_model_parameters",
                None,
                None,
                f"bundle was developed on seasons {banned}",
            )
        )
    if declared_sha256 != file_sha256:
        out.append(
            violation(
                "e_model_parameters",
                None,
                None,
                "the run's inference bundle hash is not the audited bundle file's hash",
            )
        )
    return out


def check_team_stats(games: pd.DataFrame, usage: pd.DataFrame) -> list[dict[str, Any]]:
    """Rule f. ``usage``: the ``as_of_week`` of the stats shown for each game."""
    _require(usage, ("game_id", "stats_as_of_week"), "usage")
    week = games.set_index("game_id")["week"]
    out = []
    for row in usage.itertuples(index=False):
        game = int(row.game_id)
        if game in week.index and int(row.stats_as_of_week) > int(week[game]):
            out.append(
                violation(
                    "f_team_stats",
                    game,
                    week[game],
                    f"team statistics as_of_week {int(row.stats_as_of_week)} is after the "
                    f"game's week {int(week[game])}",
                )
            )
    return out


def check_cutoff_coherence(
    games: pd.DataFrame, runs: pd.DataFrame
) -> list[dict[str, Any]]:
    """Rule g. ``runs``: one row per run (week, run_id, forecast_as_of, market_as_of,
    display_only). Both cutoffs must be recorded; a run that forecasts a whole slate
    (not display-only or per-game) was cut off no later than the slate's first kickoff.
    Per-game replays bind their cutoffs to the individual rating states; an earlier
    market capture is valid for those forecasts."""
    _require(runs, ("week", "run_id", "forecast_as_of", "market_as_of"), "runs")
    first = games.groupby("week")["kickoff_utc"].apply(
        lambda s: min(_utc(v) for v in s)
    )
    out = []
    for row in runs.itertuples(index=False):
        week = int(row.week)
        if pd.isna(row.forecast_as_of) or pd.isna(row.market_as_of):
            out.append(
                violation(
                    "g_cutoff_coherence",
                    None,
                    week,
                    f"{row.run_id}: a cutoff is not recorded",
                )
            )
            continue
        display_only = bool(getattr(row, "display_only", False))
        if (
            not display_only
            and not bool(getattr(row, "per_game_cutoffs", False))
            and week in first.index
            and _utc(row.forecast_as_of) > first[week]
        ):
            out.append(
                violation(
                    "g_cutoff_coherence",
                    None,
                    week,
                    f"{row.run_id}: forecast as_of {_utc(row.forecast_as_of).isoformat()} "
                    f"is after the slate's first kickoff {first[week].isoformat()}",
                )
            )
        if not bool(getattr(row, "per_game_cutoffs", False)) and _utc(
            row.market_as_of
        ) < _utc(row.forecast_as_of):
            out.append(
                violation(
                    "g_cutoff_coherence",
                    None,
                    week,
                    f"{row.run_id}: market cutoff is before the forecast as_of",
                )
            )
    return out


def run_audit(
    *,
    games: pd.DataFrame,
    forecasts: pd.DataFrame,
    runs: pd.DataFrame,
    history: pd.DataFrame,
    states: pd.DataFrame,
    quotes: pd.DataFrame,
    accepted_late: Sequence[Mapping[str, Any]],
    bundle: Mapping[str, Any],
    declared_bundle_sha256: str,
    bundle_file_sha256: str,
    team_stats_usage: pd.DataFrame,
    environment: str,
    inputs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run every rule and return a signed receipt (``state`` is ``passed`` or ``failed``)."""
    _require(games, ("game_id", "week", "kickoff_utc"), "games")
    _require(forecasts, ("game_id", "run_id", "forecast_as_of"), "forecasts")
    violations: list[dict[str, Any]] = []
    violations += check_rating_inputs(games, forecasts, history)
    violations += check_rating_state(games, forecasts, states)
    violations += check_forecast_time(games, forecasts)
    quote_violations, used_late = check_quote_time(
        games, forecasts, quotes, accepted_late
    )
    violations += quote_violations
    violations += check_model_parameters(
        bundle, declared_sha256=declared_bundle_sha256, file_sha256=bundle_file_sha256
    )
    violations += check_team_stats(games, team_stats_usage)
    violations += check_cutoff_coherence(games, runs)

    used_keys = {
        (int(u["game_id"]), str(u["target"]), str(u["quote_id"])) for u in used_late
    }
    unused = [
        dict(item)
        for item in accepted_late
        if (int(item["game_id"]), str(item["target"]), str(item["quote_id"]))
        not in used_keys
    ]
    bad_games = {v["game_id"] for v in violations if v["game_id"] is not None}
    rows = []
    for g in games.sort_values("game_id").itertuples(index=False):
        f = forecasts.loc[forecasts["game_id"] == g.game_id]
        rows.append(
            {
                "game_id": int(g.game_id),
                "week": int(g.week),
                "kickoff_utc": _utc(g.kickoff_utc).isoformat(),
                "run_id": None if f.empty else str(f.iloc[0]["run_id"]),
                "forecast_as_of": None
                if f.empty or pd.isna(f.iloc[0]["forecast_as_of"])
                else _utc(f.iloc[0]["forecast_as_of"]).isoformat(),
                "passed": int(g.game_id) not in bad_games,
            }
        )
    counts = {rule: sum(1 for v in violations if v["rule"] == rule) for rule in RULES}
    body = {
        "schema_version": SCHEMA,
        "season": 2026,
        "environment": environment,
        "state": "failed" if violations else "passed",
        "weeks": sorted({int(w) for w in games["week"]}),
        "runs": {
            str(int(r.week)): str(r.run_id)
            for r in runs.sort_values("week").itertuples()
        },
        "games_checked": int(len(games)),
        "violation_counts": counts,
        "violations": violations,
        "accepted_late_used": used_late,
        "accepted_late_unused": unused,
        "assumptions": list(ASSUMPTIONS),
        "rules": list(RULES),
        "inputs": dict(inputs or {}),
        "games": rows,
    }
    return signed_payload(body)
