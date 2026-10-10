"""Subject-independent evaluation for single models and ensembles.

The primary protocol is ``LeaveOneGroupOut`` over ``subject_id`` - the same one
the Phase 1 SVM already used. No window-level random split is reported
anywhere: windows overlap at a 5 s stride and arrive in long per-subject runs,
so a random split leaks near-duplicates and reads far too well.

What one outer fold does
------------------------
For each held-out subject, :func:`run_loso_evaluation` evaluates all seven
candidates in a single pass over the training subjects::

    1. tune each base model on the training subjects only
       (grouped inner GroupKFold, compact grid)
    2. grouped OOF probabilities on the training subjects
    3. soft-voting weights derived from those OOF probabilities
    4. LogisticRegression meta-model fitted on those OOF probabilities
    5. base models refitted on all training subjects
    6. everything predicts the held-out subject, once

The held-out subject takes no part in tuning, OOF generation, meta-model
training or weight selection - only in step 6. Sharing steps 1-2 across all
candidates is what makes 16 nested folds affordable; it does not relax the
isolation, because every shared artifact is built from training subjects alone.

One documented approximation: within a fold, hyperparameters chosen in step 1
(on all training subjects) are reused for the step-2 OOF clones. That is
selection information moving *inside* the training portion, which does not
touch the outer held-out subject.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import LeaveOneGroupOut

from .common import BASE_MODEL_NAMES, RANDOM_SEED, stress_proba, tune_model
from .ensemble import (
    DEFAULT_THRESHOLD,
    derive_weights_from_oof,
    generate_oof_probabilities,
)

logger = logging.getLogger(__name__)

# The seven things being compared. Soft voting appears twice: equal weights is
# the §7 primary baseline, the derived-weight variant is the labelled
# experiment sitting beside it.
SOFT_EQUAL = "soft_voting"
SOFT_WEIGHTED = "soft_voting_weighted"
STACKING = "stacking"
CANDIDATES: tuple[str, ...] = (*BASE_MODEL_NAMES, SOFT_EQUAL, SOFT_WEIGHTED, STACKING)


# --------------------------------------------------------------------------
# Metrics (§6, §9)
# --------------------------------------------------------------------------


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    p_stress: np.ndarray | None = None,
) -> dict:
    """Accuracy, macro F1, per-class precision/recall/F1, confusion matrix,
    and (where defined) ROC-AUC and Brier score.

    ROC-AUC and Brier are returned as ``None`` rather than a filler value when
    ``y_true`` holds a single class, so downstream averaging can skip the fold
    instead of averaging in a fabricated number.
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    precision = precision_score(y_true, y_pred, average=None, labels=[0, 1], zero_division=0)
    recall = recall_score(y_true, y_pred, average=None, labels=[0, 1], zero_division=0)
    per_class_f1 = f1_score(y_true, y_pred, average=None, labels=[0, 1], zero_division=0)

    roc_auc: float | None = None
    brier: float | None = None
    if p_stress is not None and len(np.unique(y_true)) == 2:
        roc_auc = float(roc_auc_score(y_true, p_stress))
        brier = float(brier_score_loss(y_true, p_stress))

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
        "baseline_precision": float(precision[0]),
        "baseline_recall": float(recall[0]),
        "baseline_f1": float(per_class_f1[0]),
        "stress_precision": float(precision[1]),
        "stress_recall": float(recall[1]),
        "stress_f1": float(per_class_f1[1]),
        "roc_auc": roc_auc,
        "brier": brier,
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist(),
        "n_samples": int(len(y_true)),
    }


def _mean_std(values: list[float | None]) -> tuple[float | None, float | None, int]:
    present = [v for v in values if v is not None and not np.isnan(v)]
    if not present:
        return None, None, 0
    return float(np.mean(present)), float(np.std(present)), len(present)


# --------------------------------------------------------------------------
# Result container
# --------------------------------------------------------------------------


