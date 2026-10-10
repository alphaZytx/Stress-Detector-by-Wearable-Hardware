# Current Model Summary

The deployed v4 model family was trained on 5,462 windows from 16 subjects using the current 18-feature contract: seven MAX30105 heart-rate features, eight GSR features, and three MLX90614 temperature features.

Artifacts:

- `svm_combined_v4.joblib`
- `rf_combined_v4.joblib`
- `xgb_combined_v4.joblib`
- `mlp_combined_v4.joblib`
- `ensemble_soft_v4.joblib`
- `ensemble_stack_v4.joblib`

`metrics_ensemble_artifacts_v4.json` records the training metadata and latency checks. Historical metrics from the retired sensor schema are not applicable to this hardware revision.
