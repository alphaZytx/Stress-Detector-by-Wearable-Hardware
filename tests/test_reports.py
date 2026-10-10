"""Tests for eval/reports.py using synthetic models and labels (no real data)."""

import numpy as np
import pytest
from sklearn.pipeline import Pipeline

from stress_detection.eval.reports import feature_importance, per_class_metrics
from stress_detection.models.svm import build_pipeline


def _make_separable_data(n: int = 100, n_features: int = 4, seed: int = 42):
    rng = np.random.default_rng(seed)
    X = np.vstack([
        rng.normal(-2, 0.5, (n, n_features)),
        rng.normal(+2, 0.5, (n, n_features)),
    ])
    y = np.array([0] * n + [1] * n)
    return X, y


class TestFeatureImportance:
    def test_returns_dataframe_with_expected_columns(self):
        X, y = _make_separable_data()
        model = build_pipeline()
        model.fit(X, y)
        df = feature_importance(model, X, y, n_repeats=3)
        assert list(df.columns) == ["feature", "importance_mean", "importance_std"]

    def test_row_count_equals_n_features(self):
        X, y = _make_separable_data(n_features=4)
        model = build_pipeline()
        model.fit(X, y)
        df = feature_importance(model, X, y, n_repeats=3)
        assert len(df) == 4

    def test_sorted_descending(self):
        X, y = _make_separable_data()
        model = build_pipeline()
        model.fit(X, y)
        df = feature_importance(model, X, y, n_repeats=3)
        assert (df["importance_mean"].diff().dropna() <= 0).all()

    def test_accepts_dataframe_input_and_preserves_names(self):
        import pandas as pd
        X, y = _make_separable_data(n_features=3)
        col_names = ["alpha", "beta", "gamma"]
        X_df = pd.DataFrame(X, columns=col_names)
        model = build_pipeline()
        model.fit(X, y)
        df = feature_importance(model, X_df, y, n_repeats=3)
        assert set(df["feature"]) == set(col_names)


class TestPerClassMetrics:
    def test_returns_expected_columns(self):
        y_true = np.array([0, 0, 1, 1, 0, 1])
        y_pred = np.array([0, 0, 1, 0, 0, 1])
        df = per_class_metrics(y_true, y_pred)
        assert list(df.columns) == ["class", "precision", "recall", "f1", "support"]

    def test_default_class_names(self):
        y_true = np.array([0, 1])
        y_pred = np.array([0, 1])
        df = per_class_metrics(y_true, y_pred)
        assert list(df["class"]) == ["baseline", "stress"]

    def test_custom_class_names(self):
        y_true = np.array([0, 1])
        y_pred = np.array([0, 1])
        df = per_class_metrics(y_true, y_pred, class_names=["low", "high"])
        assert list(df["class"]) == ["low", "high"]

    def test_perfect_predictions(self):
        y_true = np.array([0, 0, 1, 1])
        y_pred = np.array([0, 0, 1, 1])
        df = per_class_metrics(y_true, y_pred)
        assert (df["precision"] == 1.0).all()
        assert (df["recall"] == 1.0).all()
        assert (df["f1"] == 1.0).all()

    def test_support_counts(self):
        y_true = np.array([0, 0, 0, 1, 1])
        y_pred = np.array([0, 0, 1, 1, 1])
        df = per_class_metrics(y_true, y_pred)
        assert df[df["class"] == "baseline"]["support"].iloc[0] == 3
        assert df[df["class"] == "stress"]["support"].iloc[0] == 2
