"""Retained pre-kickoff quotes precede explicitly retrospective CFBD lines."""

from __future__ import annotations

import json
from dataclasses import asdict

import numpy as np
import pandas as pd

from cks_picks_cfb.data.lake import MarketQuote, select_market_snapshot
from cks_picks_cfb.models.market_grading import (
    _side_price,
    _sort_key,
    pick_direction,
    select_best_quote,
    settle_quote,
)
from cks_picks_cfb.season.manifest import utc


def normalize_quotes(table: pd.DataFrame) -> pd.DataFrame:
    """Accept normalized target quotes or the lake's paired spread/total rows."""
    if table.empty:
        return pd.DataFrame(columns=["game_id", "target", "point", "captured_at"])
    rows = []
    for source in table.to_dict("records"):
        for target in (
            (source["target"],) if "target" in source else ("spread", "total")
        ):
            point = source.get("point") if "target" in source else source.get(target)
            if point is None or pd.isna(point):
                continue
            row = {**source, "target": target, "point": float(point)}
            if target not in {"spread", "total"} or not np.isfinite(row["point"]):
                raise ValueError("invalid market target/point")
            row["captured_at"] = utc(row["captured_at"])
            rows.append(row)
    return pd.DataFrame(rows)


def select_market(
    rows: pd.DataFrame,
    *,
    target: str,
    prediction: float,
    game_id: int,
    kickoff: pd.Timestamp,
    cutoff: pd.Timestamp,
    historical: bool,
) -> dict | None:
    if rows.empty:
        return None
    slate = rows[rows.game_id.eq(game_id) & rows.target.eq(target)].copy()
    if slate.empty:
        return None
    if not historical:
        slate = slate[slate.captured_at.le(cutoff)]
    if slate.empty:
        return None
    required = {"quote_id", "provider"}
    if (
        required - set(slate)
        or slate.quote_id.isna().any()
        or slate.provider.isna().any()
    ):
        raise ValueError("market rows require quote identity and provider")
    rule, provider_count = None, None
    if not {"snapshot_id", "canonical_line"} <= set(slate):
        # The checked lake quote set itself defines this snapshot; preserve real capture times.
        from cks_picks_cfb.season.manifest import sha

        # A revision can retain several captures. Shop only the latest quote per provider.
        slate = slate.sort_values(
            ["captured_at", "quote_id"], kind="stable"
        ).drop_duplicates("provider", keep="last")
        snapshot = select_market_snapshot(
            [
                MarketQuote(
                    quote_id=str(r.quote_id),
                    game_id=int(r.game_id),
                    provider=str(r.provider),
                    captured_at=r.captured_at.to_pydatetime(),
                    spread=float(r.point) if target == "spread" else None,
                    total=float(r.point) if target == "total" else None,
                )
                for r in slate.itertuples()
            ],
            game_id=game_id,
            as_of=slate.captured_at.max().to_pydatetime(),
        )
        slate["canonical_line"] = (
            snapshot.spread if target == "spread" else snapshot.total
        )
        rule = snapshot.spread_rule if target == "spread" else snapshot.total_rule
        provider_count = (
            snapshot.spread_provider_count
            if target == "spread"
            else snapshot.total_provider_count
        )
        slate["snapshot_id"] = sha(
            slate.sort_values("quote_id")
            .to_json(date_format="iso", orient="records")
            .encode()
        )
    # Direction is fixed by consensus before shopping eligible quotes in its snapshot.
    latest = slate.sort_values(
        ["captured_at", "snapshot_id", "quote_id"], kind="stable"
    ).iloc[-1]
    linked = slate[slate.snapshot_id.eq(latest.snapshot_id)]
    canonical_lines = linked.canonical_line.dropna().unique()
    if len(canonical_lines) != 1 or not np.isfinite(canonical_lines[0]):
        raise ValueError("snapshot has conflicting/missing consensus line")
    canonical_line = float(canonical_lines[0])
    # Snapshot lineage: every quote linked to the chosen snapshot for this target.
    lineage = {
        "canonical_line": canonical_line,
        "snapshot_rule": rule,
        "provider_count": (
            provider_count
            if provider_count is not None
            else int(linked.provider.nunique())
        ),
        "source_quote_ids": json.dumps(sorted(linked.quote_id.astype(str))),
        "snapshot_captured_at": linked.captured_at.max().isoformat(),
    }
    if historical:
        side = pick_direction(prediction, canonical_line, target=target)
        candidates = []
        for row in linked.to_dict("records"):
            price = _side_price(row, side, target, require_price=False)
            if price is not None and np.isfinite(price) and price != 0:
                candidates.append({**row, "price": price})
        if not candidates:
            return None
        best = min(
            candidates, key=lambda row: _sort_key(row, target=target, direction=side)
        )
        return {
            **best,
            **lineage,
            "side": side,
            "benchmark_type": "cfbd_retrospective",
        }
    selected = select_best_quote(
        target=target,
        prediction=prediction,
        canonical_snapshot_id=str(latest.snapshot_id),
        canonical_line=canonical_line,
        game_id=game_id,
        kickoff_utc=kickoff.to_pydatetime(),
        forecast_cutoff=None if historical else cutoff.to_pydatetime(),
        quote_candidates=linked.to_dict("records"),
    )
    if selected is None:
        return None
    chosen = asdict(selected)
    chosen["provider"] = linked.set_index("quote_id").loc[selected.quote_id, "provider"]
    return {**chosen, **lineage, "benchmark_type": "retained_prekickoff"}


