from typing import Dict, Optional

import arviz as az
import numpy as np
import pandas as pd
import pymc as pm


class ProbabilisticPowerRating:
    def __init__(self, team_to_idx: Dict[str, int], idx_to_team: Dict[int, str]):
        self.team_to_idx = team_to_idx
        self.idx_to_team = idx_to_team
        self.n_teams = len(team_to_idx)
        self.model = None
        self.trace = None

    def fit(
        self,
        df: pd.DataFrame,
        draws: int = 1000,
        tune: int = 1000,
        chains: int = 2,
        random_seed: int = 42,
        use_team_hfa: bool = False,
        recency_weight: Optional[float] = None,
    ):
        """
        Fits the Bayesian Hierarchical Model.

        Args:
            use_team_hfa: If True, model HFA per team.
            recency_weight: If provided (e.g. 0.1), weights games by exp(-weight * weeks_ago).
                            Implemented by scaling sigma: sigma_g = sigma / sqrt(weight_g).
        """
        home_idx = df["home_id"].values
        away_idx = df["away_id"].values
        home_points = df["home_points"].values
        away_points = df["away_points"].values
        neutral_site = df["neutral_site"].values.astype(int)

        # Calculate weights if recency is used
        weights = np.ones(len(df))
        if recency_weight is not None:
            max_week = df["week"].max()
            weeks_ago = max_week - df["week"].values
            # Weight = exp(-decay * weeks_ago)
            # e.g. decay=0.1, 5 weeks ago -> exp(-0.5) = 0.60
            weights = np.exp(-recency_weight * weeks_ago)

        # Sigma scaling: higher sigma for older games (lower weight)
        # sigma_observed = sigma_score / sqrt(weight)
        # This effectively reduces the precision of older observations.
        sigma_scale = 1.0 / np.sqrt(weights)

        # HFA applies only if NOT neutral
        # We model HFA as a constant added to home team
        # hfa_effect = hfa * (1 - neutral_site)

        with pm.Model() as self.model:
            # Global parameters
            base_score = pm.Normal("base_score", mu=28, sigma=5)
            sigma_score = pm.HalfNormal("sigma_score", sigma=10)

            # HFA
            if use_team_hfa:
                # Hierarchical HFA
                mu_hfa = pm.Normal("mu_hfa", mu=2.5, sigma=1)
                sigma_hfa = pm.HalfNormal("sigma_hfa", sigma=1)
                hfa = pm.Normal("hfa", mu=mu_hfa, sigma=sigma_hfa, shape=self.n_teams)
                hfa_term = hfa[home_idx] * (1 - neutral_site)
            else:
                hfa = pm.Normal("hfa", mu=2.5, sigma=1)
                hfa_term = hfa * (1 - neutral_site)

            # Hierarchical priors for team strength
            tau_off = pm.HalfNormal("tau_off", sigma=10)
            tau_def = pm.HalfNormal("tau_def", sigma=10)

            # Team-specific parameters (centered parameterization for now)
            off_rating = pm.Normal(
                "off_rating", mu=0, sigma=tau_off, shape=self.n_teams
            )
            def_rating = pm.Normal(
                "def_rating", mu=0, sigma=tau_def, shape=self.n_teams
            )

            # Expected scores
            # Note: Def rating is "points allowed", so positive is BAD for defense?
            # Let's define: mu = Base + Off - Def.
            # If Def is "strength", it should be minus. If Def is "weakness", it should be plus.
            # Standard convention: Higher rating = Better.
            # So: mu = Base + Off_own - Def_opp.
            # If Def_opp is high (good defense), score should go DOWN. So minus is correct.

            mu_home = (
                base_score + off_rating[home_idx] - def_rating[away_idx] + hfa_term
            )
            mu_away = base_score + off_rating[away_idx] - def_rating[home_idx]

            # Likelihood with weighted sigma
            pm.Normal(
                "obs_home",
                mu=mu_home,
                sigma=sigma_score * sigma_scale,
                observed=home_points,
            )
            pm.Normal(
                "obs_away",
                mu=mu_away,
                sigma=sigma_score * sigma_scale,
                observed=away_points,
            )

            # Sampling
            self.trace = pm.sample(
                draws=draws,
                tune=tune,
                chains=chains,
                random_seed=random_seed,
                progressbar=True,
            )

    def get_ratings(self) -> pd.DataFrame:
        """Returns a DataFrame of mean ratings."""
        if self.trace is None:
            raise ValueError("Model not fitted yet.")

        summary = az.summary(self.trace, var_names=["off_rating", "def_rating"])

        ratings = []
        for i in range(self.n_teams):
            team = self.idx_to_team[i]
            off_mean = summary.loc[f"off_rating[{i}]", "mean"]
            def_mean = summary.loc[f"def_rating[{i}]", "mean"]
            # Net rating = Off + Def (assuming Def is subtracted from opponent, so high Def is good)
            # Wait, in the formula: mu = ... - Def_opp.
            # So high Def reduces opponent score. Yes, high Def is good.
            net = off_mean + def_mean
            ratings.append(
                {
                    "team": team,
                    "off_rating": off_mean,
                    "def_rating": def_mean,
                    "net_rating": net,
                }
            )

        return pd.DataFrame(ratings).sort_values("net_rating", ascending=False)

    def predict_spread(
        self, home_team: str, away_team: str, neutral: bool = False
    ) -> Dict[str, float]:
        """
        Predicts spread (Home - Away) distribution stats.
        Returns: mean, std, p_home_cover (vs 0), etc.
        """
        if self.trace is None:
            raise ValueError("Model not fitted yet.")

        if home_team not in self.team_to_idx or away_team not in self.team_to_idx:
            return None  # Unknown team

        h_idx = self.team_to_idx[home_team]
        a_idx = self.team_to_idx[away_team]

        posterior = self.trace.posterior

        base = posterior["base_score"].values.flatten()
        hfa = posterior[
            "hfa"
        ].values  # Shape: (chains, draws) or (chains, draws, n_teams)
        off_h = posterior["off_rating"][:, :, h_idx].values.flatten()
        def_h = posterior["def_rating"][:, :, h_idx].values.flatten()
        off_a = posterior["off_rating"][:, :, a_idx].values.flatten()
        def_a = posterior["def_rating"][:, :, a_idx].values.flatten()

        # Handle HFA shape
        if hfa.ndim > 2:  # Team-specific HFA: (chains, draws, n_teams)
            hfa_val = hfa[:, :, h_idx].flatten()
        else:  # Global HFA: (chains, draws)
            hfa_val = hfa.flatten()

        hfa_effect = hfa_val if not neutral else 0

        mu_h = base + off_h - def_a + hfa_effect
        mu_a = base + off_a - def_h

        margin = mu_h - mu_a  # Home margin
        total = mu_h + mu_a

        return {
            "pred_spread": np.mean(margin),  # Predicted margin (Home - Away)
            "pred_spread_std": np.std(margin),
            "pred_total": np.mean(total),
            "pred_total_std": np.std(total),
            "prob_home_win": np.mean(margin > 0),
            "home_score": np.mean(mu_h),
            "away_score": np.mean(mu_a),
        }
