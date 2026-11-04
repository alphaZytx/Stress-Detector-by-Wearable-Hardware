"""Personalized Extra Trees deployment model with a safe raw-data fallback."""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier

from .common import RANDOM_SEED


def build_personalized_extra_trees(**overrides) -> ExtraTreesClassifier:
    params = {
        "n_estimators": 600,
        "max_depth": None,
        "max_features": 1.0,
        "min_samples_leaf": 2,
        "class_weight": "balanced",
        "n_jobs": -1,
        "random_state": RANDOM_SEED,
    }
    params.update(overrides)
    return ExtraTreesClassifier(**params)


PERSONALIZED_PARAM_GRID = {
    "max_depth": [None, 16],
    "max_features": [0.5, 0.8, 1.0],
    "min_samples_leaf": [1, 2, 4],
}


class PersonalizedStressModel:
    """One portable artifact containing personalized and fallback estimators.

    ``predict_proba`` deliberately uses the raw-feature fallback. The inference
    engine calls ``predict_proba_personalized`` only after applying a complete
    120-second resting baseline. This prevents raw values from accidentally
    entering a model trained on relative features.
    """

    requires_complete_calibration = True

    def __init__(
        self,
        personalized_model,
        fallback_model,
        *,
        feature_names: list[str],
        fallback_model_type: str = "soft_voting",
        threshold: float = 0.5,
        metadata=None,
    ):
        self.personalized_model = personalized_model
        self.fallback_model = fallback_model
        self.fallback_model_type = fallback_model_type
        self.threshold = float(threshold)
        self.metadata = metadata
        self.classes_ = np.array([0, 1])
        self.feature_names_in_ = np.asarray(feature_names, dtype=object)
        self.n_features_in_ = len(feature_names)

    def _check(self, X) -> np.ndarray:
        values = np.asarray(X, dtype=float)
        if values.ndim != 2 or values.shape[1] != self.n_features_in_:
            raise ValueError(
                f"PersonalizedStressModel expects (*, {self.n_features_in_}), "
                f"got {values.shape}."
            )
        return values

    def predict_proba(self, X) -> np.ndarray:
        """Safe behavior without a complete baseline: use the raw fallback."""
        return np.asarray(self.fallback_model.predict_proba(self._check(X)))

    def predict_proba_personalized(self, X) -> np.ndarray:
        return np.asarray(self.personalized_model.predict_proba(self._check(X)))

    def predict(self, X) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= self.threshold).astype(int)

    def predict_personalized(self, X) -> np.ndarray:
        return (
            self.predict_proba_personalized(X)[:, 1] >= self.threshold
        ).astype(int)
