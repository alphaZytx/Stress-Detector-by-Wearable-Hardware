"""XGBoost base model.

Module name note: this file is ``stress_detection.models.xgboost``; the
``from xgboost import XGBClassifier`` below is an absolute import and therefore
resolves to the real third-party package, not to this module.

The import is deliberately lazy (inside the builder). xgboost is an optional
dependency with a native libomp requirement, and the FastAPI service running on
the SVM baseline must keep importing ``stress_detection.models`` even on a
machine where the wheel is absent.

``XGBClassifier`` already satisfies the common contract, with P(stress) in
``predict_proba(X)[:, 1]`` for the binary objective.
"""

from __future__ import annotations

from typing import Any

from .common import RANDOM_SEED

_DEFAULTS: dict[str, Any] = {
    "n_estimators": 300,
    "max_depth": 4,
    "learning_rate": 0.1,
    "subsample": 0.9,
    "colsample_bytree": 0.9,
    "min_child_weight": 1,
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    # "hist" is the fastest tree method at this data size and is deterministic
    # for a fixed seed, which §16 requires.
    "tree_method": "hist",
    "random_state": RANDOM_SEED,
    "n_jobs": -1,
}

# Full grid for the deployed artifact. 2*2*2*2*2*2 = 64 candidates - modest for
# ~5.5k windows and 18 features, where a single fit is well under a second.
PARAM_GRID: dict[str, list] = {
    "n_estimators": [200, 400],
    "max_depth": [3, 6],
    "learning_rate": [0.05, 0.1],
    "subsample": [0.8, 1.0],
    "colsample_bytree": [0.8, 1.0],
    "min_child_weight": [1, 5],
}

# Compact grid for the nested LOSO inner loop: depth and learning rate are the
# two parameters that trade off under-/over-fitting most sharply here.
COMPACT_PARAM_GRID: dict[str, list] = {
    "max_depth": [3, 6],
    "learning_rate": [0.05, 0.1],
}


def build_xgboost(**overrides: Any):
    """Return an unfitted XGBClassifier with project defaults."""
    try:
        from xgboost import XGBClassifier
    except ImportError as exc:  # pragma: no cover - depends on install
        raise ImportError(
            "xgboost is required for the 'xgboost' base model. "
            "Install it with: pip install 'xgboost>=2.0,<3.1' "
            "(macOS also needs `brew install libomp`)."
        ) from exc

    params = dict(_DEFAULTS)
    params.update(overrides)
    return XGBClassifier(**params)
