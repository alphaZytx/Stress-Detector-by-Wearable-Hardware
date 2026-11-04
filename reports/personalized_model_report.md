# Personalized Extra Trees Model — v3

## Outcome

The calibrated model reached **95.65% pooled accuracy** under nested
leave-one-subject-out evaluation and is now the configured deployment model.
The previous Soft Voting ensemble remains bundled as the automatic fallback
when no complete user calibration is available.

| Metric | Personalized Extra Trees |
|---|---:|
| Accuracy | 0.9565 |
| Macro-F1 | 0.9530 |
| Stress F1 | 0.9401 |
| ROC-AUC | 0.9938 |
| Confusion matrix | `[[3119, 40], [181, 1735]]` |

## Protocol

- Dataset: 15 WESAD wrist subjects.
- Hardware-compatible inputs: derived heart rate, EDA/GSR, and skin temperature.
- Calibration: first 120 seconds of each known resting block.
- Calibration windows: excluded from fitting and scoring.
- Representation: heart-rate and GSR magnitudes divided by their personal
  resting means; temperature mean expressed as a resting delta.
- Evaluation: nested leave-one-subject-out. Each outer fold tuned Extra Trees
  only with the other subjects using four-fold grouped cross-validation.
- Threshold: fixed at `P(stress) >= 0.5`; it was not selected on held-out data.

## Deployment behavior

`personalized_extra_trees_wesad_v3.joblib` contains both the calibrated Extra
Trees estimator and the v2 Soft Voting fallback. The inference engine enables
Extra Trees only when HR, GSR, and object-temperature baselines are all present
and non-zero. Raw sensor features can therefore never be accidentally sent to
the relative-feature model.

## Important limitations

- This is a WESAD result, not measured accuracy on the project's physical rig.
- WESAD uses an Empatica E4 on the wrist; the project uses different sensors,
  placement, temperature measurement, and GSR electronics.
- Performance still varies by person: the weakest held-out subject had 77.7%
  accuracy even though pooled accuracy exceeded 95%.
- Resting calibration reduces positive scale differences, but it cannot repair
  reversed GSR polarity, motion artefacts, poor finger contact, or bad labels.
- This is a stress-screening project result, not a medical diagnosis.

Reproduce the complete training and evaluation run with:

```bash
.venv/bin/python scripts/train_personalized_model.py --version v3
```

Machine-readable outputs are in
`metrics_personalized_extra_trees_v3.json`,
`personalized_extra_trees_holdout_v3.csv`, and
`personalized_extra_trees_folds_v3.json`.