def grade_predictions(
    predictions: pd.DataFrame,
    schedule: pd.DataFrame,
    finals: pd.DataFrame,
    retained: pd.DataFrame,
    fallback: pd.DataFrame,
    *,
    live_week: int | None,
    as_of: str,
) -> pd.DataFrame:
    quotes = normalize_quotes(retained)
    historical_lines = normalize_quotes(fallback)
    if (
        not historical_lines.empty
        and not historical_lines.get("source_provider", historical_lines.provider)
        .astype(str)
        .str.casefold()
        .eq("cfbd")
        .all()
    ):
        raise ValueError("retrospective fallback must identify CFBD")
    for table in (quotes, historical_lines):
        if not table.empty and table.captured_at.gt(utc(as_of)).any():
            raise ValueError("quote capture is later than preparation as-of")
    games = schedule.set_index("game_id")
    scores = finals.set_index("game_id")
    rows = []
    for prediction in predictions.itertuples():
        game = games.loc[prediction.game_id]
        target = "spread" if prediction.target == "margin" else "total"
        kickoff = utc(game.kickoff_utc)
        cutoff = utc(as_of) if prediction.week == live_week else kickoff
        # Historical eligibility uses real capture time strictly before kickoff.
        eligible = (
            quotes[quotes.captured_at.lt(kickoff)] if not quotes.empty else quotes
        )
        selected = select_market(
            eligible,
            target=target,
            prediction=prediction.mean,
            game_id=prediction.game_id,
            kickoff=kickoff,
            cutoff=cutoff,
            historical=False,
        )
        if selected is None and prediction.week != live_week:
            selected = select_market(
                historical_lines,
                target=target,
                prediction=prediction.mean,
                game_id=prediction.game_id,
                kickoff=kickoff,
                cutoff=cutoff,
                historical=True,
            )
        row = {
            "season": 2026,
            "week": int(prediction.week),
            "game_id": int(prediction.game_id),
            "target": target,
            "prediction": float(prediction.mean),
            "benchmark_type": "ungraded",
            "side": None,
            "point": None,
            "price": None,
            "quote_id": None,
            "snapshot_id": None,
            "provider": None,
            "captured_at": None,
            "result": None,
            "units": None,
            "canonical_line": None,
            "snapshot_rule": None,
            "provider_count": None,
            "source_quote_ids": None,
            "snapshot_captured_at": None,
        }
        if selected:
            for name in (
                "benchmark_type",
                "side",
                "point",
                "price",
                "quote_id",
                "snapshot_id",
                "provider",
                "canonical_line",
                "snapshot_rule",
                "provider_count",
                "source_quote_ids",
                "snapshot_captured_at",
            ):
                row[name] = selected[name]
            row["captured_at"] = utc(selected["captured_at"]).isoformat()
            if prediction.game_id in scores.index:
                score = scores.loc[prediction.game_id]
                point = float(selected["point"])
                # Settlement expects the selected-side spread, whereas stored points are home-signed.
                if target == "spread" and selected["side"] == "away":
                    point = -point
                units = settle_quote(
                    target=target,
                    direction=selected["side"],
                    actual_spread=float(score.home_points - score.away_points),
                    actual_total=float(score.home_points + score.away_points),
                    point=point,
                    price=selected["price"],
                )
                row.update(
                    units=units,
                    result="win" if units > 0 else "loss" if units < 0 else "push",
                )
        rows.append(row)
    return pd.DataFrame(rows)
