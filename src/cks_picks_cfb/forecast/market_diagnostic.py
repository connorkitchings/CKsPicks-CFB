"""Contract 02 (2026-09-21) 2025 market-line diagnostic study.

Compares the 11A-verified V5 conditional 2025 forecasts against replay
provider-recorded lines as a labeled diagnostic.  Independent of every forecast
producer *and* of the 2025 V4 replay predictions: it reads only the immutable
``market_snapshots`` dataset bytes plus the 12A loader path for forecasts.

Permitted use: ``diagnostic_comparison_only``.
Line semantics: ``provider_recorded_lines_postseason_capture`` — this study is
explicitly NOT closing-line or CLV evidence and has no effect on any readiness
gate, eligibility, Contract 11/12, or the 04/04B lifecycle.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.forecast.historical_scorecard import (
    VERIFICATION_MANIFEST_URI,
    ScorecardError,
    _load_predictions,
    validate_verification_manifest,
)

# ---------------------------------------------------------------------------
# Contract-pinned constants
# ---------------------------------------------------------------------------

DIAGNOSTIC_SCHEMA = "data_first_market_diagnostic_v1"
DIAGNOSTIC_MANIFEST_SCHEMA = "data_first_market_diagnostic_manifest_v1"

OUTPUT_ROOT = "artifacts/research/data-first-football-v1/market-diagnostics/v1/runs"

PERMITTED_USE = "diagnostic_comparison_only"
LINE_SEMANTICS = "provider_recorded_lines_postseason_capture"

# Exact replay market_snapshots identity, confirmed from the immutable
# replay-2025-v4-w1..w16 input_refs.json records (unanimous 16/16).
MARKET_DATASET = "market_snapshots"
MARKET_VERSION_ID = "e4061aab93b1e667a34ce780"
MARKET_SCHEMA_VERSION = "market_snapshots_v1"
MARKET_CONTENT_SHA = "6df93ed56b3fbcaea4434151099fe75794c3c9205f278d437895a170339cc5d9"
MARKET_URI = (
    "lake/silver/dataset=market_snapshots/version=e4061aab93b1e667a34ce780/data.parquet"
)
MARKET_POLICY_VERSION = "consensus_then_median_v1"
EXPECTED_MARKET_CATALOG_STATE = "quarantined"

REPLAY_WEEKS = tuple(f"w{i}" for i in range(1, 17))
REPLAY_INPUT_REFS_PREFIX = "artifacts/preview/pipeline-runs/replay-2025-v4-"

STUDY_SEASON = 2025
TARGETS = ("margin", "total")
MIN_INTERSECTION_PER_TARGET = 500

# Sign-convention gates (documented thresholds; fail closed below).
R_PRED_MARKET_MIN = 0.6
R_ACTUAL_PRED_MIN = 0.25
R_ACTUAL_MARKET_MIN = 0.25

BOOTSTRAP_SEED = 20260921
BOOTSTRAP_REPS = 2000

FORECAST_COLUMNS = frozenset(
    {"game_id", "target", "prediction", "actual", "completed_games"}
)
SNAPSHOT_COLUMNS = frozenset(
    {"game_id", "spread_line", "total_line", "market_policy_version"}
)


class MarketDiagnosticError(ScorecardError):
    """Raised when the market-line diagnostic cannot proceed."""


# ---------------------------------------------------------------------------
# Market snapshots resolution (Task 1)
# ---------------------------------------------------------------------------


def replay_market_ref_uris() -> list[str]:
    """URIs of the immutable replay pipeline-run input refs."""
    return [
        f"{REPLAY_INPUT_REFS_PREFIX}{week}/input_refs.json" for week in REPLAY_WEEKS
    ]


def resolve_market_snapshots_ref(storage: Any) -> dict[str, Any]:
    """Resolve the pinned market_snapshots identity from replay input refs.

    Reads all 16 immutable replay-2025-v4-w* input_refs.json records, requires
    unanimous agreement on the ``betting_lines`` (market_snapshots) ref, and
    requires an exact match to the contract-pinned identity.  Returns the
    ref dict.  Raises MarketDiagnosticError on any disagreement.
    """
    refs: list[dict[str, Any]] = []
    for uri in replay_market_ref_uris():
        try:
            records = json.loads(storage.read_bytes(uri))
        except (OSError, FileNotFoundError, json.JSONDecodeError) as exc:
            raise MarketDiagnosticError(
                f"Replay input refs unreadable at {uri!r}"
            ) from exc
        matches = [
            r
            for r in records
            if r.get("entity") == "betting_lines" and r.get("dataset") == MARKET_DATASET
        ]
        if len(matches) != 1:
            raise MarketDiagnosticError(
                f"Replay input refs at {uri!r} have {len(matches)} "
                f"market_snapshots refs (expected exactly 1)"
            )
        refs.append(matches[0])

    first = refs[0]
    for other in refs[1:]:
        if other != first:
            raise MarketDiagnosticError(
                "Replay input refs disagree on the market_snapshots identity"
            )

    pinned = {
        "dataset": MARKET_DATASET,
        "version_id": MARKET_VERSION_ID,
        "schema_version": MARKET_SCHEMA_VERSION,
        "content_sha": MARKET_CONTENT_SHA,
        "uri": MARKET_URI,
    }
    for key, expected in pinned.items():
        if first.get(key) != expected:
            raise MarketDiagnosticError(
                f"Replay market_snapshots {key} mismatch: "
                f"expected {expected!r}, got {first.get(key)!r}"
            )
    return dict(first)


def fetch_market_catalog_state(conn_url: str) -> dict[str, Any]:
    """Read-only lookup of the pinned market_snapshots catalog row."""
    import psycopg

    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT version_id, schema_version, content_sha, uri, state "
                "FROM catalog.dataset_versions WHERE dataset = %s "
                "AND version_id = %s",
                (MARKET_DATASET, MARKET_VERSION_ID),
            )
            row = cur.fetchone()
    if not row:
        raise MarketDiagnosticError(
            f"Catalog has no {MARKET_DATASET}/{MARKET_VERSION_ID} row"
        )
    return {
        "version_id": str(row[0]),
        "schema_version": str(row[1]),
        "content_sha": str(row[2]),
        "uri": str(row[3]),
        "state": str(row[4]),
    }


def assert_market_quarantined(catalog_row: dict[str, Any]) -> None:
    """Assert the catalog row matches the pinned identity and quarantine."""
    for key, expected in (
        ("version_id", MARKET_VERSION_ID),
        ("schema_version", MARKET_SCHEMA_VERSION),
        ("content_sha", MARKET_CONTENT_SHA),
        ("uri", MARKET_URI),
    ):
        if catalog_row.get(key) != expected:
            raise MarketDiagnosticError(
                f"Catalog market_snapshots {key} mismatch: "
                f"expected {expected!r}, got {catalog_row.get(key)!r}"
            )
    if catalog_row.get("state") != EXPECTED_MARKET_CATALOG_STATE:
        raise MarketDiagnosticError(
            "Catalog market_snapshots state is not "
            f"{EXPECTED_MARKET_CATALOG_STATE!r}: {catalog_row.get('state')!r}"
        )


def load_market_snapshots(storage: Any, ref: dict[str, Any]) -> pd.DataFrame:
    """Checksum-verified read of the market_snapshots dataset bytes."""
    dataset_ref = DatasetRef(
        dataset=str(ref["dataset"]),
        version_id=str(ref["version_id"]),
        schema_version=str(ref["schema_version"]),
        content_sha=str(ref["content_sha"]),
        uri=str(ref["uri"]),
    )
    try:
        return read_dataset(storage, dataset_ref)
    except Exception as exc:
        raise MarketDiagnosticError(
            f"Cannot load market_snapshots from {ref.get('uri')!r}"
        ) from exc


def validate_snapshots_frame(frame: pd.DataFrame) -> dict[str, Any]:
    """Validate the market_snapshots frame; return row/null accounting."""
    missing = sorted(SNAPSHOT_COLUMNS - set(frame.columns))
    if missing:
        raise MarketDiagnosticError(f"market_snapshots missing columns: {missing}")
    if frame.duplicated(subset=["game_id"], keep=False).any():
        raise MarketDiagnosticError("market_snapshots has duplicate game_id rows")
    bad_policy = frame[frame["market_policy_version"] != MARKET_POLICY_VERSION]
    if not bad_policy.empty:
        raise MarketDiagnosticError(
            f"market_snapshots has {len(bad_policy)} rows with unexpected policy"
        )
    spread_vals = pd.to_numeric(frame["spread_line"], errors="coerce")
    total_vals = pd.to_numeric(frame["total_line"], errors="coerce")
    if (~np.isfinite(spread_vals.to_numpy()) & frame["spread_line"].notna()).any():
        raise MarketDiagnosticError("market_snapshots has non-numeric spread_line")
    if (~np.isfinite(total_vals.to_numpy()) & frame["total_line"].notna()).any():
        raise MarketDiagnosticError("market_snapshots has non-numeric total_line")
    return {
        "snapshot_rows": int(len(frame)),
        "spread_lined": int(spread_vals.notna().sum()),
        "total_lined": int(total_vals.notna().sum()),
        "policy": MARKET_POLICY_VERSION,
    }


# ---------------------------------------------------------------------------
# Forecast loading (Task 1)
# ---------------------------------------------------------------------------


def load_study_forecasts(storage: Any) -> pd.DataFrame:
    """Load 11A-verified forecast rows filtered to the 2025 study season."""
    manifest = validate_verification_manifest(storage)
    frame = _load_predictions(storage, manifest)
    missing = sorted(FORECAST_COLUMNS - set(frame.columns))
    if missing:
        raise MarketDiagnosticError(f"forecast_prediction missing columns: {missing}")
    rows = frame[frame["season"] == STUDY_SEASON].copy()
    if rows.empty:
        raise MarketDiagnosticError(f"No forecast rows for season {STUDY_SEASON}")
    forbidden = rows[rows["season"].isin([2020, 2026])]
    if not forbidden.empty:
        raise MarketDiagnosticError("Study population contains forbidden seasons")
    for column in ("prediction", "actual"):
        vals = pd.to_numeric(rows[column], errors="coerce")
        if vals.isna().any() or (~np.isfinite(vals.to_numpy())).any():
            raise MarketDiagnosticError(
                f"Study forecasts have non-finite {column} values"
            )
    if rows.duplicated(subset=["game_id", "target"], keep=False).any():
        raise MarketDiagnosticError("Study forecasts have duplicate game_id+target")
    by_game = rows.groupby("game_id")["target"].apply(set)
    incomplete = by_game[by_game != set(TARGETS)]
    if not incomplete.empty:
        raise MarketDiagnosticError(
            f"Study forecasts have {len(incomplete)} games with incomplete targets"
        )
    return rows


# ---------------------------------------------------------------------------
# Sign-convention validation (Task 1)
# ---------------------------------------------------------------------------


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    x = x - x.mean()
    y = y - y.mean()
    denom = float(np.sqrt((x**2).sum() * (y**2).sum()))
    if denom == 0:
        return float("nan")
    return float((x * y).sum() / denom)


def validate_sign_convention(
    forecasts: pd.DataFrame, snapshots: pd.DataFrame
) -> dict[str, Any]:
    """Confirm margin orientation before any metric is computed.

    Market-implied home margin is ``-spread_line`` (spread_line is
    home-perspective: negative means the home team is favored).  V5 margin
    predictions and actuals must correlate positively with it; predictions
    and actuals must correlate positively with each other.  Fail closed.
    """
    margin = forecasts[forecasts["target"] == "margin"].copy()
    joined = margin.merge(
        snapshots[["game_id", "spread_line"]], on="game_id", how="inner"
    )
    joined = joined[pd.to_numeric(joined["spread_line"], errors="coerce").notna()]
    if joined.empty:
        raise MarketDiagnosticError("No margin rows join to lined games")
    pred = pd.to_numeric(joined["prediction"], errors="coerce").to_numpy(float)
    actual = pd.to_numeric(joined["actual"], errors="coerce").to_numpy(float)
    implied = -pd.to_numeric(joined["spread_line"], errors="coerce").to_numpy(float)

    result = {
        "n": int(len(joined)),
        "r_pred_market": _pearson(pred, implied),
        "r_actual_pred": _pearson(actual, pred),
        "r_actual_market": _pearson(actual, implied),
    }
    failures = []
    if not result["r_pred_market"] > R_PRED_MARKET_MIN:
        failures.append(
            f"r_pred_market={result['r_pred_market']:.3f} <= {R_PRED_MARKET_MIN}"
        )
    if not result["r_actual_pred"] > R_ACTUAL_PRED_MIN:
        failures.append(
            f"r_actual_pred={result['r_actual_pred']:.3f} <= {R_ACTUAL_PRED_MIN}"
        )
    if not result["r_actual_market"] > R_ACTUAL_MARKET_MIN:
        failures.append(
            f"r_actual_market={result['r_actual_market']:.3f} <= {R_ACTUAL_MARKET_MIN}"
        )
    if failures:
        raise MarketDiagnosticError(
            "Sign-convention gates failed: " + "; ".join(failures)
        )
    result["gates"] = "pass"
    return result


# ---------------------------------------------------------------------------
# Study population (Task 1)
# ---------------------------------------------------------------------------


def _line_column(target: str) -> str:
    return "spread_line" if target == "margin" else "total_line"


def build_study_population(
    forecasts: pd.DataFrame,
    snapshots: pd.DataFrame,
    *,
    min_intersection: int = MIN_INTERSECTION_PER_TARGET,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Join forecasts to lines per target; return population + accounting."""
    v5_games = sorted(int(g) for g in forecasts["game_id"].unique())
    lined_games = sorted(int(g) for g in snapshots["game_id"].unique())

    pieces: list[pd.DataFrame] = []
    per_target: dict[str, Any] = {}
    for target in TARGETS:
        leg = forecasts[forecasts["target"] == target][
            ["game_id", "prediction", "actual", "completed_games"]
        ].copy()
        line_col = _line_column(target)
        lines = snapshots[["game_id", line_col]].copy()
        lines[line_col] = pd.to_numeric(lines[line_col], errors="coerce")
        lines = lines[lines[line_col].notna()]
        joined = leg.merge(lines, on="game_id", how="inner")
        if joined.duplicated(subset=["game_id"], keep=False).any():
            raise MarketDiagnosticError(
                f"Study population has duplicate game_id rows for {target!r}"
            )
        excluded = sorted(
            set(leg["game_id"].astype(int)) - set(lines["game_id"].astype(int))
        )
        per_target[target] = {
            "v5_games": int(leg["game_id"].nunique()),
            "lined_games": int(lines["game_id"].nunique()),
            "intersection_games": int(len(joined)),
            "excluded_unlined_count": len(excluded),
            "excluded_unlined_game_ids": excluded,
        }
        if len(joined) < min_intersection:
            raise MarketDiagnosticError(
                f"Target {target!r} intersection {len(joined)} < floor {min_intersection}"
            )
        joined["target"] = target
        joined["market_implied"] = (
            -joined[line_col] if target == "margin" else joined[line_col]
        )
        pieces.append(joined)

    population = pd.concat(pieces, ignore_index=True)
    accounting = {
        "v5_games_2025": len(v5_games),
        "lined_games": len(lined_games),
        "per_target": per_target,
    }
    return population, accounting