@dataclass
class LosoResult:
    """Everything one LOSO sweep produced, for all candidates at once."""

    candidates: list[str]
    subjects: list[str]                          # fold order
    y_true: np.ndarray                           # concatenated, fold order
    row_subject: np.ndarray                      # subject id per row
    probabilities: dict[str, np.ndarray]         # candidate -> P(stress) per row
    predictions: dict[str, np.ndarray]           # candidate -> 0/1 per row
    fold_metrics: dict[str, list[dict]]          # candidate -> per-fold metrics
    tuned_params: dict[str, dict] = field(default_factory=dict)   # subject -> {model: params}
    soft_weights: dict[str, dict] = field(default_factory=dict)   # subject -> {model: weight}
    meta_coefficients: dict[str, dict] = field(default_factory=dict)
    fit_seconds: float = 0.0

    def aggregate(self, candidate: str) -> dict:
        """Pooled metrics over every held-out window, plus per-fold mean/std.

        Pooled numbers come from concatenating all 16 folds' predictions, so
        each window counts once. The ``*_mean``/``*_std`` pair summarises the
        spread *across subjects*, which §19.4 asks for and which a single
        pooled number hides.
        """
        folds = self.fold_metrics[candidate]
        pooled = compute_metrics(
            self.y_true, self.predictions[candidate], self.probabilities[candidate]
        )
        out = {f"pooled_{k}": v for k, v in pooled.items()}
        out["confusion_matrix"] = pooled["confusion_matrix"]
        for key in ("accuracy", "macro_f1", "stress_f1", "baseline_f1", "roc_auc", "brier"):
            mean, std, n = _mean_std([f[key] for f in folds])
            out[f"{key}_mean"] = mean
            out[f"{key}_std"] = std
            if key in ("roc_auc", "brier"):
                out[f"{key}_n_folds"] = n
        out["n_folds"] = len(folds)
        return out

    def probability_correlation(self) -> dict[str, dict[str, float]]:
        """Pearson correlation between candidates' held-out P(stress) (§19.3).

        Highly correlated base models make similar mistakes, which bounds how
        much any ensemble over them can help - this is the number that says
        whether the ensemble had anything to work with.
        """
        names = self.candidates
        matrix = np.column_stack([self.probabilities[n] for n in names])
        corr = np.corrcoef(matrix, rowvar=False)
        return {
            a: {b: float(corr[i, j]) for j, b in enumerate(names)}
            for i, a in enumerate(names)
        }


# --------------------------------------------------------------------------
# The LOSO sweep
# --------------------------------------------------------------------------


