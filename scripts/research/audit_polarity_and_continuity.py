"""Diagnostic Polarity Audit & Continuity Probe for V6 Ratings Lab.

Reads persisted corpus and features stages from research storage:
1. Calculates Pearson correlation between each of the 16 multi-factor rating columns
   and actual_margin (home_points - away_points) & actual_total (home_points + away_points).
2. Diagnoses defense space (allowed-rate space vs quality space).
3. Inspects corpus.lower_level_refs across all seasons to probe continuity records.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from cks_picks_cfb.ratings_lab.artifacts import (
    open_research_storage,
)
from cks_picks_cfb.ratings_lab.corpus import load_persisted_corpus
from cks_picks_cfb.ratings_lab.evaluation import FOUR_FACTOR_CORE_IDS
from cks_picks_cfb.ratings_lab.stages import read_frame_stage


def main() -> None:
    load_dotenv()
    for name in ("BUCKET", "ACCOUNT_ID", "ACCESS_KEY", "SECRET_KEY", "ENDPOINT"):
        if not os.getenv(f"CFB_R2_LAB_SOURCE_{name}") and os.getenv(f"CFB_R2_{name}"):
            os.environ[f"CFB_R2_LAB_SOURCE_{name}"] = os.environ[f"CFB_R2_{name}"]

    if not os.getenv("CFB_LAB_LOCAL_ROOT"):
        os.environ["CFB_LAB_LOCAL_ROOT"] = os.path.expanduser("~/cfb_ratings_lab_v6")

    storage = open_research_storage()
    print(f"[*] Research storage initialized: output={storage.output.identity}")

    # Find persisted manifests
    local_output = Path(os.environ["CFB_LAB_LOCAL_ROOT"]) / "output"
    corpus_manifests = list(local_output.glob("ratings-lab/v1/runs/*/corpus.json"))
    features_manifests = list(local_output.glob("ratings-lab/v1/runs/*/features.json"))

    if not corpus_manifests or not features_manifests:
        raise FileNotFoundError("Missing persisted corpus or features stage manifest")

    corpus_path = corpus_manifests[0].relative_to(local_output)
    features_path = features_manifests[0].relative_to(local_output)

    print(f"[*] Reading corpus from {corpus_path}...")
    corpus_ref, _ = storage.stage_at(str(corpus_path))
    corpus = load_persisted_corpus(storage, corpus_ref)

    print(f"[*] Reading features from {features_path}...")
    features_ref, _ = storage.stage_at(str(features_path))
    features = read_frame_stage(storage, features_ref, stage="features")

    print(f"[*] Features columns ({len(features.columns)}):", list(features.columns))
    print(f"[*] Outcomes columns ({len(corpus.outcomes.columns)}):", list(corpus.outcomes.columns))
    # Merge with outcomes for actual_margin and actual_total
    print(f"[*] Merging features ({len(features)} rows) with outcomes...")
    merged = features.merge(
        corpus.outcomes,
        on=["season", "game_id"],
        how="inner",
        suffixes=("", "_outcome"),
    )
    merged = merged[merged["completed"] == 1].copy()
    merged["actual_margin"] = merged["home_points"] - merged["away_points"]
    merged["actual_total"] = merged["home_points"] + merged["away_points"]

    print(f"[*] Evaluating correlations on {len(merged)} completed games...")

    # The 16 rating columns
    columns_16 = []
    for side in ("home", "away"):
        for role in ("offense", "defense"):
            for mid in FOUR_FACTOR_CORE_IDS:
                columns_16.append(f"{side}_{role}__{mid}")

    records = []
    for col in columns_16:
        if col not in merged.columns:
            records.append({
                "column": col,
                "corr_margin": float("nan"),
                "corr_total": float("nan"),
                "status": "MISSING",
            })
            continue
        corr_m = float(merged[col].corr(merged["actual_margin"]))
        corr_t = float(merged[col].corr(merged["actual_total"]))
        records.append({
            "column": col,
            "corr_margin": corr_m,
            "corr_total": corr_t,
        })

    print("\n" + "=" * 80)
    print("POLARITY AUDIT CORRELATION TABLE (Pearson r against actual_margin & actual_total)")
    print("=" * 80)
    print(f"{'Feature Column':<42} | {'r (actual_margin)':<18} | {'r (actual_total)':<18}")
    print("-" * 80)
    for r in records:
        print(f"{r['column']:<42} | {r['corr_margin']:>17.4f}  | {r['corr_total']:>17.4f}")
    print("=" * 80)

    # Polarity Verdict
    # Expected under allowed-rate space (lower=better):
    # home_offense > 0, away_offense < 0, home_defense < 0, away_defense > 0
    home_off = [r["corr_margin"] for r in records if "home_offense" in r["column"]]
    away_off = [r["corr_margin"] for r in records if "away_offense" in r["column"]]
    home_def = [r["corr_margin"] for r in records if "home_defense" in r["column"]]
    away_def = [r["corr_margin"] for r in records if "away_defense" in r["column"]]

    avg_ho = sum(home_off) / len(home_off)
    avg_ao = sum(away_off) / len(away_off)
    avg_hd = sum(home_def) / len(home_def)
    avg_ad = sum(away_def) / len(away_def)

    print("\n--- Summary Averages ---")
    print(f"Average home_offense r(margin): {avg_ho:+.4f} (expected +)")
    print(f"Average away_offense r(margin): {avg_ao:+.4f} (expected -)")
    print(f"Average home_defense r(margin): {avg_hd:+.4f} (if allowed space: - ; if quality space: +)")
    print(f"Average away_defense r(margin): {avg_ad:+.4f} (if allowed space: + ; if quality space: -)")

    if avg_hd < 0 and avg_ad > 0:
        verdict = "CONFIRMED: Defensive columns live in raw ALLOWED-RATE space (lower=better). Bridge B's (home_off - away_def) inverted defensive effect."
    elif avg_hd > 0 and avg_ad < 0:
        verdict = "REJECTED: Defensive columns live in QUALITY space (higher=better)."
    else:
        verdict = f"AMBIGUOUS: Mixed signs (home_def={avg_hd:+.4f}, away_def={avg_ad:+.4f})."

    print("\nVERDICT LINE:")
    print(verdict)
    print("=" * 80 + "\n")

    # 3. Continuity Probe
    print("=" * 80)
    print("CONTINUITY PROBE (Inspecting corpus.lower_level_refs)")
    print("=" * 80)
    refs = getattr(corpus, "lower_level_refs", {})
    print(f"lower_level_refs seasons count: {len(refs)}")
    for season in sorted(refs.keys()):
        s_refs = refs[season]
        keys = list(s_refs.keys())
        print(f"Season {season} dataset keys ({len(keys)}): {keys}")
        for k in ("returning_production", "recruiting", "coaching"):
            if k in s_refs:
                print(f"  -> {k}: {s_refs[k]}")
            else:
                print(f"  -> {k}: NOT FOUND in season {season} refs")
    print("=" * 80)


if __name__ == "__main__":
    main()
