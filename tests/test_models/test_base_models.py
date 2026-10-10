"""Every base model honours the shared contract (§23, model tests)."""

from __future__ import annotations

import numpy as np
import pytest

from stress_detection.models.common import (
    BASE_MODEL_NAMES,
    build_model,
    param_grid,
    stress_proba,
    tune_model,
)

pytestmark = pytest.mark.parametrize("name", BASE_MODEL_NAMES)


def test_model_builds_and_fits(name, small_grouped_data):
    X, y, _ = small_grouped_data
    model = build_model(name)
    fitted = model.fit(X, y)
    assert fitted is not None


def test_model_predicts_binary_labels(name, small_grouped_data):
    X, y, _ = small_grouped_data
    model = build_model(name).fit(X, y)
    preds = model.predict(X)
    assert len(preds) == len(y)
    assert set(np.unique(preds)).issubset({0, 1})


def test_predict_proba_shape_and_range(name, small_grouped_data):
    X, y, _ = small_grouped_data
    model = build_model(name).fit(X, y)
    proba = model.predict_proba(X)
    assert proba.shape == (len(y), 2)
    assert np.all(proba >= 0.0) and np.all(proba <= 1.0)
    assert np.allclose(proba.sum(axis=1), 1.0)


def test_stress_probability_is_column_one(name, small_grouped_data):
    """The project-wide contract: predict_proba(X)[:, 1] == P(stress)."""
    X, y, _ = small_grouped_data
    model = build_model(name).fit(X, y)
    p = stress_proba(model, X)
    assert p.shape == (len(y),)
    assert np.all((p >= 0.0) & (p <= 1.0))
    np.testing.assert_allclose(p, model.predict_proba(X)[:, 1], atol=1e-12)
    # And it really is the stress class, not merely column 1 by convention.
    assert list(np.asarray(model.classes_).ravel().astype(int)) == [0, 1]


def test_probability_separates_the_classes(name, small_grouped_data):
    """A sanity floor: a fitted model puts higher P(stress) on stress windows."""
    X, y, _ = small_grouped_data
    model = build_model(name).fit(X, y)
    p = stress_proba(model, X)
    assert p[y == 1].mean() > p[y == 0].mean()


def test_feature_count_mismatch_fails_clearly(name, small_grouped_data):
    X, y, _ = small_grouped_data
    model = build_model(name).fit(X, y)
    with pytest.raises(ValueError, match=r"(?i)feature|shape|expect"):
        model.predict_proba(X[:, :5])


def test_fixed_seed_is_reproducible(name, small_grouped_data):
    X, y, _ = small_grouped_data
    first = stress_proba(build_model(name).fit(X, y), X)
    second = stress_proba(build_model(name).fit(X, y), X)
    np.testing.assert_allclose(first, second)


def test_grids_are_defined_and_modest(name):
    full = param_grid(name)
    compact = param_grid(name, compact=True)
    assert full and compact
    n_compact = int(np.prod([len(v) for v in compact.values()]))
    # The compact grid is re-run inside all 16 outer folds; keep it small.
    assert n_compact <= 8, f"{name} compact grid has {n_compact} candidates"


def test_tuning_is_subject_grouped(name, small_grouped_data):
    """tune_model requires groups and returns a fitted estimator + params."""
    X, y, groups = small_grouped_data
    estimator, params = tune_model(name, X, y, groups, compact=True, n_splits=2, n_jobs=1)
    assert set(params).issubset(set(param_grid(name, compact=True)))
    assert stress_proba(estimator, X).shape == (len(y),)
    assert getattr(estimator, "grouped_cv_score_", None) is not None
