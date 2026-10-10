"""Shared contract and helpers for every stress-detection classifier.

Model contract
--------------
Each base model is a scikit-learn estimator (usually a ``Pipeline``) and so
satisfies the common interface natively::

    fit(X, y) -> self
    predict(X) -> ndarray of {0, 1}
    predict_proba(X) -> ndarray of shape (n_samples, 2)

The probability contract across the whole project is::

    P(stress) == predict_proba(X)[:, 1]      0 = baseline, 1 = stress

which matches ``label_map = {"baseline": 0, "stress": 1}`` in the Phase 1
training scripts and ``_CLASS_NAMES`` in ``service.inference.engine``. Nothing
here introduces a second label convention. Use :func:`stress_proba` rather than
indexing column 1 by hand - it resolves the column through ``classes_`` so a
model fitted on an odd fold can never silently return P(baseline) instead.

Where the models live
---------------------
``build_model(name)`` dispatches to the per-model modules (``svm.py``,
``random_forest.py``, ``xgboost.py``, ``mlp.py``), each of which owns its own
defaults and hyperparameter grids. The import is done lazily inside the
dispatch so that (a) there is no import cycle and (b) the FastAPI service,
which only needs the SVM, still starts when the optional xgboost wheel is
missing.

Hyperparameter grids
--------------------
Each model module defines two grid sizes:

``PARAM_GRID``
    The full search, used once per model to pick the hyperparameters of the
    *deployed* artifact (subject-grouped ``GroupKFold`` over the whole dataset).

``COMPACT_PARAM_GRID``
    A deliberately small search, re-run *inside* each outer LOSO fold of the
    nested evaluation. Re-tuning inside the fold is what keeps the held-out
    subject out of model selection; a small grid is what keeps 16 nested folds
    affordable.

Both are always searched with subject-grouped folds. Ordinary ``KFold`` is
never used anywhere in this project: windows overlap at a 5 s stride and come
in long per-subject runs, so a random split would put near-duplicate windows
from one subject on both sides and inflate every score.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Protocol, runtime_checkable

import numpy as np
from sklearn.base import BaseEstimator
from sklearn.model_selection import GridSearchCV, GroupKFold

logger = logging.getLogger(__name__)

# Single seed for every stochastic component in the project (§16).
RANDOM_SEED = 42

# The one label convention.
LABEL_MAP: dict[str, int] = {"baseline": 0, "stress": 1}
CLASS_NAMES: dict[int, str] = {0: "baseline", 1: "stress"}

# Canonical base-model order. The stacking meta-feature matrix uses exactly
# this column order, so it must stay stable between training and serving.
BASE_MODEL_NAMES: tuple[str, ...] = ("svm", "random_forest", "xgboost", "mlp")

# name -> (module, builder attribute)
_MODEL_MODULES: dict[str, tuple[str, str]] = {
    "svm": ("stress_detection.models.svm", "build_svm"),
    "random_forest": ("stress_detection.models.random_forest", "build_random_forest"),
    "xgboost": ("stress_detection.models.xgboost", "build_xgboost"),
    "mlp": ("stress_detection.models.mlp", "build_mlp"),
}


@runtime_checkable
class StressClassifier(Protocol):
    """The only interface the ensemble and inference layers depend on."""

    def fit(self, X: np.ndarray, y: np.ndarray) -> Any: ...

    def predict(self, X: np.ndarray) -> np.ndarray: ...

    def predict_proba(self, X: np.ndarray) -> np.ndarray: ...


def _model_module(name: str):
    try:
        module_path, _ = _MODEL_MODULES[name]
    except KeyError:
        raise ValueError(
            f"Unknown model '{name}'. Known models: {sorted(_MODEL_MODULES)}"
        ) from None
    return importlib.import_module(module_path)


def build_model(name: str, **overrides: Any) -> BaseEstimator:
    """Return an unfitted estimator for ``name`` (see :data:`BASE_MODEL_NAMES`)."""
    module = _model_module(name)
    builder = getattr(module, _MODEL_MODULES[name][1])
    return builder(**overrides)


def param_grid(name: str, compact: bool = False) -> dict[str, list]:
    """Return the full or compact hyperparameter grid for ``name``."""
    module = _model_module(name)
    return dict(getattr(module, "COMPACT_PARAM_GRID" if compact else "PARAM_GRID"))


def grouped_cv(groups: np.ndarray, n_splits: int = 5) -> GroupKFold:
    """GroupKFold sized to the number of distinct subjects present."""
    n_groups = len(np.unique(groups))
    if n_groups < 2:
        raise ValueError(f"Subject-grouped CV needs >= 2 subjects, got {n_groups}.")
    return GroupKFold(n_splits=min(n_splits, n_groups))


def tune_model(
    name: str,
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    *,
    compact: bool = False,
    n_splits: int = 5,
    scoring: str = "f1_macro",
    n_jobs: int = -1,
) -> tuple[BaseEstimator, dict]:
    """Subject-grouped grid search. Returns ``(best_estimator, best_params)``.

    ``groups`` is required, not optional: every tuning call in this project is
    subject-grouped. The returned estimator is already refitted on all of
    ``(X, y)`` - which is the *caller's* training portion, so when this is
    called from inside a LOSO fold the outer test subject is absent by
    construction.
    """
    search = GridSearchCV(
        build_model(name),
        param_grid(name, compact=compact),
        cv=grouped_cv(groups, n_splits),
        scoring=scoring,
        n_jobs=n_jobs,
        refit=True,
    )
    search.fit(X, y, groups=groups)
    logger.info(
        "%s: best %s=%.4f params=%s",
        name, scoring, search.best_score_, search.best_params_,
    )
    best = search.best_estimator_
    # The grouped CV score that *selected* these hyperparameters. It is a
    # selection statistic, not a performance estimate - the reported numbers
    # come from the nested LOSO sweep in models.evaluation.
    try:
        best.grouped_cv_score_ = float(search.best_score_)
    except AttributeError:  # pragma: no cover - sklearn estimators allow this
        pass
    return best, dict(search.best_params_)


def stress_proba(model: StressClassifier, X: np.ndarray) -> np.ndarray:
    """Return P(stress) as a 1-D array.

    Resolves the column through ``classes_`` when available instead of assuming
    column 1, so a degenerate fit (or a model whose ``classes_`` came back in a
    different order) raises or indexes correctly rather than silently returning
    P(baseline).
    """
    proba = np.asarray(model.predict_proba(X))
    classes = getattr(model, "classes_", None)
    if classes is None:
        return proba[:, 1]
    classes = [int(c) for c in np.asarray(classes).ravel()]
    if 1 not in classes:
        raise ValueError(
            f"Model was fitted without the stress class (classes_={classes}); "
            "P(stress) is undefined."
        )
    return proba[:, classes.index(1)]
