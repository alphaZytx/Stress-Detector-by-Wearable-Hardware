"""Leakage tests (§23) - the guarantees that make stacking valid.

These do not merely assert that ``GroupKFold`` was *asked for*. They watch what
the estimators are actually handed. The synthetic dataset from ``conftest.py``
carries the subject index in feature column 0, so a spy estimator can report,
from inside its own ``fit`` and ``predict_proba``, exactly which subjects it
saw - and the tests then check that those sets never intersect.
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.model_selection import LeaveOneGroupOut

from stress_detection.models.common import BASE_MODEL_NAMES, build_model
from stress_detection.models.ensemble import StackingEnsemble, generate_oof_probabilities
from stress_detection.models.evaluation import run_loso_evaluation

from .conftest import make_grouped_dataset

# Subject index lives in feature column 0 (see conftest).
_SUBJECT_COLUMN = 0


class SpyClassifier(BaseEstimator, ClassifierMixin):
    """Records which subjects it was fitted on and which it predicted.

    Events go to a module-level log rather than to instance state, because
    ``sklearn.base.clone`` rebuilds the estimator from its constructor
    parameters and would otherwise drop any shared recorder.
    """

    LOG: list[tuple[str, str, frozenset]] = []

    def __init__(self, tag: str = "spy"):
        self.tag = tag

    def fit(self, X, y):
        X = np.asarray(X)
        self.classes_ = np.unique(y)
        self.n_features_in_ = X.shape[1]
        self._rate = float(np.mean(y)) if len(y) else 0.5
        SpyClassifier.LOG.append(("fit", self.tag, _subjects(X)))
        return self

    def predict_proba(self, X):
        X = np.asarray(X)
        SpyClassifier.LOG.append(("predict", self.tag, _subjects(X)))
        # Deterministic, mildly informative, and never exactly 0 or 1.
        p = 1.0 / (1.0 + np.exp(-X[:, 1]))
        return np.column_stack([1.0 - p, p])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


def _subjects(X: np.ndarray) -> frozenset:
    return frozenset(np.unique(X[:, _SUBJECT_COLUMN]).tolist())


@pytest.fixture(autouse=True)
def clear_spy_log():
    SpyClassifier.LOG.clear()
    yield
    SpyClassifier.LOG.clear()


def _spy_models():
    return {name: SpyClassifier(tag=name) for name in BASE_MODEL_NAMES}


def _fit_predict_pairs() -> list[tuple[frozenset, frozenset]]:
    """Pair each fit with the predict call that immediately followed it."""
    pairs = []
    pending: dict[str, frozenset] = {}
    for kind, tag, subjects in SpyClassifier.LOG:
        if kind == "fit":
            pending[tag] = subjects
        elif tag in pending:
            pairs.append((pending.pop(tag), subjects))
    return pairs


# --------------------------------------------------------------------------
# OOF generation
# --------------------------------------------------------------------------


class TestOofGeneration:
    def test_a_subject_is_never_in_the_fit_data_for_its_own_oof_prediction(self):
        """The core guarantee of §8.1, verified from inside the estimators."""
        X, y, groups = make_grouped_dataset(n_subjects=6, n_per_subject=20)
        generate_oof_probabilities(
            _spy_models(), X, y, groups, model_names=BASE_MODEL_NAMES, n_splits=3
        )

        pairs = _fit_predict_pairs()
        assert pairs, "the spy recorded no fit/predict pairs"
        for fitted_on, predicted in pairs:
            assert not (fitted_on & predicted), (
                f"subject(s) {sorted(fitted_on & predicted)} were both trained on "
                "and predicted by the same base model"
            )

    def test_folds_are_grouped_not_random(self):
        """Each predict block covers whole subjects - never a slice of one."""
        X, y, groups = make_grouped_dataset(n_subjects=6, n_per_subject=20)
        generate_oof_probabilities(
            _spy_models(), X, y, groups, model_names=BASE_MODEL_NAMES, n_splits=3
        )
        all_subjects = set(np.unique(X[:, _SUBJECT_COLUMN]).tolist())
        for kind, _tag, subjects in SpyClassifier.LOG:
            if kind == "fit":
                # A random KFold would hand a fit almost every subject every time.
                assert subjects < all_subjects

    def test_every_row_receives_an_out_of_fold_prediction(self):
        X, y, groups = make_grouped_dataset(n_subjects=5, n_per_subject=20)
        oof = generate_oof_probabilities(
            _spy_models(), X, y, groups, model_names=BASE_MODEL_NAMES, n_splits=5
        )
        assert oof.shape == (len(y), len(BASE_MODEL_NAMES))
        assert not np.isnan(oof).any()

    def test_oof_probabilities_differ_from_in_sample_ones(self):
        """Proof it is not the invalid 'fit on everything, predict the same rows' recipe."""
        X, y, groups = make_grouped_dataset(n_subjects=5, n_per_subject=30)
        models = {name: build_model(name) for name in BASE_MODEL_NAMES}
        oof = generate_oof_probabilities(
            models, X, y, groups, model_names=BASE_MODEL_NAMES, n_splits=5
        )
        in_sample = np.column_stack([
            build_model(name).fit(X, y).predict_proba(X)[:, 1] for name in BASE_MODEL_NAMES
        ])
        assert not np.allclose(oof, in_sample, atol=1e-6)

    def test_grouping_is_mandatory(self):
        X, y, _ = make_grouped_dataset(n_subjects=3, n_per_subject=20)
        single_group = np.array(["only"] * len(y))
        with pytest.raises(ValueError, match=r">= 2 subjects"):
            generate_oof_probabilities(
                _spy_models(), X, y, single_group,
                model_names=BASE_MODEL_NAMES, n_splits=3,
            )


# --------------------------------------------------------------------------
# Meta-model training
# --------------------------------------------------------------------------


class SpyMetaModel(BaseEstimator, ClassifierMixin):
    """Captures exactly what matrix the meta-model was trained on."""

    def __init__(self):
        self.seen_X = None

    def fit(self, X, y):
        self.seen_X = np.array(X, copy=True)
        self.classes_ = np.unique(y)
        self.n_features_in_ = np.asarray(X).shape[1]
        return self

    def predict_proba(self, X):
        p = np.asarray(X).mean(axis=1)
        return np.column_stack([1.0 - p, p])


class TestMetaModelTraining:
    def test_meta_model_is_trained_on_the_oof_matrix_only(self):
        X, y, groups = make_grouped_dataset(n_subjects=5, n_per_subject=24)
        meta = SpyMetaModel()
        ensemble = StackingEnsemble(
            {name: build_model(name) for name in BASE_MODEL_NAMES},
            meta_model=meta,
            n_oof_splits=5,
        ).fit(X, y, groups)

        assert meta.seen_X is not None
        np.testing.assert_allclose(meta.seen_X, ensemble.oof_probabilities_)
        assert meta.seen_X.shape == (len(y), len(BASE_MODEL_NAMES))

    def test_meta_model_never_sees_the_raw_features(self):
        X, y, groups = make_grouped_dataset(n_subjects=5, n_per_subject=24)
        meta = SpyMetaModel()
        StackingEnsemble(
            {name: build_model(name) for name in BASE_MODEL_NAMES},
            meta_model=meta,
            n_oof_splits=5,
        ).fit(X, y, groups)
        assert meta.seen_X.shape[1] == len(BASE_MODEL_NAMES)
        assert meta.seen_X.shape[1] != X.shape[1]

    def test_meta_training_matrix_is_not_the_in_sample_matrix(self):
        X, y, groups = make_grouped_dataset(n_subjects=5, n_per_subject=24)
        meta = SpyMetaModel()
        ensemble = StackingEnsemble(
            {name: build_model(name) for name in BASE_MODEL_NAMES},
            meta_model=meta,
            n_oof_splits=5,
        ).fit(X, y, groups)
        # After fit, base models are refitted on everything; their in-sample
        # probabilities must NOT be what the meta-model was trained on.
        in_sample = np.column_stack([
            ensemble.base_models[n].predict_proba(X)[:, 1] for n in BASE_MODEL_NAMES
        ])
        assert not np.allclose(meta.seen_X, in_sample, atol=1e-6)


# --------------------------------------------------------------------------
# Outer LOSO isolation
# --------------------------------------------------------------------------


class TestOuterLosoIsolation:
    def test_held_out_subject_never_appears_in_any_fitting_data(self):
        """No fit inside an outer fold may see that fold's held-out subject."""
        X, y, groups = make_grouped_dataset(n_subjects=4, n_per_subject=24)
        logo = LeaveOneGroupOut()
        for train_idx, test_idx in logo.split(X, y, groups):
            held_out = _subjects(X[test_idx])
            SpyClassifier.LOG.clear()
            generate_oof_probabilities(
                _spy_models(), X[train_idx], y[train_idx], groups[train_idx],
                model_names=BASE_MODEL_NAMES, n_splits=3,
            )
            for kind, _tag, subjects in SpyClassifier.LOG:
                assert not (subjects & held_out), (
                    f"held-out subject {sorted(held_out)} reached a {kind} call"
                )

    def test_run_loso_evaluation_scores_every_window_exactly_once(self):
        X, y, groups = make_grouped_dataset(n_subjects=4, n_per_subject=24)
        result = run_loso_evaluation(X, y, groups, inner_splits=3, tune_splits=2, n_jobs=1)
        assert len(result.y_true) == len(y)
        assert sorted(result.subjects) == sorted(set(groups.tolist()))
        for candidate in result.candidates:
            assert result.probabilities[candidate].shape == (len(y),)
            assert np.all((result.probabilities[candidate] >= 0.0)
                          & (result.probabilities[candidate] <= 1.0))

    def test_each_fold_tests_exactly_one_subject(self):
        X, y, groups = make_grouped_dataset(n_subjects=4, n_per_subject=24)
        result = run_loso_evaluation(X, y, groups, inner_splits=3, tune_splits=2, n_jobs=1)
        for candidate in result.candidates:
            subjects = [f["subject_id"] for f in result.fold_metrics[candidate]]
            assert len(subjects) == len(set(subjects)) == 4

    def test_weights_and_meta_model_are_refit_per_fold(self):
        """Weight and meta-model selection happen inside the fold, not once globally."""
        X, y, groups = make_grouped_dataset(n_subjects=4, n_per_subject=24)
        result = run_loso_evaluation(X, y, groups, inner_splits=3, tune_splits=2, n_jobs=1)
        assert set(result.soft_weights) == set(result.subjects)
        assert set(result.meta_coefficients) == set(result.subjects)
        assert set(result.tuned_params) == set(result.subjects)
        for weights in result.soft_weights.values():
            assert sum(weights.values()) == pytest.approx(1.0)
