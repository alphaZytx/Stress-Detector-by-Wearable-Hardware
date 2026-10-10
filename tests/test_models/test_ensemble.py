"""Soft voting and stacking behave as specified (§23, ensemble tests)."""

from __future__ import annotations

import joblib
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from stress_detection.models.common import BASE_MODEL_NAMES, build_model, stress_proba
from stress_detection.models.ensemble import (
    DEFAULT_THRESHOLD,
    SoftVotingEnsemble,
    StackingEnsemble,
    derive_weights_from_oof,
    generate_oof_probabilities,
)


def _base_models():
    return {name: build_model(name) for name in BASE_MODEL_NAMES}


# --------------------------------------------------------------------------
# Soft voting
# --------------------------------------------------------------------------


class TestSoftVoting:
    def test_default_weights_are_equal_and_sum_to_one(self):
        ensemble = SoftVotingEnsemble(_base_models())
        assert set(ensemble.weights) == set(BASE_MODEL_NAMES)
        assert all(w == pytest.approx(0.25) for w in ensemble.weights.values())
        assert sum(ensemble.weights.values()) == pytest.approx(1.0)

    def test_custom_weights_are_normalised_to_sum_to_one(self):
        raw = {"svm": 2.0, "random_forest": 1.0, "xgboost": 1.0, "mlp": 0.0}
        ensemble = SoftVotingEnsemble(_base_models(), weights=raw)
        assert sum(ensemble.weights.values()) == pytest.approx(1.0)
        assert ensemble.weights["svm"] == pytest.approx(0.5)
        assert ensemble.weights["mlp"] == pytest.approx(0.0)

    def test_negative_weights_are_rejected(self):
        raw = {"svm": -1.0, "random_forest": 1.0, "xgboost": 1.0, "mlp": 1.0}
        with pytest.raises(ValueError, match="non-negative"):
            SoftVotingEnsemble(_base_models(), weights=raw)

    def test_zero_weights_are_rejected(self):
        raw = dict.fromkeys(BASE_MODEL_NAMES, 0.0)
        with pytest.raises(ValueError, match="sum to zero"):
            SoftVotingEnsemble(_base_models(), weights=raw)

    def test_missing_weight_fails_cleanly(self):
        with pytest.raises(ValueError, match="Missing weights"):
            SoftVotingEnsemble(_base_models(), weights={"svm": 1.0})

    def test_combines_base_probabilities_by_the_weighted_mean(self, small_grouped_data):
        """The headline arithmetic: P = w1*P1 + w2*P2 + w3*P3 + w4*P4."""
        X, y, _ = small_grouped_data
        weights = {"svm": 0.4, "random_forest": 0.3, "xgboost": 0.2, "mlp": 0.1}
        ensemble = SoftVotingEnsemble(_base_models(), weights=weights).fit(X, y)

        expected = sum(
            weights[name] * stress_proba(ensemble.base_models[name], X)
            for name in BASE_MODEL_NAMES
        )
        np.testing.assert_allclose(ensemble.predict_proba(X)[:, 1], expected, atol=1e-12)

    def test_equal_weighting_is_the_plain_mean(self, small_grouped_data):
        X, y, _ = small_grouped_data
        ensemble = SoftVotingEnsemble(_base_models()).fit(X, y)
        expected = np.mean(
            [stress_proba(ensemble.base_models[n], X) for n in BASE_MODEL_NAMES], axis=0
        )
        np.testing.assert_allclose(ensemble.predict_proba(X)[:, 1], expected, atol=1e-12)

    def test_returns_valid_two_column_probabilities(self, small_grouped_data):
        X, y, _ = small_grouped_data
        proba = SoftVotingEnsemble(_base_models()).fit(X, y).predict_proba(X)
        assert proba.shape == (len(y), 2)
        assert np.all((proba >= 0.0) & (proba <= 1.0))
        np.testing.assert_allclose(proba.sum(axis=1), 1.0)

    def test_predict_applies_the_threshold(self, small_grouped_data):
        X, y, _ = small_grouped_data
        ensemble = SoftVotingEnsemble(_base_models()).fit(X, y)
        p = ensemble.predict_proba(X)[:, 1]
        np.testing.assert_array_equal(
            ensemble.predict(X), (p >= DEFAULT_THRESHOLD).astype(int)
        )