def run_loso_evaluation(
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    *,
    model_names: tuple[str, ...] = BASE_MODEL_NAMES,
    inner_splits: int = 5,
    tune_splits: int = 3,
    compact_grid: bool = True,
    threshold: float = DEFAULT_THRESHOLD,
    n_jobs: int = -1,
) -> LosoResult:
    """Run the nested LOSO comparison described in this module's docstring."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y)
    groups = np.asarray(groups)
    model_names = tuple(model_names)
    candidates = [*model_names, SOFT_EQUAL, SOFT_WEIGHTED, STACKING]

    logo = LeaveOneGroupOut()
    n_folds = logo.get_n_splits(X, y, groups)
    logger.info(
        "LOSO: %d folds, %d windows, %d features, candidates=%s",
        n_folds, len(y), X.shape[1], candidates,
    )

    subjects: list[str] = []
    y_chunks: list[np.ndarray] = []
    subject_chunks: list[np.ndarray] = []
    prob_chunks: dict[str, list[np.ndarray]] = {c: [] for c in candidates}
    fold_metrics: dict[str, list[dict]] = {c: [] for c in candidates}
    tuned_params: dict[str, dict] = {}
    soft_weights: dict[str, dict] = {}
    meta_coefficients: dict[str, dict] = {}

    started = time.perf_counter()
    for fold, (train_idx, test_idx) in enumerate(logo.split(X, y, groups), start=1):
        held_out = str(np.unique(groups[test_idx])[0])
        X_tr, y_tr, g_tr = X[train_idx], y[train_idx], groups[train_idx]
        X_te, y_te = X[test_idx], y[test_idx]

        # Hard guarantee, re-checked every fold rather than assumed.
        if set(np.unique(g_tr).tolist()) & {held_out}:
            raise AssertionError(f"Subject {held_out} leaked into its own training split.")

        # 1. tune each base model on the training subjects only
        tuned: dict[str, object] = {}
        params: dict[str, dict] = {}
        for name in model_names:
            estimator, best = tune_model(
                name, X_tr, y_tr, g_tr,
                compact=compact_grid, n_splits=tune_splits, n_jobs=n_jobs,
            )
            tuned[name] = estimator          # already refitted on all of X_tr
            params[name] = best
        tuned_params[held_out] = params

        # 2. grouped OOF probabilities over the training subjects
        oof = generate_oof_probabilities(
            tuned, X_tr, y_tr, g_tr, model_names=model_names, n_splits=inner_splits,
        )

        # base-model probabilities on the held-out subject
        base_te = np.column_stack([stress_proba(tuned[n], X_te) for n in model_names])
        for col, name in enumerate(model_names):
            prob_chunks[name].append(base_te[:, col])

        # 3. soft voting - equal weights (primary) and OOF-derived (experiment)
        equal_w = np.full(len(model_names), 1.0 / len(model_names))
        prob_chunks[SOFT_EQUAL].append(np.clip(base_te @ equal_w, 0.0, 1.0))

        derived = derive_weights_from_oof(oof, y_tr, model_names)
        soft_weights[held_out] = derived
        w_vec = np.array([derived[n] for n in model_names])
        prob_chunks[SOFT_WEIGHTED].append(np.clip(base_te @ w_vec, 0.0, 1.0))

        # 4. stacking meta-model on the OOF probabilities
        meta = LogisticRegression(C=1.0, max_iter=1000, random_state=RANDOM_SEED)
        meta.fit(oof, y_tr)
        meta_classes = [int(c) for c in np.asarray(meta.classes_).ravel()]
        stack_p = meta.predict_proba(base_te)[:, meta_classes.index(1)]
        prob_chunks[STACKING].append(stack_p)
        meta_coefficients[held_out] = {
            n: float(c) for n, c in zip(model_names, np.asarray(meta.coef_).ravel())
        }

        subjects.append(held_out)
        y_chunks.append(y_te)
        subject_chunks.append(np.full(len(y_te), held_out, dtype=object))

        for cand in candidates:
            p = prob_chunks[cand][-1]
            metrics = compute_metrics(y_te, (p >= threshold).astype(int), p)
            metrics["subject_id"] = held_out
            fold_metrics[cand].append(metrics)

        logger.info(
            "fold %d/%d subject=%s n=%d  svm=%.3f rf=%.3f xgb=%.3f mlp=%.3f "
            "soft=%.3f stack=%.3f (macro-F1)",
            fold, n_folds, held_out, len(y_te),
            *[fold_metrics[c][-1]["macro_f1"] for c in
              (*model_names, SOFT_EQUAL, STACKING)],
        )

    probabilities = {c: np.concatenate(prob_chunks[c]) for c in candidates}
    predictions = {c: (p >= threshold).astype(int) for c, p in probabilities.items()}

    return LosoResult(
        candidates=candidates,
        subjects=subjects,
        y_true=np.concatenate(y_chunks),
        row_subject=np.concatenate(subject_chunks),
        probabilities=probabilities,
        predictions=predictions,
        fold_metrics=fold_metrics,
        tuned_params=tuned_params,
        soft_weights=soft_weights,
        meta_coefficients=meta_coefficients,
        fit_seconds=time.perf_counter() - started,
    )


def loso_result_from_holdout(
    holdout: pd.DataFrame,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    tuned_params: dict[str, dict] | None = None,
    soft_weights: dict[str, dict] | None = None,
    meta_coefficients: dict[str, dict] | None = None,
    fit_seconds: float = 0.0,
) -> LosoResult:
    """Rebuild a :class:`LosoResult` from a saved held-out probability table.

    ``ensemble_holdout_probabilities_*.csv`` holds every held-out window's
    ``P(stress)`` from every candidate - the rawest output of a sweep, and the
    thing all the tables and figures are derived from. Reloading it lets the
    report and figures be regenerated without re-running the 16-fold
    evaluation, and it is what makes the report's "any number here can be
    re-derived" claim true rather than aspirational.

    Every per-fold metric is recomputed from the probabilities rather than read
    back, so a regenerated report cannot drift from the numbers it ships with.
    """
    candidates = [c.removeprefix("p_stress_") for c in holdout.columns
                  if c.startswith("p_stress_")]
    if not candidates:
        raise ValueError("No p_stress_* columns found in the held-out table.")

    y_true = holdout["y_true"].to_numpy(dtype=int)
    row_subject = holdout["subject_id"].to_numpy().astype(object)
    probabilities = {
        c: holdout[f"p_stress_{c}"].to_numpy(dtype=float) for c in candidates
    }
    predictions = {c: (p >= threshold).astype(int) for c, p in probabilities.items()}

    # Fold order = order of first appearance, which is the order LOSO produced.
    subjects: list[str] = []
    for subject in row_subject:
        if subject not in subjects:
            subjects.append(str(subject))

    fold_metrics: dict[str, list[dict]] = {c: [] for c in candidates}
    for subject in subjects:
        mask = row_subject == subject
        for candidate in candidates:
            metrics = compute_metrics(
                y_true[mask], predictions[candidate][mask], probabilities[candidate][mask]
            )
            metrics["subject_id"] = subject
            fold_metrics[candidate].append(metrics)

    return LosoResult(
        candidates=candidates,
        subjects=subjects,
        y_true=y_true,
        row_subject=row_subject,
        probabilities=probabilities,
        predictions=predictions,
        fold_metrics=fold_metrics,
        tuned_params=tuned_params or {},
        soft_weights=soft_weights or {},
        meta_coefficients=meta_coefficients or {},
        fit_seconds=fit_seconds,
    )


def nested_loso_single_model(
    name: str,
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    *,
    tune_splits: int = 3,
    compact_grid: bool = True,
    threshold: float = DEFAULT_THRESHOLD,
    n_jobs: int = -1,
) -> dict:
    """Nested LOSO for one model - the honest single-model number.

    Hyperparameters are re-selected inside every outer fold, so the held-out
    subject influences neither the fit nor the model choice. Used by the
    per-model training scripts; the cross-model comparison goes through
    :func:`run_loso_evaluation`, which shares this work across all candidates.
    """
    X, y, groups = np.asarray(X, dtype=float), np.asarray(y), np.asarray(groups)
    probs = np.zeros(len(y), dtype=float)
    fold_metrics: list[dict] = []
    fold_params: dict[str, dict] = {}

    for train_idx, test_idx in LeaveOneGroupOut().split(X, y, groups):
        held_out = str(np.unique(groups[test_idx])[0])
        estimator, params = tune_model(
            name, X[train_idx], y[train_idx], groups[train_idx],
            compact=compact_grid, n_splits=tune_splits, n_jobs=n_jobs,
        )
        fold_params[held_out] = params
        p = stress_proba(estimator, X[test_idx])
        probs[test_idx] = p
        metrics = compute_metrics(y[test_idx], (p >= threshold).astype(int), p)
        metrics["subject_id"] = held_out
        fold_metrics.append(metrics)

    predictions = (probs >= threshold).astype(int)
    pooled = compute_metrics(y, predictions, probs)
    accuracy_mean, accuracy_std, _ = _mean_std([f["accuracy"] for f in fold_metrics])
    macro_mean, macro_std, _ = _mean_std([f["macro_f1"] for f in fold_metrics])
    return {
        "model": name,
        "protocol": "nested LOSO (hyperparameters re-selected per outer fold)",
        "pooled": pooled,
        "accuracy_mean": accuracy_mean,
        "accuracy_std": accuracy_std,
        "macro_f1_mean": macro_mean,
        "macro_f1_std": macro_std,
        "n_folds": len(fold_metrics),
        "fold_metrics": fold_metrics,
        "fold_params": fold_params,
        "probabilities": probs,
        "predictions": predictions,
    }


def loso_probabilities(
    estimator,
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    threshold: float = DEFAULT_THRESHOLD,
) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """LOSO probabilities for a single fixed-hyperparameter estimator.

    Used for quick single-model checks (and by the tests); the full comparison
    goes through :func:`run_loso_evaluation`.
    """
    X, y, groups = np.asarray(X, dtype=float), np.asarray(y), np.asarray(groups)
    probs = np.zeros(len(y), dtype=float)
    fold_metrics: list[dict] = []
    for train_idx, test_idx in LeaveOneGroupOut().split(X, y, groups):
        model = clone(estimator)
        model.fit(X[train_idx], y[train_idx])
        p = stress_proba(model, X[test_idx])
        probs[test_idx] = p
        metrics = compute_metrics(y[test_idx], (p >= threshold).astype(int), p)
        metrics["subject_id"] = str(np.unique(groups[test_idx])[0])
        fold_metrics.append(metrics)
    return probs, (probs >= threshold).astype(int), fold_metrics