# ---------------------------------------------------------------------------
# Paired metrics (Task 2)
# ---------------------------------------------------------------------------


def _stage_key(completed_games: int) -> str:
    if completed_games >= 4:
        return "4_plus"
    return str(int(completed_games))


def _paired_metrics(
    v5_pred: np.ndarray, market_pred: np.ndarray, actual: np.ndarray
) -> dict[str, Any]:
    v5_err = np.abs(v5_pred - actual)
    mkt_err = np.abs(market_pred - actual)
    delta = mkt_err - v5_err  # positive means V5 is closer
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    idx = rng.integers(0, len(delta), size=(BOOTSTRAP_REPS, len(delta)))
    boot_means = delta[idx].mean(axis=1)
    lo, hi = (float(np.percentile(boot_means, q)) for q in (2.5, 97.5))
    return {
        "n": int(len(delta)),
        "v5_mae": float(v5_err.mean()),
        "v5_rmse": float(np.sqrt(((v5_pred - actual) ** 2).mean())),
        "v5_bias": float((v5_pred - actual).mean()),
        "market_mae": float(mkt_err.mean()),
        "market_rmse": float(np.sqrt(((market_pred - actual) ** 2).mean())),
        "market_bias": float((market_pred - actual).mean()),
        "mae_delta_market_minus_v5": float(delta.mean()),
        "mae_delta_ci95": [lo, hi],
        "v5_closer": int((delta > 0).sum()),
        "market_closer": int((delta < 0).sum()),
        "ties": int((delta == 0).sum()),
    }