# --------------------------------------------------------------------------
# Stacking
# --------------------------------------------------------------------------


class TestStacking:
    def test_meta_model_takes_four_probability_features(self, small_grouped_data):
        X, y, groups = small_grouped_data
        ensemble = StackingEnsemble(_base_models(), n_oof_splits=2).fit(X, y, groups)
        assert ensemble.oof_probabilities_.shape == (len(y), len(BASE_MODEL_NAMES))
        assert ensemble.meta_model.n_features_in_ == len(BASE_MODEL_NAMES)

    def test_meta_features_are_probabilities(self, small_grouped_data):
        X, y, groups = small_grouped_data
        ensemble = StackingEnsemble(_base_models(), n_oof_splits=2).fit(X, y, groups)
        oof = ensemble.oof_probabilities_
        assert np.all((oof >= 0.0) & (oof <= 1.0))
        assert not np.isnan(oof).any()

    def test_returns_valid_probabilities(self, small_grouped_data):
        X, y, groups = small_grouped_data
        ensemble = StackingEnsemble(_base_models(), n_oof_splits=2).fit(X, y, groups)
        proba = ensemble.predict_proba(X)
        assert proba.shape == (len(y), 2)
        assert np.all((proba >= 0.0) & (proba <= 1.0))
        np.testing.assert_allclose(proba.sum(axis=1), 1.0)

    def test_meta_model_is_logistic_regression(self, small_grouped_data):
        X, y, groups = small_grouped_data
        ensemble = StackingEnsemble(_base_models(), n_oof_splits=2).fit(X, y, groups)
        assert isinstance(ensemble.meta_model, LogisticRegression)
        assert set(ensemble.meta_coefficients) == set(BASE_MODEL_NAMES)

    def test_fit_requires_groups(self, small_grouped_data):
        X, y, _ = small_grouped_data
        with pytest.raises(TypeError):
            StackingEnsemble(_base_models()).fit(X, y)

    def test_mismatched_groups_length_fails_cleanly(self, small_grouped_data):
        X, y, groups = small_grouped_data
        with pytest.raises(ValueError, match="groups has"):
            StackingEnsemble(_base_models()).fit(X, y, groups[:-5])

    def test_predicting_before_fit_fails_cleanly(self, small_grouped_data):
        X, _, _ = small_grouped_data
        with pytest.raises(ValueError, match="not fitted"):
            StackingEnsemble(_base_models()).predict_proba(X)

    def test_base_models_are_refitted_on_all_training_data(self, small_grouped_data):
        """Step 3 of fit: after OOF, every base model is refitted for serving."""
        X, y, groups = small_grouped_data
        ensemble = StackingEnsemble(_base_models(), n_oof_splits=2).fit(X, y, groups)
        for name in BASE_MODEL_NAMES:
            probs = stress_proba(ensemble.base_models[name], X)
            assert probs.shape == (len(y),)


# --------------------------------------------------------------------------
# Shared ensemble behaviour
# --------------------------------------------------------------------------


class TestEnsembleContract:
    @pytest.fixture(params=["soft", "stack"])
    def fitted_ensemble(self, request, small_grouped_data):
        X, y, groups = small_grouped_data
        if request.param == "soft":
            return SoftVotingEnsemble(_base_models()).fit(X, y), X, y
        return StackingEnsemble(_base_models(), n_oof_splits=2).fit(X, y, groups), X, y

    def test_exposes_the_sklearn_schema_attributes(self, fitted_ensemble):
        """The service's schema guard reads these off whatever it loaded."""
        ensemble, X, _ = fitted_ensemble
        assert list(ensemble.classes_) == [0, 1]
        assert ensemble.n_features_in_ == X.shape[1]

    def test_feature_count_mismatch_fails_clearly(self, fitted_ensemble):
        ensemble, X, _ = fitted_ensemble
        with pytest.raises(ValueError, match="expects .* features"):
            ensemble.predict_proba(X[:, :5])

    def test_base_probabilities_are_exposed_per_model(self, fitted_ensemble):
        ensemble, X, y = fitted_ensemble
        probs = ensemble.base_probabilities(X)
        assert set(probs) == set(BASE_MODEL_NAMES)
        for value in probs.values():
            assert value.shape == (len(y),)
            assert np.all((value >= 0.0) & (value <= 1.0))

    def test_missing_base_model_fails_cleanly(self):
        partial = {name: build_model(name) for name in BASE_MODEL_NAMES[:3]}
        with pytest.raises(ValueError, match="No estimator supplied"):
            SoftVotingEnsemble(partial)
        with pytest.raises(ValueError, match="No estimator supplied"):
            StackingEnsemble(partial)

    def test_round_trips_through_joblib(self, fitted_ensemble, tmp_path):
        ensemble, X, _ = fitted_ensemble
        path = tmp_path / "ensemble.joblib"
        joblib.dump(ensemble, path)
        reloaded = joblib.load(path)
        np.testing.assert_allclose(
            reloaded.predict_proba(X), ensemble.predict_proba(X), atol=1e-12
        )


