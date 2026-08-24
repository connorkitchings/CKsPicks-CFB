## Session Log Summary

This document provides a high-level, chronological summary of the key development activities for the `cfb_model` project, compiled from individual session logs.

---

### October 2025: Kelly Sizing, Risk Caps, and Ops Utilities

- Kelly-based bet sizing implemented (fractional 25%) with a 5% single-bet cap; confidence filters defaulted to spreads ≤ 3.0 and totals ≤ 1.5 using ensemble std-dev.
- Weekly generator updated with per-model feature alignment and report columns for Kelly and unit sizing; docs updated.
- Added bankroll simulation script and weekly report driver with spread vs total hit/bet breakdown.
- Storage fixes: LocalStorage path composition corrected; persist partition standardized to `game_id`.
- Health: Lint clean; tests (15) passing; docs build clean.

### January - August 2025: Project Setup, Data Ingestion & Architecture Pivot

- **Initial Setup & API Integration (Early August)**
  - Resolved all environment and dependency issues (`uv.lock`, `pyproject.toml`).
  - Established connection to the CollegeFootballData.com API and began extracting data schemas for games, plays, drives, and other key entities.
  - Initial data ingestion scripts were created, focusing on FBS/year-specific filtering.

- **Architectural Pivot to Local Storage (Mid-August)**
  - **Decision**: Moved away from a Supabase backend to a local, partitioned data storage system to simplify the architecture and reduce external dependencies.
  - Implemented a `LocalStorage` backend using CSV files (initially Parquet, then standardized to CSV for easier inspection).
  - Data is partitioned by `year`, `week`, and `game_id` as appropriate for each entity. Each partition includes a `manifest.json` for validation.
  - All ingestion scripts were refactored to use this new local storage backend.

- **Completion of Historical Data Ingestion (Mid-August)**
  - Systematically ingested all historical data for core entities (plays, games, teams, etc.) for the entire project scope (2014-2024, excluding 2020).
  - Overcame API rate limits and database timeouts by implementing efficient batching strategies.

- **Documentation & Feature Engineering Planning (Mid-August)**
  - Aligned all project documentation (`README.md`, `project_charter.md`, etc.) with the new local storage architecture.
  - Finalized the feature engineering plan, defining the multi-stage aggregation pipeline (plays -> drives -> games -> season) and the iterative opponent-adjustment algorithm.

---

### September 2025: Feature Engineering, Validation, and Initial Modeling

- **Core Aggregation Pipeline (Early September)**
  - Implemented the full pre-aggregation pipeline in `src/cfb_model/data/aggregations/`, transforming raw play-by-play data into team-game and team-season level features.
  - Fixed a critical bug in the time-remaining calculation, ensuring all time-based features are accurate.
  - Implemented deep semantic validation checks to ensure data quality and consistency across all aggregation layers.
  - Re-ran the entire aggregation pipeline for all historical years to generate a clean, validated, and feature-rich dataset.

- **Advanced Feature Engineering (Mid-September)**
  - Implemented several advanced feature sets:
    - **PPA-based Luck Factor**: To identify teams outperforming or underperforming their play-by-play stats.
    - **Deeper Rushing Analysis**: `line_yards`, `power_success_rate`, `second_level_yards`, and `open_field_yards`.
    - **Advanced Drive Analysis**: `successful`, `busted`, and `explosive` drive rates.
    - **Granular Special Teams Metrics**: `net_punt_yards` and field goal success rates by distance.

- **Initial Modeling & Critical Bug Fix (Late September)**
  - **Data Leakage Prevention**: Implemented strict point-in-time feature generation (`generate_point_in_time_features`) to ensure models are trained only on historical data, preventing a critical form of data leakage.
  - **Critical Bug Fix**: Discovered and fixed a fundamental flaw in the spread betting logic. The model was incorrectly comparing its predicted margin to the raw spread line instead of the expected margin, leading to artificially inflated performance.
  - **Realistic Baseline**: After fixing the logic, a true baseline model performance was established at a **51.7% hit rate**, just below the profitability threshold.

- **Pipeline Optimization & Refinement (Late September)**
  - Refactored the weekly prediction pipeline to use a pre-calculated cache of weekly stats, dramatically improving performance.
  - Consolidated multiple CLI scripts into a single, unified entry point (`scripts/cli.py`) for better usability.
  - Implemented a no-leakage, training-derived calibration system to correct for week-of-season biases.
  - Based on analysis, the default betting edge thresholds were updated to **6.0** for both spreads and totals.
