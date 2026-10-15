"""One chronological fixed-model computation, shared by replay and refresh."""

from __future__ import annotations

import pandas as pd

from cks_picks_cfb.forecast.live import (
    DEVELOPMENT_SEASONS,
    apply_exported_bridge,
    build_live_application_frame,
)
from cks_picks_cfb.forecast.offsets import build_offsets
from cks_picks_cfb.ratings.possession_intended_update import IntendedUpdate
from cks_picks_cfb.season.grading import grade_predictions
from cks_picks_cfb.season.inputs import SeasonInputs
from cks_picks_cfb.season.manifest import utc


def compute(
    inputs: SeasonInputs,
    revision: dict,
    *,
    through_week: int,
    next_week: int | None,
    as_of: str,
    run_id: str,
    model_sha: str,
    revision_sha: str,
    reconstruct_next_week: bool = False,
) -> dict[str, pd.DataFrame]:
    if through_week < 0 or (next_week is not None and next_week != through_week + 1):
        raise ValueError("next week must immediately follow completed history")
    now = utc(as_of)
    if utc(revision["captured_at"]) > now:
        raise ValueError("revision capture is after preparation as-of")
    schedule = inputs.schedule[
        inputs.schedule.week.le(next_week if next_week is not None else through_week)
    ].copy()
    if next_week is not None and schedule[schedule.week.eq(next_week)].empty:
        raise ValueError("next week has no scheduled games")
    teams = set(inputs.schedule.home_team) | set(inputs.schedule.away_team)
    priors = inputs.priors[inputs.priors.team.isin(teams)].copy()
    engine = IntendedUpdate(
        schedule=inputs.schedule,
        observations=inputs.observations,
        priors=priors,
        historical_terminal=inputs.terminal,
    )
    forecasts, ratings, roles, features_out, offsets_out = [], [], [], [], []
    weeks = list(range(through_week + 1)) + (
        [next_week] if next_week is not None else []
    )
    for week in weeks:
        live = week == next_week and not reconstruct_next_week
        cutoff_text = as_of if live else revision["pre_week_cutoffs"][str(week)]
        cutoff = utc(cutoff_text)
        target = schedule[schedule.week.eq(week)]
        if not live and cutoff >= target.kickoff_utc.min():
            raise ValueError(f"Week {week} cutoff is not before every kickoff")
        earlier = schedule[schedule.week.lt(week)].copy()
        if (
            not earlier.empty
            and (earlier.kickoff_utc + pd.Timedelta(hours=6)).gt(cutoff).any()
        ):
            raise ValueError("prior-week observations unavailable at forecast cutoff")
        if cutoff > now:
            raise ValueError("forecast cutoff exceeds run as-of")
        generation = (
            engine._states(week=week, cutoff=cutoff, game_id=None, teams=engine.teams)
            if week == 0
            else engine.current(post_week=week - 1, cutoff_utc=cutoff_text)
        )
        state = generation.team_states.assign(game_id=0, target_week=week)
        ratings.append(state)
        roles.append(generation.rating_states.assign(target_week=week))
        completed = earlier.assign(
            schedule_completed=True,
            outcome_valid=True,
            forecast_eligible=True,
            measurement_usable=True,
        )
        population = pd.concat(
            [
                inputs.historical_population,
                completed,
                target.assign(
                    schedule_completed=False,
                    outcome_valid=False,
                    forecast_eligible=True,
                    measurement_usable=False,
                ),
            ],
            ignore_index=True,
        )
        allowed_events = inputs.events[inputs.events.game_id.isin(earlier.game_id)]
        offsets = build_offsets(
            population,
            pd.concat([inputs.historical_events, allowed_events], ignore_index=True),
            development_seasons=DEVELOPMENT_SEASONS + (2026,),
            equivalent_games=4,
        ).offsets
        offsets = offsets[offsets.season.eq(2026) & offsets.week.eq(week)].copy()
        # Live omissions use the real run cutoff; replay uses a pre-week cutoff and full slate.
        eligible = target[target.kickoff_utc.gt(cutoff)]
        if eligible.empty:
            if live:
                continue
            raise ValueError("historical slate unexpectedly empty")
        frame, refs = build_live_application_frame(
            schedule, completed, state, offsets, as_of=cutoff_text, target_week=week
        )
        prediction = apply_exported_bridge(
            inputs.bridge,
            frame,
            run_id=run_id,
            model_ref=f"model:{model_sha}",
            source_ref=f"revision:{revision_sha}",
            state_refs=refs,
            timing_class="live" if live else "replay",
        ).predictions
        expected = set(eligible.game_id.astype(int))
        if set(prediction.game_id.astype(int)) != expected or len(
            prediction
        ) != 2 * len(expected):
            raise ValueError("forecast coverage differs from eligible schedule")
        frame["forecast_cutoff"] = cutoff_text
        features_out.append(frame)
        offsets_out.append(offsets)
        forecasts.append(prediction)
    post_teams, post_roles = [], []
    for week in range(through_week + 1):
        post_cutoff = revision.get("post_week_cutoffs", {}).get(
            str(week), revision["pre_week_cutoffs"].get(str(week + 1), as_of)
        )
        if utc(post_cutoff) > now:
            raise ValueError("post-week cutoff exceeds run as-of")
        generation = engine.current(post_week=week, cutoff_utc=post_cutoff)
        post_teams.append(generation.team_states.assign(post_week=week))
        post_roles.append(generation.rating_states.assign(post_week=week))
    predictions = pd.concat(forecasts, ignore_index=True)
    grades = grade_predictions(
        predictions,
        schedule,
        inputs.finals,
        inputs.quotes,
        inputs.historical_lines,
        live_week=None if reconstruct_next_week else next_week,
        as_of=as_of,
    )
    historical_ids = set(
        schedule.loc[schedule.week.le(through_week), "game_id"].astype(int)
    )
    if (
        set(predictions.loc[predictions.week.le(through_week), "game_id"].astype(int))
        != historical_ids
    ):
        raise ValueError("historical forecast population incomplete")
    return {
        "schedule": schedule,
        "finals": inputs.finals,
        "predictions": predictions,
        "grades": grades,
        "ratings": pd.concat(ratings, ignore_index=True),
        "rating_roles": pd.concat(roles, ignore_index=True),
        "current_ratings": pd.concat(post_teams, ignore_index=True),
        "current_rating_roles": pd.concat(post_roles, ignore_index=True),
        "features": pd.concat(features_out, ignore_index=True),
        "offsets": pd.concat(offsets_out, ignore_index=True),
        "measurements": inputs.observations,
        "scoring_events": inputs.events,
    }
