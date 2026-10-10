"""SVM classifier for binary stress detection.

Pipeline: StandardScaler → SVC(RBF kernel, probability=True).
Probability calibration is enabled so the dashboard can show a confidence score.

Cross-validation strategy:
  - If subject IDs are provided as `groups`, uses LeaveOneGroupOut (LOSO).
    This is the honest evaluation for a subject-generalising model - each
    fold trains on N-1 subjects and tests on 1 held-out subject.
  - Otherwise, falls back to a single temporal split: the first 70% of rows
    (in whatever order they were supplied) train, the last 30% test. This is
    NOT split within each class separately, despite an earlier version of
    this docstring claiming so - it is one slice of the full row order.
    Every caller in this repo supplies `groups`, so this fallback is not
    exercised by any script here; it exists only as a defensive default.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import (
    GridSearchCV,
    GroupKFold,
    LeaveOneGroupOut,
    StratifiedKFold,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from .common import RANDOM_SEED

logger = logging.getLogger(__name__)

# Full grid for the deployed artifact. Unchanged from Phase 1.
PARAM_GRID = {
    "svc__C": [0.1, 1, 10, 100],
    "svc__gamma": ["scale", 0.001, 0.01, 0.1],
}

# Compact grid re-run inside every outer LOSO fold of the nested evaluation.
# The Phase 1 full-grid search settled on C=1, gamma="scale"; this keeps that
# neighbourhood plus the two next-most-plausible settings.
COMPACT_PARAM_GRID = {
    "svc__C": [1, 10, 100],
    "svc__gamma": ["scale", 0.01],
}

_DEFAULT_PARAM_GRID = PARAM_GRID  # back-compat alias


def build_svm(**overrides) -> Pipeline:
    """Return an unfitted StandardScaler → RBF SVC pipeline.

    ``probability=True`` fits Platt scaling by internal 5-fold CV, which is
    stochastic - hence the fixed ``random_state`` (§16). Overrides accept bare
    names (``C=10``) or the pipeline-qualified form (``svc__C=10``).
    """
    params = {
        "C": 1.0,
        "gamma": "scale",
        "kernel": "rbf",
        "probability": True,
        "random_state": RANDOM_SEED,
    }
    for key, value in overrides.items():
        params[key.removeprefix("svc__")] = value
    return Pipeline([("scaler", StandardScaler()), ("svc", SVC(**params))])


def build_pipeline(
    C: float = 1.0,
    gamma: str | float = "scale",
    kernel: str = "rbf",
) -> Pipeline:
    """Return an unfitted StandardScaler → SVC pipeline.

    Kept as the Phase 1 entry point; delegates to :func:`build_svm`.
    """
    return build_svm(C=C, gamma=gamma, kernel=kernel)


def tune_svm(
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray | None = None,
    param_grid: dict | None = None,
) -> tuple[Pipeline, dict]:
    """Grid-search SVM hyperparameters and return the best-fitted pipeline.

    Args:
        X: Feature matrix.
        y: Binary label vector (0 = baseline, 1 = stress).
        groups: Subject-ID array for GroupKFold (use for WESAD data).
                If None, StratifiedKFold(5) is used instead.
        param_grid: Parameter grid for GridSearchCV. Defaults to
                    C ∈ [0.1,1,10,100] × gamma ∈ ["scale",0.001,0.01,0.1].

    Returns:
        (best_pipeline, cv_results_dict) where best_pipeline is already fitted
        on the full (X, y).
    """
    if param_grid is None:
        param_grid = _DEFAULT_PARAM_GRID

    cv = (
        GroupKFold(n_splits=min(5, len(np.unique(groups))))
        if groups is not None
        else StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    )

    pipeline = build_pipeline()
    search = GridSearchCV(
        pipeline,
        param_grid,
        cv=cv,
        scoring="f1_macro",
        n_jobs=-1,
        refit=True,
    )

    fit_kwargs: dict = {}
    if groups is not None:
        fit_kwargs["groups"] = groups

    search.fit(X, y, **fit_kwargs)
    logger.info("Best params: %s  CV f1_macro=%.4f", search.best_params_, search.best_score_)

    return search.best_estimator_, search.cv_results_


def evaluate(
    model: Pipeline,
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray | None = None,
) -> dict:
    """Evaluate the model and return a metrics dict plus aggregated confusion matrix.

    Args:
        model: A fitted (or unfitted) Pipeline - the hyperparams are fixed and
               refitted in each evaluation fold.
        X: Feature matrix.
        y: Binary label vector.
        groups: Subject IDs for LOSO. If None, temporal split is used.

    Returns:
        Dict with:
          accuracy_mean, accuracy_std, macro_f1_mean, macro_f1_std,
          weighted_f1_mean, weighted_f1_std,
          precision_per_class_mean, recall_per_class_mean, f1_per_class_mean,
          confusion_matrix (aggregated over all folds, as list-of-lists).
    """
    y_true_all: list[np.ndarray] = []
    y_pred_all: list[np.ndarray] = []
    fold_accs: list[float] = []
    fold_f1s: list[float] = []

    if groups is not None:
        logo = LeaveOneGroupOut()
        for train_idx, test_idx in logo.split(X, y, groups):
            m = clone(model)
            m.fit(X[train_idx], y[train_idx])
            y_pred = m.predict(X[test_idx])
            y_true_all.append(y[test_idx])
            y_pred_all.append(y_pred)
            fold_accs.append(accuracy_score(y[test_idx], y_pred))
            fold_f1s.append(f1_score(y[test_idx], y_pred, average="macro", zero_division=0))
    else:
        # Temporal split: stable 70/30 to avoid window-overlap leakage
        n = len(y)
        split = int(n * 0.7)
        m = clone(model)
        m.fit(X[:split], y[:split])
        y_pred = m.predict(X[split:])
        y_true_all.append(y[split:])
        y_pred_all.append(y_pred)
        fold_accs.append(accuracy_score(y[split:], y_pred))
        fold_f1s.append(f1_score(y[split:], y_pred, average="macro", zero_division=0))

    y_true = np.concatenate(y_true_all)
    y_pred = np.concatenate(y_pred_all)

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])

    return {
        "accuracy_mean": float(np.mean(fold_accs)),
        "accuracy_std": float(np.std(fold_accs)),
        "macro_f1_mean": float(np.mean(fold_f1s)),
        "macro_f1_std": float(np.std(fold_f1s)),
        "weighted_f1_mean": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
        "precision_per_class": precision_score(y_true, y_pred, average=None, zero_division=0).tolist(),
        "recall_per_class": recall_score(y_true, y_pred, average=None, zero_division=0).tolist(),
        "f1_per_class": f1_score(y_true, y_pred, average=None, zero_division=0).tolist(),
        "confusion_matrix": cm.tolist(),
        "n_folds": len(fold_accs),
    }
