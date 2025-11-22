## 2025-11-21: Successful Walk-Forward Validation of CatBoost Spread Model
- **Context:** After multiple failed attempts to stabilize the linear models, the root cause was identified as a data quality issue in the feature engineering pipeline, specifically the handling of `NaN` values in special teams and trench warfare features for older seasons.
- **Decision:** A fix was implemented in `src/features/core.py` to handle `NaN` values more robustly by using `np.nansum` and clipping extreme values for punt yardage. The feature caches for 2019, 2021, and 2022 were rebuilt. A walk-forward validation was successfully run for the CatBoost spread model on the 2023 and 2024 seasons.
- **Rationale:** This successful run provides a reliable performance baseline for the CatBoost spread model on clean data, unblocking further development.
- **Impact:** The CatBoost spread model is now the official baseline. The overall RMSE for the 2023-2024 seasons is **18.57**. Future spread model improvements will be measured against this benchmark.
- **Rejected Alternatives:** None. This was the necessary next step to unblock the project.

## 2025-11-20: Final Investigation into Model Instability
- **Context:** Previous attempts to stabilize the linear models failed. A final, comprehensive attempt was made by fixing `NaN` propagation in the feature engineering code and using a robust training pipeline that dropped `NaN`s, pruned high-VIF features, and scaled the data.
- **Decision:** All modeling work on the spread prediction target is definitively paused. The next and only step is a manual, code-level audit and debugging of the feature engineering pipeline in `src/features/core.py`.
- **Rationale:** The final, robust training pipeline still produced `RuntimeWarning`s. This proves that the root cause is not simple multicollinearity or missing values that can be handled at the modeling stage. The problem is fundamental to the data generation process itself, which is creating extreme, non-physical values that break the linear algebra of the models.
- **Impact:** No reliable model can be trained until the feature engineering code is fixed. The project must pivot from modeling to a deep data quality and debugging session.
- **Rejected Alternatives:** All standard and advanced preprocessing techniques at the modeling stage have been exhausted. The problem is at the source.