def _edge_distribution(v5_pred: np.ndarray, market_pred: np.ndarray) -> dict[str, Any]:
    edge = v5_pred - market_pred
    quantiles = (float(np.percentile(edge, q)) for q in (10, 25, 50, 75, 90))
    p10, p25, p50, p75, p90 = quantiles
    return {
        "mean": float(edge.mean()),
        "sd": float(edge.std(ddof=1)) if len(edge) > 1 else 0.0,
        "p10": p10,
        "p25": p25,
        "p50": p50,
        "p75": p75,
        "p90": p90,
    }


def compute_market_diagnostic(
    population: pd.DataFrame,
    *,
    sign_convention: dict[str, Any],
    accounting: dict[str, Any],
    market_provenance: dict[str, Any],
) -> dict[str, Any]:
    """Compute the full paired V5-vs-market diagnostic evidence block."""
    targets: dict[str, Any] = {}
    for target in TARGETS:
        rows = population[population["target"] == target].copy()
        if rows.empty:
            raise MarketDiagnosticError(f"No population rows for {target!r}")
        v5_pred = rows["prediction"].to_numpy(float)
        market_pred = rows["market_implied"].to_numpy(float)
        actual = rows["actual"].to_numpy(float)

        block: dict[str, Any] = {
            "overall": _paired_metrics(v5_pred, market_pred, actual),
            "edge_v5_minus_market": _edge_distribution(v5_pred, market_pred),
        }
        stages: dict[str, Any] = {}
        for stage in (0, 1, 2, 3):
            key = str(stage)
            leg = rows[rows["completed_games"] == stage]
            if leg.empty:
                stages[key] = {"n": 0}
            else:
                stages[key] = _paired_metrics(
                    leg["prediction"].to_numpy(float),
                    leg["market_implied"].to_numpy(float),
                    leg["actual"].to_numpy(float),
                )
        leg4 = rows[rows["completed_games"] >= 4]
        stages["4_plus"] = (
            _paired_metrics(
                leg4["prediction"].to_numpy(float),
                leg4["market_implied"].to_numpy(float),
                leg4["actual"].to_numpy(float),
            )
            if not leg4.empty
            else {"n": 0}
        )
        block["by_completed_game_stage"] = stages
        targets[target] = block

    return {
        "study_season": STUDY_SEASON,
        "targets": targets,
        "population": accounting,
        "sign_convention": sign_convention,
        "market": market_provenance,
        "permitted_use": PERMITTED_USE,
        "line_semantics": LINE_SEMANTICS,
        "closing_line_evidence": False,
        "production_activation_authorized": False,
        "readiness_recommendation": None,
        "v4_comparison": None,
    }


