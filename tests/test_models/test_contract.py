"""Project-wide model invariants that are not per-model (§4)."""

from __future__ import annotations

import numpy as np
import pytest

from stress_detection.models.common import (
    BASE_MODEL_NAMES,
    CLASS_NAMES,
    LABEL_MAP,
    RANDOM_SEED,
    build_model,
    grouped_cv,
    stress_proba,
)


def test_single_label_convention():
    """0 = baseline, 1 = stress, everywhere. No second convention exists."""
    assert LABEL_MAP == {"baseline": 0, "stress": 1}
    assert CLASS_NAMES == {0: "baseline", 1: "stress"}


def test_base_model_order_is_fixed():
    """Stacking meta-features are positional; this order must not drift."""
    assert BASE_MODEL_NAMES == ("svm", "random_forest", "xgboost", "mlp")


def test_seed_is_fixed():
    assert RANDOM_SEED == 42


def test_unknown_model_name_raises():
    with pytest.raises(ValueError, match="Unknown model"):
        build_model("definitely_not_a_model")


def test_grouped_cv_needs_at_least_two_subjects():
    with pytest.raises(ValueError, match=r">= 2 subjects"):
        grouped_cv(np.array(["S1"] * 10))


def test_grouped_cv_never_splits_a_subject():
    groups = np.repeat([f"S{i}" for i in range(6)], 20)
    X = np.zeros((len(groups), 3))
    y = np.tile([0, 1], len(groups) // 2)
    for train_idx, test_idx in grouped_cv(groups, 3).split(X, y, groups):
        assert not set(groups[train_idx]) & set(groups[test_idx])


def test_stress_proba_rejects_a_model_without_the_stress_class():
    """A model fitted on one class has no P(stress) - say so, don't return P(baseline)."""

    class OneClass:
        classes_ = np.array([0])

        def predict_proba(self, X):
            return np.ones((len(X), 1))

    with pytest.raises(ValueError, match="without the stress class"):
        stress_proba(OneClass(), np.zeros((3, 22)))
