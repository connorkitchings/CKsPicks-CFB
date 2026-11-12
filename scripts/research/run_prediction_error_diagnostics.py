"""Regenerate the V5 prediction-error diagnostics report (2021-2025, read-only).

Reads the persisted ratings-lab corpus from local lab storage (the local-output
exception in docs/research/ratings-lab-v1.md). Venue and conference rows come
from the pinned `fbs_involved_games` dataset; they are cached in the local lab
output after the first run, and only that first run does a read-only read of the
Preview data lake (credentials from the checkout's environment). Nothing is
written to any bucket, and the only repository file written is the report. The
first step reproduces the known 2025 V5 MAEs; a mismatch stops the run before
any slice is computed.

    uv run python scripts/research/run_prediction_error_diagnostics.py
    uv run python scripts/research/run_prediction_error_diagnostics.py --check
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from cks_picks_cfb.ratings_lab.artifacts import (
    LocalLabStore,
    ReadOnlySource,
    ResearchStorage,
)
from cks_picks_cfb.ratings_lab.contracts import HEADLINE_SEASONS
from cks_picks_cfb.ratings_lab.corpus import Corpus, load_persisted_corpus
from cks_picks_cfb.ratings_lab.error_slices import (
    GAP_LABELS,
    MIN_CELL_GAMES,
    TERCILE_LABELS,
    WEEK_BUCKETS,
    attach_slices,
    early_season_cost,
    game_attributes,
    quarantine_exposed_games,
    require_development_view,
    slice_table,
)
from cks_picks_cfb.ratings_lab.evaluation import (
    KEYS,
    common_bridge_predictions,
    frozen_v5_predictions,
    scorecard,
)
from cks_picks_cfb.ratings_lab.site_context import (
    CONFERENCE_GAME_LABELS,
    CONFERENCE_GROUPS,
    HOME_VENUE_MIN_GAMES,
    VENUE_CLASSES,
    game_context,
)
from cks_picks_cfb.ratings_lab.total_bias import (
    bias_share_of_mse,
    error_correlation,
    level_and_slope,
    paired_errors,
    quantile_bands,
    rolling_recentering,
    team_points_split,
)

REPORT = Path("docs/modeling/prediction_error_diagnostics_2021_2025.md")
EXPECTED_2025_MAE = {"margin": 14.1596, "total": 13.3558}
TARGETS = ("margin", "total")
DIMENSIONS = (
    ("week_bucket", "Week of season", WEEK_BUCKETS),
    ("gap_bin", "Rating-gap size", GAP_LABELS),
    ("totals_regime", "Totals regime", TERCILE_LABELS),
    ("stage_label", "Completed-game stage", tuple(f"stage {n}" for n in range(5))),
    ("venue_class", "Site class", VENUE_CLASSES),
    ("conference_group", "Home-team conference group", CONFERENCE_GROUPS),
    ("home_conference", "Home-team conference", None),
    (
        "conference_game_label",
        "Conference versus non-conference",
        CONFERENCE_GAME_LABELS,
    ),
    (
        "quarantine_label",
        "Partial-quarantine exposure (descriptive)",
        ("not exposed", "exposed"),
    ),
)
SITE_COLUMNS = [
    "season",
    "game_id",
    "home_team",
    "away_team",
    "neutral_site",
    "venue_id",
    "home_conference",
    "away_conference",
    "conference_game",
]
SITE_DATASET = "fbs_involved_games"
SITE_SEASONS = (2021, 2022, 2023, 2024, 2025)
HEADER = ["Slice", "Games", "MAE", "RMSE", "Bias", "90% coverage"]


def _open_local(lab_root: Path, corpus_key: str | None) -> tuple[Corpus, str]:
    storage = ResearchStorage(
        source=ReadOnlySource(LocalLabStore(lab_root / "source")),
        output=LocalLabStore(lab_root / "output"),
    )
    if corpus_key is None:
        found = sorted((lab_root / "output").glob("ratings-lab/v1/runs/*/corpus.json"))
        if len(found) != 1:
            raise SystemExit(
                f"expected exactly one persisted corpus under {lab_root}/output, "
                f"found {len(found)}; pass --corpus-key"
            )
        corpus_key = found[0].relative_to(lab_root / "output").as_posix()
    ref, _ = storage.stage_at(corpus_key)
    return load_persisted_corpus(storage, ref), corpus_key


def _read_site_rows_from_lake(lab_root: Path) -> pd.DataFrame:
    """Read-only read of the pinned `fbs_involved_games` dataset (no writes, no provider calls)."""
    from dotenv import find_dotenv, load_dotenv

    from cks_picks_cfb.data.lake import read_dataset
    from cks_picks_cfb.ratings.possession_rating_materializer import (
        _core_eligibility_refs,
    )
    from cks_picks_cfb.ratings_lab.artifacts import R2LabStore
    from cks_picks_cfb.ratings_lab.corpus import _load_manifest

    load_dotenv(find_dotenv(usecwd=True))
    names = ("BUCKET", "ACCOUNT_ID", "ACCESS_KEY", "SECRET_KEY")
    config = {name: os.getenv(f"CFB_R2_PREVIEW_{name}", "") for name in names}
    if not all(config.values()):
        raise SystemExit(
            "no cached venue/conference rows and the Preview read-source variables "
            "CFB_R2_PREVIEW_{BUCKET,ACCOUNT_ID,ACCESS_KEY,SECRET_KEY} are not set"
        )
    source = ReadOnlySource(
        R2LabStore(
            bucket=config["BUCKET"],
            account=config["ACCOUNT_ID"],
            access=config["ACCESS_KEY"],
            secret=config["SECRET_KEY"],
            endpoint=os.getenv("CFB_R2_PREVIEW_ENDPOINT"),
        )
    )
    storage = ResearchStorage(source, LocalLabStore(lab_root / "output"))
    refs = _core_eligibility_refs(source, _load_manifest(storage, "repair"))
    frames = [read_dataset(source, refs[s][SITE_DATASET]) for s in SITE_SEASONS]
    return pd.concat(frames, ignore_index=True)[SITE_COLUMNS]


def load_site_rows(lab_root: Path, corpus_key: str) -> pd.DataFrame:
    """Venue and conference rows for 2021-2025, cached deterministically in the lab output."""
    run_id = corpus_key.split("/")[-2]
    store = LocalLabStore(lab_root / "output")
    key = f"ratings-lab/v1/diagnostics/{run_id}/game_site_context.parquet"
    try:
        return pd.read_parquet(io.BytesIO(store.read(key)))
    except FileNotFoundError:
        pass
    rows = _read_site_rows_from_lake(lab_root)
    rows = rows.sort_values(["season", "game_id"], kind="mergesort").reset_index(
        drop=True
    )
    buffer = io.BytesIO()
    rows.to_parquet(buffer, index=False, compression="zstd")
    store.create_once(key, buffer.getvalue())
    return rows


def reproduction_check(frozen: pd.DataFrame) -> dict[str, float]:
    pooled = scorecard(frozen[frozen["season"].eq(2025)])["pooled"]
    observed = {target: float(pooled[target]["mae"]) for target in TARGETS}
    for target, expected in EXPECTED_2025_MAE.items():
        if round(observed[target], 4) != expected:
            raise SystemExit(
                f"reproduction check failed for {target}: "
                f"{observed[target]:.4f} != {expected:.4f}; stopping"
            )
    return observed


def _row(label: str, cell: pd.Series) -> list[str]:
    games = f"{int(cell['games'])}{'*' if cell['small'] else ''}"
    return [
        label,
        games,
        f"{cell['mae']:.3f}",
        f"{cell['rmse']:.3f}",
        f"{cell['bias']:+.3f}",
        f"{100 * cell['coverage']:.1f}%",
    ]


def _markdown(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def _extremes(title: str, target: str, table: pd.DataFrame) -> str | None:
    """Plain extremes among cells with enough games."""
    usable = table[~table["small"]]
    if len(usable) < 2:
        return None
    hi, lo = usable["mae"].idxmax(), usable["mae"].idxmin()
    bias = usable["bias"].abs().idxmax()
    cov_lo, cov_hi = usable["coverage"].idxmin(), usable["coverage"].idxmax()
    return (
        f"{target.capitalize()} by {title.lower()}: MAE is largest in `{hi}` "
        f"({usable.loc[hi, 'mae']:.2f}) and smallest in `{lo}` ({usable.loc[lo, 'mae']:.2f}); "
        f"the largest bias is `{bias}` ({usable.loc[bias, 'bias']:+.2f}); 90% coverage runs "
        f"from {100 * usable.loc[cov_lo, 'coverage']:.1f}% (`{cov_lo}`) to "
        f"{100 * usable.loc[cov_hi, 'coverage']:.1f}% (`{cov_hi}`)."
    )


def _totals_section(common: pd.DataFrame, attrs: pd.DataFrame, w) -> list[str]:
    """Totals over-prediction diagnostic; returns plain observation lines."""
    findings: list[str] = []
    total = common[common["target"].eq("total")]
    w("## Totals over-prediction diagnostic", "")
    w(
        "Read-only decomposition of the total's negative bias (outcomes below the prediction, so "
        "predicted totals run high). The margin is untouched. Nothing here is a proposed model: "
        "regressions are descriptive and the recentering below is a labelled diagnostic.",
        "",
    )

    w("### Bias by slice (total)", "")
    bias_dims = (
        ("week_bucket", WEEK_BUCKETS),
        ("total_band", tuple(f"band {i}" for i in range(1, 6))),
        ("gap_bin", GAP_LABELS),
        ("venue_class", VENUE_CLASSES),
        ("conference_group", CONFERENCE_GROUPS),
        ("conference_game_label", CONFERENCE_GAME_LABELS),
    )
    rows = []
    cells = {}
    for key, order in bias_dims:
        table = slice_table(total, key, order)
        for _, r in table.iterrows():
            games_cell = f"{int(r['games'])}{'*' if r['small'] else ''}"
            rows.append([key, r["slice"], games_cell, f"{r['bias']:+.3f}"])
            if not r["small"]:
                cells[(key, r["slice"])] = float(r["bias"])
    w(_markdown(["Dimension", "Slice", "Games", "Bias"], rows), "")
    lo, hi = min(cells, key=cells.get), max(cells, key=cells.get)
    findings.append(
        f"Total bias by slice (cells of at least {MIN_CELL_GAMES} games) runs from "
        f"{cells[lo]:+.2f} (`{lo[1]}`, {lo[0]}) to {cells[hi]:+.2f} (`{hi[1]}`, {hi[0]}); "
        "the sign is negative in "
        f"{sum(v < 0 for v in cells.values())} of {len(cells)} cells."
    )

    errors = paired_errors(common)
    w("### Home-team and away-team points", "")
    w(
        "Implied team points are (total + margin) / 2 for home and (total - margin) / 2 for away, "
        "so these errors are exact combinations of the margin and total errors. Outcomes in the "
        "corpus give each team's actual points. Bias is actual minus implied points.",
        "",
    )
    split = team_points_split(errors)
    w(
        _markdown(
            ["Season", "Games", "Home bias", "Away bias", "Home MAE", "Away MAE"],
            [
                [
                    r.season,
                    str(int(r.games)),
                    f"{r.home_bias:+.3f}",
                    f"{r.away_bias:+.3f}",
                    f"{r.home_mae:.3f}",
                    f"{r.away_mae:.3f}",
                ]
                for r in split.itertuples()
            ],
        ),
        "",
    )
    pooled = split.iloc[-1]
    findings.append(
        f"Total over-prediction by team: pooled home-team points bias {pooled['home_bias']:+.2f}, "
        f"away-team points bias {pooled['away_bias']:+.2f}."
    )

    w("### Level offset or slope", "")
    w(
        "Descriptive regression of actual total on predicted total, per season (not used to "
        "score anything). Level gap is mean actual minus mean predicted. A slope of 1 with a "
        "level gap is a pure offset; a slope below 1 means the gap widens as the predicted total "
        "rises.",
        "",
    )
    fit = level_and_slope(total)
    w(
        _markdown(
            [
                "Season",
                "Games",
                "Mean predicted",
                "Mean actual",
                "Level gap",
                "Slope",
                "Intercept",
            ],
            [
                [
                    r.season,
                    str(int(r.games)),
                    f"{r.mean_predicted:.2f}",
                    f"{r.mean_actual:.2f}",
                    f"{r.level_gap:+.2f}",
                    f"{r.slope:.3f}",
                    f"{r.intercept:.2f}",
                ]
                for r in fit.itertuples()
            ],
        ),
        "",
    )
    by_season = fit.iloc[:-1]
    pooled_fit = fit.iloc[-1]
    findings.append(
        f"Total level: the level gap by season ranges from {by_season['level_gap'].min():+.2f} "
        f"to {by_season['level_gap'].max():+.2f}; the actual-on-predicted slope ranges from "
        f"{by_season['slope'].min():.2f} to {by_season['slope'].max():.2f} (pooled "
        f"{pooled_fit['slope']:.2f}). Predicted totals have a standard deviation of only "
        f"{total['prediction'].std(ddof=0):.2f} points, so per-season slopes are imprecise."
    )

    w("### Rolling-origin recentering (diagnostic, not a model)", "")
    w(
        "Each season's predicted total is shifted by the mean total error of strictly earlier "
        "seasons only (2022 by 2021, 2023 by 2021 to 2022, and so on); 2021 has no earlier "
        "season and is unshifted. The same-season column removes that season's own mean error, "
        "which uses the scored rows and is an upper bound on what any recentering could do. "
        "Intervals are shifted by the same amount.",
        "",
    )
    roll = rolling_recentering(total)
    w(
        _markdown(
            [
                "Season",
                "Games",
                "Shift",
                "MAE base",
                "MAE rolling",
                "MAE same-season",
                "RMSE base",
                "RMSE rolling",
                "Bias after rolling",
                "Coverage base",
                "Coverage rolling",
            ],
            [
                [
                    str(r.season),
                    str(r.games),
                    f"{r.shift:+.3f}",
                    f"{r.base['mae']:.3f}",
                    f"{r.rolling['mae']:.3f}",
                    f"{r.same_season['mae']:.3f}",
                    f"{r.base['rmse']:.3f}",
                    f"{r.rolling['rmse']:.3f}",
                    f"{r.rolling['bias']:+.3f}",
                    f"{100 * r.base['coverage']:.1f}%",
                    f"{100 * r.rolling['coverage']:.1f}%",
                ]
                for r in roll.itertuples()
            ],
        ),
        "",
    )
    scored = roll[roll["shift"].ne(0.0)]
    weight = scored["games"].to_numpy(float)

    def weighted(column: str, key: str) -> float:
        return float(np.average([c[key] for c in scored[column]], weights=weight))

    base_mae = weighted("base", "mae")
    rolling_mae = weighted("rolling", "mae")
    own_mae = weighted("same_season", "mae")
    base_cov = weighted("base", "coverage")
    rolling_cov = weighted("rolling", "coverage")
    share = bias_share_of_mse(total)
    w("### How much recentering explains", "")
    w(
        _markdown(
            ["Measure (2022 to 2025, game-weighted)", "Value"],
            [
                ["MAE, uncorrected", f"{base_mae:.3f}"],
                ["MAE, rolling-origin recentered", f"{rolling_mae:.3f}"],
                ["MAE, same-season recentered (upper bound)", f"{own_mae:.3f}"],
                [
                    "MAE change, rolling",
                    f"{rolling_mae - base_mae:+.3f} ({100 * (rolling_mae - base_mae) / base_mae:+.1f}%)",
                ],
                [
                    "MAE change, same-season",
                    f"{own_mae - base_mae:+.3f} ({100 * (own_mae - base_mae) / base_mae:+.1f}%)",
                ],
                ["90% coverage, uncorrected", f"{100 * base_cov:.1f}%"],
                ["90% coverage, rolling", f"{100 * rolling_cov:.1f}%"],
                [
                    "Squared mean error as share of total MSE (2021 to 2025)",
                    f"{100 * share:.1f}%",
                ],
            ],
        ),
        "",
    )
    findings.append(
        f"Rolling-origin recentering of the total moves 2022 to 2025 MAE from {base_mae:.2f} to "
        f"{rolling_mae:.2f} ({rolling_mae - base_mae:+.2f}); removing each season's own mean "
        f"error gives {own_mae:.2f}. The squared mean error is {100 * share:.1f}% of the total's "
        f"mean squared error, so {100 * (1 - rolling_mae / base_mae):.1f}% of MAE is removed "
        "and the rest is game-to-game scatter."
    )

    w("### Margin error against total error", "")
    corr = error_correlation(errors)
    w(
        _markdown(
            ["Season", "Games", "Correlation"],
            [
                [r.season, str(int(r.games)), f"{r.correlation:+.3f}"]
                for r in corr.itertuples()
            ],
        ),
        "",
    )
    findings.append(
        f"Margin error and total error are correlated {corr.iloc[-1]['correlation']:+.2f} pooled "
        f"(by season {corr.iloc[:-1]['correlation'].min():+.2f} to "
        f"{corr.iloc[:-1]['correlation'].max():+.2f})."
    )
    return findings


def build_report(corpus: Corpus, corpus_key: str, site_rows: pd.DataFrame) -> str:
    frozen = frozen_v5_predictions(corpus)
    observed = reproduction_check(frozen)

    features = corpus.v5_features
    kwargs = {"candidate_id": "v5_common_alpha10_v1", "bridge": "v5_common"}
    headline = common_bridge_predictions(corpus, features, **kwargs)
    early = common_bridge_predictions(
        corpus, features, seasons=(2018, 2019, 2021), **kwargs
    )
    common = pd.concat(
        [
            early[early["season"].eq(2021)],
            headline[headline["season"].isin(HEADLINE_SEASONS)],
        ],
        ignore_index=True,
    )
    require_development_view(common)
    paired = frozen.merge(
        common, on=KEYS, suffixes=("_frozen", "_common"), validate="one_to_one"
    )
    identical = len(paired) == len(frozen) and bool(
        np.allclose(paired["prediction_frozen"], paired["prediction_common"], atol=1e-9)
    )
    if not identical:
        raise SystemExit("frozen V5 and v5-common predictions differ for 2022-2025")

    exposure = quarantine_exposed_games(corpus.observations, features)
    attrs, edges = game_attributes(common, features, exposure)
    attrs["quarantine_label"] = attrs["quarantine_exposed"].map(
        {True: "exposed", False: "not exposed"}
    )
    context = game_context(site_rows)
    attrs = attrs.merge(context, on=["season", "game_id"], how="left", validate="1:1")
    if attrs["venue_class"].isna().any():
        raise SystemExit(
            "venue and conference rows do not cover every development game"
        )
    attrs["total_band"], band_edges = quantile_bands(attrs["predicted_total"], 5)
    common = attach_slices(common, attrs)
    seasons = sorted(common["season"].unique())
    games = len(attrs)

    out: list[str] = []

    def w(*lines: str) -> None:
        out.append("\n".join(lines))

    findings: list[str] = []

    w("# Prediction-error diagnostics, 2021 to 2025", "")
    w(
        "Read-only diagnostics of where V5 prediction error sits. Plain observations only: "
        "no candidate fixes, and no model, data, threshold or release change. "
        "Generated by `scripts/research/run_prediction_error_diagnostics.py`; rerunning it "
        "reproduces this file byte for byte. Contract: "
        "[prediction-error diagnostics](../plans/2026-11-12/03-prediction-error-diagnostics.md). "
        "Protocol: [offseason research protocol](../plans/2026-11-12/02-offseason-research-protocol.md) "
        "(development view 2021 to 2025 only; 2020 excluded; no betting-outcome slices).",
        "",
    )
    w("## Scope and sources", "")
    w(
        f"- Corpus: persisted ratings-lab corpus `{corpus_key}` in local lab storage "
        "(local-output exception).",
        f"- Venue and conference: the `{SITE_DATASET}` dataset (neutral-site flag, venue id, each "
        "team's conference in that season, conference-game flag), reached through the same pinned "
        "core-eligibility references as the corpus and joined by season and `game_id`. It was read "
        "once, read-only, from the Preview data lake and cached in the local lab output.",
        f"- Population: {games:,} games, 2021 to 2025, margin and total each. 2021 comes from the "
        "bridge's rolling-origin predictions (fit on 2015 to 2019); 2022 to 2025 are the headline "
        "seasons.",
        f"- Frozen V5 (`frozen_v5_predictions`, 2022 to 2025, {len(frozen) // 2:,} games) and the "
        "v5-common bridge (alpha-10 Ridge on V5's own pregame states, fit on earlier seasons only) "
        "give identical predictions for 2022 to 2025 (checked row by row). Frozen V5 carries no "
        "interval, so every table below uses the v5-common rows, which add the 90% intervals and "
        "the 2021 season.",
        "- Error is `actual - prediction`. Positive bias means outcomes ran above the prediction.",
        f"- Cells under {MIN_CELL_GAMES} games are marked with `*`; their MAE is noisy. "
        "Margin and total are always reported separately.",
        "- Slices use only the model's own outputs, game timing, completed-game stage and "
        "evidence-coverage flags. No slice uses market lines, against-the-spread results or "
        "over/under results.",
        "",
    )
    w("## Reproduction check", "")
    w("Pooled 2025 frozen V5 MAE, computed with `scorecard` before any slice:", "")
    w(
        _markdown(
            ["Target", "Expected", "Observed", "Match"],
            [
                [t, f"{EXPECTED_2025_MAE[t]:.4f}", f"{observed[t]:.4f}", "yes"]
                for t in TARGETS
            ],
        ),
        "",
    )
    w("## Slice definitions", "")
    w(
        f"- Rating-gap size: absolute predicted margin, terciles over all {games:,} games. Edges "
        f"{edges['gap'][0]:.3f} and {edges['gap'][1]:.3f} points: small gap at or below the first "
        "edge, medium up to the second, large above.",
        f"- Totals regime: predicted total, terciles over the same games. Edges "
        f"{edges['total'][0]:.3f} and {edges['total'][1]:.3f} points: low, mid, high. The middle "
        "tercile is narrow because predicted totals are tightly concentrated.",
        "- Week buckets: weeks 1 to 4 individually, then 5 to 8, 9 to 12, 13 to 16. Week 0 is not "
        "in the corpus (the earliest week is 1).",
        "- Completed-game stage: the corpus `completed_game_stage` value (0 to 4).",
        f"- Site class: neutral site is the dataset's neutral flag. A team's home venues are the venue ids "
        f"where it hosted at least {HOME_VENUE_MIN_GAMES} non-neutral games in 2021 to 2025, plus its most "
        "frequent hosting venue. A non-neutral game at any other venue is its own class; a game with a "
        "missing flag or venue id would be `venue unknown`.",
        "- Conference group: the home team's conference in that season, grouped as Power (ACC, "
        "Big 12, Big Ten, Pac-12, SEC), Group of 5 (American Athletic, Conference USA, Mid-American, "
        "Mountain West, Sun Belt), FBS independent, or other. Pac-12 is Power throughout although it "
        "had two members in 2024 and 2025. Conference game is the dataset's flag.",
        "- Predicted-total band: quintiles of predicted total, interior edges "
        + ", ".join(f"{e:.3f}" for e in band_edges)
        + " points.",
        "- Partial-quarantine exposure: either team played an earlier-week game, in the same "
        "season, in which some but not all team-role PPP observations were quarantined for "
        "unresolved scoring attribution. Descriptive only; see the limits below.",
        "",
    )

    w("## Overall", "")
    for target in TARGETS:
        part = common[common["target"].eq(target)].assign(group="pooled")
        rows = [
            _row(str(s), slice_table(part[part["season"].eq(s)], "group").iloc[0])
            for s in seasons
        ]
        pooled = slice_table(part, "group").iloc[0]
        rows.append(_row("pooled", pooled))
        w(
            f"### {target.capitalize()}",
            "",
            _markdown(["Season", *HEADER[1:]], rows),
            "",
        )
        findings.append(
            f"{target.capitalize()} pooled over 2021 to 2025: MAE {pooled['mae']:.2f}, RMSE "
            f"{pooled['rmse']:.2f}, bias {pooled['bias']:+.2f}, 90% interval coverage "
            f"{100 * pooled['coverage']:.1f}%."
        )

    w("## Site class counts", "")
    counts = attrs.groupby(["venue_class", "season"]).size().unstack(fill_value=0)
    rows = []
    for label in VENUE_CLASSES:
        per_season = (
            counts.loc[label] if label in counts.index else pd.Series(0, index=seasons)
        )
        rows.append(
            [label, *[str(int(per_season.get(s, 0))) for s in seasons]]
            + [str(int(per_season.sum()))]
        )
    w(_markdown(["Class", *[str(s) for s in seasons], "Total"], rows), "")
    unflagged = attrs[attrs["venue_class"].eq(VENUE_CLASSES[2])]
    findings.append(
        f"Site classes over {games:,} games: "
        + ", ".join(
            f"{int((attrs['venue_class'] == c).sum()):,} {c}" for c in VENUE_CLASSES
        )
        + f"; {len(unflagged)} non-neutral games sit at a venue that is not one of the home "
        "team's home venues."
    )

    for key, title, order in DIMENSIONS:
        w(f"## {title}", "")
        for target in TARGETS:
            table = slice_table(common[common["target"].eq(target)], key, order)
            rows = [_row(r["slice"], r) for _, r in table.iterrows()]
            w(f"### {target.capitalize()}", "", _markdown(HEADER, rows), "")
            line = _extremes(title, target, table.set_index("slice"))
            if line:
                findings.append(line)

    w("## Weeks 1 to 4 prior cost", "")
    w(
        "Early-week MAE against the level for weeks 5 to 16. Excess is early-week MAE minus the "
        "weeks 5 to 16 MAE. Week 0 games are not in the corpus.",
        "",
    )
    for target in TARGETS:
        cost = early_season_cost(common[common["target"].eq(target)])
        rows = [
            [
                str(int(r.week)),
                f"{int(r.games)}{'*' if r.small else ''}",
                f"{r.mae:.3f}",
                f"{r.later_mae:.3f}",
                f"{r.excess:+.3f}",
            ]
            for r in cost.itertuples()
        ]
        w(
            f"### {target.capitalize()}",
            "",
            _markdown(["Week", "Games", "MAE", "Weeks 5-16 MAE", "Excess"], rows),
            "",
        )
        findings.append(
            f"Early-season cost, {target}: MAE excess over the weeks 5 to 16 level is "
            + ", ".join(
                f"{r.excess:+.2f} in week {int(r.week)}" for r in cost.itertuples()
            )
            + "."
        )

    findings += _totals_section(common, attrs, w)

    exposed = int(attrs["quarantine_exposed"].sum())
    w("## What could not be computed", "")
    w(
        "- **Sensitivity of narrow matchups to the partial-quarantine policy.** A real test "
        "re-estimates the ratings with the partially quarantined games removed and re-scores the "
        "affected matchups, as in the "
        "[V5 ratings audit](v5_offense_defense_ratings_audit_2026.md). The corpus holds frozen "
        "ratings and bridge features only, so that re-estimation is not possible here and was not "
        f"approximated. The exposure table above is a descriptive proxy ({exposed:,} of {games:,} "
        "games are exposed); it compares error for games whose teams had an earlier partially "
        "quarantined game against those that did not, and says nothing about what the error would "
        "be under a different policy.",
        "",
    )
    w("## Observations", "")
    w(*[f"- {line}" for line in findings], "")
    w("## Monitoring", "")
    w(
        "This report is the development view only. A separate monitoring section for the "
        "held-out season is added only after the 2026-12-13 final close, and nothing in it "
        "feeds model choices.",
        "",
    )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--lab-root",
        default=os.getenv(
            "CFB_LAB_LOCAL_ROOT", str(Path.home() / "cfb_ratings_lab_v6")
        ),
    )
    parser.add_argument("--corpus-key", default=None)
    parser.add_argument("--output", default=str(REPORT))
    parser.add_argument(
        "--check", action="store_true", help="fail if the report on disk differs"
    )
    args = parser.parse_args(argv)
    corpus, key = _open_local(Path(args.lab_root), args.corpus_key)
    text = build_report(corpus, key, load_site_rows(Path(args.lab_root), key))
    path = Path(args.output)
    if args.check:
        if not path.exists() or path.read_text() != text:
            print("report differs from regenerated output", file=sys.stderr)
            return 1
        print("report reproduces byte for byte")
        return 0
    path.write_text(text)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