# ---------------------------------------------------------------------------
# Report rendering (Task 2)
# ---------------------------------------------------------------------------


def render_report(
    diagnostic_evidence: dict[str, Any],
    *,
    run_id: str,
    manifest_uri: str,
    manifest_raw_sha256: str,
) -> str:
    """Render the diagnostic Markdown report with mandatory labeling."""
    targets = diagnostic_evidence.get("targets", {})
    pop = diagnostic_evidence.get("population", {})
    sign = diagnostic_evidence.get("sign_convention", {})
    market = diagnostic_evidence.get("market", {})

    def _fmt(m: dict[str, Any]) -> str:
        if m.get("n", 0) == 0:
            return "  _No observations_"
        lo, hi = m["mae_delta_ci95"]
        return "\n".join(
            [
                f"  - N: {m['n']}",
                f"  - V5 MAE / RMSE / bias: {m['v5_mae']:.3f} / "
                f"{m['v5_rmse']:.3f} / {m['v5_bias']:+.3f}",
                f"  - Market MAE / RMSE / bias: {m['market_mae']:.3f} / "
                f"{m['market_rmse']:.3f} / {m['market_bias']:+.3f}",
                f"  - MAE delta (market − V5): {m['mae_delta_market_minus_v5']:+.3f} "
                f"95% CI [{lo:+.3f}, {hi:+.3f}]",
                f"  - Closer counts — V5: {m['v5_closer']}, "
                f"market: {m['market_closer']}, ties: {m['ties']}",
            ]
        )

    sections = [
        "# V5 2025 Market-Line Diagnostic",
        "",
        "> **Permitted use:** `diagnostic_comparison_only`  ",
        "> **Line semantics:** `provider_recorded_lines_postseason_capture` — "
        "these are provider-recorded lines captured post-season, NOT authentic "
        "timestamped pre-kickoff quotes. This report is NOT closing-line or CLV "
        "evidence.  ",
        "> **Production activation authorized:** false  ",
        "> **Readiness recommendation:** none — diagnostic comparison only; no "
        "effect on any gate, eligibility, Contract 11/12, or the 04/04B lifecycle.  ",
        "> **V4 comparison:** none  ",
        "",
        "## Entry identities",
        "",
        f"- Forecast entry record: `{VERIFICATION_MANIFEST_URI}` "
        "(11A-verified, SHA-pinned)",
        f"- Market dataset: `{market.get('dataset')}` version "
        f"`{market.get('version_id')}` (content SHA "
        f"`{market.get('content_sha')}`)",
        f"- Market dataset URI: `{market.get('uri')}`",
        f"- Replay input-ref agreement: `{market.get('replay_ref_agreement')}`",
        f"- Catalog state: `{market.get('catalog_state')}` "
        "(read-only lookup; quarantine untouched)",
        f"- Snapshot policy: `{market.get('policy')}`",
        "",
        "## Sign-convention validation",
        "",
        f"- Rows checked: {sign.get('n', '?')}",
        f"- r(V5 prediction, market-implied): {sign.get('r_pred_market', float('nan')):.3f}",
        f"- r(V5 actual, V5 prediction): {sign.get('r_actual_pred', float('nan')):.3f}",
        f"- r(V5 actual, market-implied): {sign.get('r_actual_market', float('nan')):.3f}",
        f"- Gates: `{sign.get('gates')}`",
        "",
        "## Population accounting (2025)",
        "",
    ]
    for target in TARGETS:
        t_pop = (pop.get("per_target") or {}).get(target, {})
        sections += [
            f"### {target}",
            "",
            f"- V5 2025 games: {t_pop.get('v5_games', '?')}",
            f"- Lined games: {t_pop.get('lined_games', '?')}",
            f"- Intersection games: {t_pop.get('intersection_games', '?')}",
            f"- Excluded (unlined, mostly FBS-FCS): "
            f"{t_pop.get('excluded_unlined_count', '?')}",
            "",
        ]

    for target in TARGETS:
        t_data = targets.get(target, {})
        edge = t_data.get("edge_v5_minus_market", {})
        sections += [
            f"## Target: {target}",
            "",
            "### Overall (intersection)",
            "",
            _fmt(t_data.get("overall", {})),
            "",
            "### Edge distribution (V5 − market-implied, descriptive only)",
            "",
            f"  - mean: {edge.get('mean', float('nan')):+.3f}, "
            f"sd: {edge.get('sd', float('nan')):.3f}",
            f"  - deciles p10/p25/p50/p75/p90: "
            f"{edge.get('p10', float('nan')):+.2f} / "
            f"{edge.get('p25', float('nan')):+.2f} / "
            f"{edge.get('p50', float('nan')):+.2f} / "
            f"{edge.get('p75', float('nan')):+.2f} / "
            f"{edge.get('p90', float('nan')):+.2f}",
            "",
            "### By completed-game stage",
            "",
        ]
        for stage_key in ("0", "1", "2", "3", "4_plus"):
            label = f"Stage {stage_key}" if stage_key != "4_plus" else "Stage 4+"
            sections.append(f"**{label}:**")
            sections.append(
                _fmt(t_data.get("by_completed_game_stage", {}).get(stage_key, {}))
            )
            sections.append("")

    sections += [
        "## Evidence provenance",
        "",
        f"- Run ID: `{run_id}`",
        f"- Diagnostic manifest URI: `{manifest_uri}`",
        f"- Diagnostic manifest raw SHA-256: `{manifest_raw_sha256}`",
        "",
        "---",
        "_This report is diagnostic comparison evidence only, computed from "
        "provider-recorded lines captured post-season. It is not closing-line "
        "or CLV evidence, not readiness evidence, not 2026 authorization, not "
        "a V4 comparison, and not prospective forecasting permission._",
        "",
    ]
    return "\n".join(sections)
