# Probabilistic Power Ratings (Research)

## Overview

**Probabilistic Power Ratings (PPR)** represent the next generation of modeling for the CFB project. While the current "Points-For" architecture relies on regression against game-level features, PPR aims to learn a latent "strength" distribution for each team that evolves over time.

> **Status**: Research / Prototype Phase
> **Target Deployment**: 2026 Season

## Core Concept

In a rating system (like Elo or Glicko), a team is represented by a single number (Rating). In a **Probabilistic** system, a team is represented by a **distribution** (e.g., a Gaussian $\mathcal{N}(\mu, \sigma^2)$).

- $\mu$ (Mu): The team's expected strength (how many points they are better than an average team).
- $\sigma$ (Sigma): The uncertainty or inconsistency of the team.

## Architecture Goals

1.  **Uncertainty Quantification**: We don't just want to know _who_ will win, but _how confident_ we are. A team with high $\sigma$ (e.g., a volatile team) should result in wider prediction intervals.
2.  **Bayesian Updating**: As new game results come in, we update our beliefs ($\mu$ and $\sigma$) about each team mathematically.
3.  **Spread-Specific Tuning**: Unlike generic power ratings (ESPN FPI, SP+), these ratings will be optimized specifically to maximize **Spread Betting ROI**.

## Proposed Methodology

### State-Space Models

We are exploring State-Space Models (SSM) or Kalman Filters to track latent strength.

- **State**: Team Strength vector at time $t$.
- **Observation**: Game Score Margin.
- **Transition**: Strength evolves from week to week (drift/mean reversion).

### Hierarchical Models

Alternatively, a Bayesian Hierarchical Model (using PyMC or Stan) could pool information across conferences or similar teams to improve estimates for teams with few data points.

## Integration with Betting

Once we have the posterior distribution of strength for Team A ($R_A$) and Team B ($R_B$), we can simulate the game outcome:

$$ \text{Margin} \sim \mathcal{N}(R_A - R_B, \text{GameNoise}) $$

This allows us to calculate:

- **Win Probability**: $P(\text{Margin} > 0)$
- **Cover Probability**: $P(\text{Margin} > \text{Line})$
- **Kelly Criterion**: Optimal bet sizing based on true probabilities.

## Current Progress

- Prototypes exist in `notebooks/research/`.
- Initial validation shows promise for "stable" teams but lags in reacting to "breakout" teams compared to the Points-For regression model.
