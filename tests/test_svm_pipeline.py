"""Tests for the SVM pipeline module using synthetic data (no real WESAD data)."""

import numpy as np
import pytest
from sklearn.pipeline import Pipeline

from stress_detection.models.svm import build_pipeline, evaluate, tune_svm


def _make_separable_data(n_per_class: int = 100, n_features: int = 2, seed: int = 0):
    """Return (X, y) with a clear linear boundary so the SVM can hit >90% accuracy."""
    rng = np.random.default_rng(seed)
    X0 = rng.normal(loc=-2.0, scale=0.5, size=(n_per_class, n_features))
    X1 = rng.normal(loc=+2.0, scale=0.5, size=(n_per_class, n_features))
    X = np.vstack([X0, X1])
    y = np.array([0] * n_per_class + [1] * n_per_class)
    return X, y


def _make_group_array(n_per_class: int = 100, n_subjects: int = 5):
    """Return group labels cycling over n_subjects for n_per_class*2 samples."""
    total = n_per_class * 2
    return np.tile(np.arange(n_subjects), total // n_subjects + 1)[:total]


class TestBuildPipeline:
    def test_returns_pipeline(self):
        p = build_pipeline()
        assert isinstance(p, Pipeline)

    def test_pipeline_steps(self):
        p = build_pipeline()
        step_names = [name for name, _ in p.steps]
        assert step_names == ["scaler", "svc"]

    def test_pipeline_fits_and_predicts(self):
        X, y = _make_separable_data()
        p = build_pipeline()
        p.fit(X, y)
        preds = p.predict(X)
        assert len(preds) == len(y)

    def test_pipeline_predict_proba(self):
        X, y = _make_separable_data()
        p = build_pipeline()
        p.fit(X, y)
        proba = p.predict_proba(X)
        assert proba.shape == (len(y), 2)
        assert np.allclose(proba.sum(axis=1), 1.0)


class TestTuneSvm:
    def test_returns_fitted_pipeline_and_dict(self):
        X, y = _make_separable_data()
        # Use a small grid to keep tests fast
        grid = {"svc__C": [1.0], "svc__gamma": ["scale"]}
        pipeline, cv_results = tune_svm(X, y, param_grid=grid)
        assert isinstance(pipeline, Pipeline)
        assert isinstance(cv_results, dict)
        assert "mean_test_score" in cv_results

    def test_fitted_pipeline_predicts(self):
        X, y = _make_separable_data()
        grid = {"svc__C": [1.0], "svc__gamma": ["scale"]}
        pipeline, _ = tune_svm(X, y, param_grid=grid)
        preds = pipeline.predict(X)
        assert len(preds) == len(y)

    def test_with_groups_uses_group_cv(self):
        X, y = _make_separable_data(n_per_class=50)
        groups = _make_group_array(n_per_class=50, n_subjects=5)
        grid = {"svc__C": [1.0], "svc__gamma": ["scale"]}
        pipeline, _ = tune_svm(X, y, groups=groups, param_grid=grid)
        assert isinstance(pipeline, Pipeline)


class TestEvaluate:
    def test_returns_expected_keys(self):
        X, y = _make_separable_data()
        p = build_pipeline()
        metrics = evaluate(p, X, y)
        expected_keys = {
            "accuracy_mean", "accuracy_std",
            "macro_f1_mean", "macro_f1_std",
            "weighted_f1_mean",
            "precision_per_class", "recall_per_class", "f1_per_class",
            "confusion_matrix", "n_folds",
        }
        assert expected_keys.issubset(metrics.keys())

    def test_accuracy_reasonable_on_separable_data(self):
        X, y = _make_separable_data()
        p = build_pipeline()
        metrics = evaluate(p, X, y)
        assert metrics["accuracy_mean"] > 0.85

    def test_confusion_matrix_shape(self):
        X, y = _make_separable_data()
        p = build_pipeline()
        metrics = evaluate(p, X, y)
        cm = metrics["confusion_matrix"]
        assert len(cm) == 2 and len(cm[0]) == 2

    def test_loso_with_groups(self):
        X, y = _make_separable_data(n_per_class=50)
        groups = _make_group_array(n_per_class=50, n_subjects=5)
        p = build_pipeline()
        metrics = evaluate(p, X, y, groups=groups)
        assert metrics["n_folds"] == 5
        assert 0.0 <= metrics["macro_f1_mean"] <= 1.0