# --------------------------------------------------------------------------
# Derived weights
# --------------------------------------------------------------------------


class TestDerivedWeights:
    def test_weights_sum_to_one(self, small_grouped_data):
        X, y, groups = small_grouped_data
        oof = generate_oof_probabilities(
            _base_models(), X, y, groups, model_names=BASE_MODEL_NAMES, n_splits=2
        )
        weights = derive_weights_from_oof(oof, y, BASE_MODEL_NAMES)
        assert sum(weights.values()) == pytest.approx(1.0)
        assert all(w >= 0.0 for w in weights.values())

    def test_a_better_model_earns_more_weight(self):
        """Weight tracks OOF ROC-AUC: a perfect column outweighs a useless one."""
        y = np.tile([0, 1], 50)
        oof = np.column_stack([
            y.astype(float) * 0.9 + 0.05,   # near-perfect
            np.full(len(y), 0.5),           # uninformative
        ])
        weights = derive_weights_from_oof(oof, y, ["good", "useless"])
        assert weights["good"] > weights["useless"]
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_falls_back_to_equal_when_nothing_beats_chance(self):
        y = np.tile([0, 1], 50)
        oof = np.full((len(y), 2), 0.5)
        weights = derive_weights_from_oof(oof, y, ["a", "b"])
        assert weights == {"a": pytest.approx(0.5), "b": pytest.approx(0.5)}


class TestHoldoutRoundTrip:
    """A saved probability table must rebuild the same result it came from.

    This is what makes `evaluate_models.py --from-cache` trustworthy: a report
    regenerated from the CSV has to agree with the run that produced it, or the
    report's "any number here can be re-derived" claim is false.
    """

    def test_metrics_survive_the_round_trip(self, small_grouped_data):
        from stress_detection.eval.ensemble_reports import holdout_probability_table
        from stress_detection.models.evaluation import (
            loso_result_from_holdout,
            run_loso_evaluation,
        )

        X, y, groups = small_grouped_data
        original = run_loso_evaluation(X, y, groups, inner_splits=3, tune_splits=2, n_jobs=1)
        rebuilt = loso_result_from_holdout(holdout_probability_table(original))

        assert rebuilt.candidates == original.candidates
        assert rebuilt.subjects == original.subjects
        np.testing.assert_array_equal(rebuilt.y_true, original.y_true)

        for candidate in original.candidates:
            np.testing.assert_allclose(
                rebuilt.probabilities[candidate], original.probabilities[candidate], atol=1e-12
            )
            before = original.aggregate(candidate)
            after = rebuilt.aggregate(candidate)
            for key in ("pooled_accuracy", "pooled_macro_f1", "pooled_roc_auc",
                        "pooled_brier", "macro_f1_mean", "macro_f1_std"):
                assert after[key] == pytest.approx(before[key]), f"{candidate}.{key}"
            assert after["confusion_matrix"] == before["confusion_matrix"]

    def test_rejects_a_table_without_probability_columns(self):
        import pandas as pd

        from stress_detection.models.evaluation import loso_result_from_holdout

        frame = pd.DataFrame({"subject_id": ["S1"], "y_true": [0]})
        with pytest.raises(ValueError, match="No p_stress_"):
            loso_result_from_holdout(frame)
