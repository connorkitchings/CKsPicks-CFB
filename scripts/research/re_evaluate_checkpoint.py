"""Re-evaluate Bridge A and Bridge B on Persisted Ratings with Quality-Signed Frame.

Implements Fix 1 Checkpoint:
- Loads persisted ratings from research storage.
- Re-assembles multi-factor frame using quality-signed defensive columns and corrected sum formula.
- Evaluates Bridge A (alpha10_direct18) and Bridge B (alpha10_differentials).
- Compares against v5-common using 2,000 block bootstraps.
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv

from cks_picks_cfb.ratings_lab.artifacts import open_research_storage
from cks_picks_cfb.ratings_lab.contracts import Rating, RatingState
from cks_picks_cfb.ratings_lab.corpus import load_persisted_corpus
from cks_picks_cfb.ratings_lab.evaluation import (
    FOUR_FACTOR_CORE_IDS,
    common_bridge_predictions,
    frame_with_multifactor_states,
    paired_comparison,
    scorecard,
)
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

    # 1. Load persisted corpus
    corpus_ref, _ = storage.stage_at(
        "ratings-lab/v1/runs/fb0baf90841f51d42958665c/corpus.json"
    )
    corpus = load_persisted_corpus(storage, corpus_ref)
    print(f"[*] Loaded persisted corpus ({len(corpus.population)} games)")

    # 2. Load persisted ratings states
    ratings_ref, _ = storage.stage_at(
        "ratings-lab/v1/runs/d5b887aa804ff2b49c6a86e6/ratings.json"
    )
    ratings_df = read_frame_stage(storage, ratings_ref, stage="ratings")
    print(f"[*] Loaded {len(ratings_df):,} persisted rating rows")

    states = [
        RatingState(
            candidate_id=r.candidate_id,
            season=int(r.season),
            week=int(r.week),
            game_id=int(r.game_id),
            cutoff_utc=str(r.cutoff_utc),
            team=str(r.team),
            role=str(r.role),
            rating=Rating(float(r.rating_mean), float(r.rating_variance)),
            prior=Rating(float(r.prior_mean), float(r.prior_variance)),
            usable_exposure=float(r.usable_exposure),
            evidence_game_ids=tuple(map(int, str(r.evidence_game_ids).split(",")))
            if str(r.evidence_game_ids)
            else (),
            explanation=json.loads(r.explanation_json),
        )
        for r in ratings_df.itertuples(index=False)
    ]

    # 3. Assemble quality-signed feature frame
    print("[*] Re-assembling feature frame with quality-signed defense...")
    signed_frame = frame_with_multifactor_states(
        corpus, states, core_mids=FOUR_FACTOR_CORE_IDS
    )
    assert len(signed_frame) == 8935

    # 4. Check new correlations
    print("\n--- Post-Signing Correlation Check (Week >= 6, N=4,936) ---")
    w6 = signed_frame[signed_frame["week"] >= 6]
    for mid in FOUR_FACTOR_CORE_IDS:
        h_off_c = w6[f"home_offense__{mid}"].corr(w6["actual_margin"])
        h_def_c = w6[f"home_defense__{mid}"].corr(w6["actual_margin"])
        a_off_c = w6[f"away_offense__{mid}"].corr(w6["actual_margin"])
        a_def_c = w6[f"away_defense__{mid}"].corr(w6["actual_margin"])
        print(
            f"{mid:<24}: h_off={h_off_c:+.4f}, h_def={h_def_c:+.4f}, a_off={a_off_c:+.4f}, a_def={a_def_c:+.4f}"
        )

    # 5. Dual Bridge Evaluation
    print("\n[*] Evaluating Bridge A (alpha10_direct18) on signed frame...")
    preds_a = common_bridge_predictions(
        corpus,
        signed_frame,
        candidate_id="kalman_exposure_v1_direct18_signed",
        bridge="alpha10_direct18",
    )
    sc_a = scorecard(preds_a)

    print("[*] Evaluating Bridge B (alpha10_differentials) on signed frame...")
    preds_b = common_bridge_predictions(
        corpus,
        signed_frame,
        candidate_id="kalman_exposure_v1_differentials_signed",
        bridge="alpha10_differentials",
    )
    sc_b = scorecard(preds_b)

    # 6. Reference v5-common
    print("[*] Loading v5-common reference predictions...")
    v5_common_preds = common_bridge_predictions(
        corpus,
        corpus.v5_features,
        candidate_id="v5_common_alpha10_v1",
        bridge="v5_common",
    )
    sc_v5 = scorecard(v5_common_preds)

    # 7. Paired comparison
    print("[*] Running 2,000 paired block bootstraps...")
    comp_a = paired_comparison(
        preds_a, v5_common_preds, corpus, seed=20260928, samples=2000
    )
    comp_b = paired_comparison(
        preds_b, v5_common_preds, corpus, seed=20260928, samples=2000
    )

    print("\n" + "=" * 85)
    print("FIX 1 CHECKPOINT RESULTS: QUALITY-SIGNED FRAME VS V5-COMMON")
    print("=" * 85)
    print(
        f"{'Model / Bridge':<30} | {'Margin MAE':<11} | {'Gain vs V5':<11} | {'90% CI [lower, upper]':<22} | {'Total MAE':<10}"
    )
    print("-" * 85)
    print(
        f"{'V5 Reference (v5_common)':<30} | {sc_v5['pooled']['margin']['mae']:>10.4f}  | {'-':>10}  | {'-':>22} | {sc_v5['pooled']['total']['mae']:>9.4f}"
    )
    print(
        f"{'Bridge A (alpha10_direct18)':<30} | {sc_a['pooled']['margin']['mae']:>10.4f}  | {comp_a['paired']['margin']['mae_gain']:>+10.4f}  | [{comp_a['paired']['margin']['lower_90']:>8.4f}, {comp_a['paired']['margin']['upper_90']:>8.4f}] | {sc_a['pooled']['total']['mae']:>9.4f}"
    )
    print(
        f"{'Bridge B (alpha10_differentials)':<30} | {sc_b['pooled']['margin']['mae']:>10.4f}  | {comp_b['paired']['margin']['mae_gain']:>+10.4f}  | [{comp_b['paired']['margin']['lower_90']:>8.4f}, {comp_b['paired']['margin']['upper_90']:>8.4f}] | {sc_b['pooled']['total']['mae']:>9.4f}"
    )
    print("=" * 85)


if __name__ == "__main__":
    main()
