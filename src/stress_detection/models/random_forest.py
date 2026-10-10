"""Random Forest base model.

No StandardScaler: trees split on thresholds and are invariant to any monotone
rescaling of a feature, so a scaler would add cost and a serialisation layer
without changing a single split. (The SVM and MLP modules *do* scale - they
need it.) The estimator satisfies the common contract directly:
``fit`` / ``predict`` / ``predict_proba`` with P(stress) in column 1.

Forest size is deliberately capped at a few hundred trees. On ~5.5k windows and
18 features the validation curve is flat well before that, and the forest has to
stay cheap enough to sit inside a nested LOSO loop (16 outer folds x inner grid
search) and to answer inside the 5 s real-time cadence.
"""

from __future__ import annotations

from typing import Any

from sklearn.ensemble import RandomForestClassifier

from .common import RANDOM_SEED

_DEFAULTS: dict[str, Any] = {
    "n_estimators": 300,
    "max_depth": None,
    "min_samples_split": 2,
    "min_samples_leaf": 1,
    "max_features": "sqrt",
    "random_state": RANDOM_SEED,
    "n_jobs": -1,
}

# Full grid for the deployed artifact - all five knobs the brief asks for.
# 2*2*2*2*2 = 32 candidates; at ~1 s per fit x 5 grouped folds that is a couple
# of minutes, which is the right budget for a one-off deployment fit.
PARAM_GRID: dict[str, list] = {
    "n_estimators": [200, 300],
    "max_depth": [None, 12],
    "min_samples_split": [2, 10],
    "min_samples_leaf": [1, 4],
    "max_features": ["sqrt", 0.5],
}

# Compact grid re-run inside every outer LOSO fold. Depth and leaf size are the
# two knobs that actually move macro-F1 at this sample size; n_estimators and
# max_features are held at the defaults above to keep 16 nested folds cheap.
COMPACT_PARAM_GRID: dict[str, list] = {
    "max_depth": [None, 12],
    "min_samples_leaf": [1, 4],
}


def build_random_forest(**overrides: Any) -> RandomForestClassifier:
    """Return an unfitted RandomForestClassifier with project defaults."""
    params = dict(_DEFAULTS)
    params.update(overrides)
    return RandomForestClassifier(**params)
