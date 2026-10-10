"""Evaluation report utilities for the stress detection SVM.

All functions accept scikit-learn compatible objects and return DataFrames
or save matplotlib figures - no file-path side-effects inside this module.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance as sk_permutation_importance
from sklearn.metrics import classification_report, confusion_matrix, precision_score, recall_score, f1_score


def feature_importance(
    model,
    X: np.ndarray | pd.DataFrame,
    y: np.ndarray,
    n_repeats: int = 10,
    random_state: int = 42,
) -> pd.DataFrame:
    """Compute permutation feature importance on a fitted model.

    Args:
        model: A fitted scikit-learn estimator (e.g., Pipeline).
        X: Feature matrix - raw features before scaling (the Pipeline handles scaling).
        y: True binary labels.
        n_repeats: Number of permutation repeats per feature.
        random_state: RNG seed for reproducibility.

    Returns:
        DataFrame sorted descending by importance_mean with columns:
            feature, importance_mean, importance_std
    """
    if isinstance(X, pd.DataFrame):
        feature_names = list(X.columns)
        X_arr = X.to_numpy(dtype=float)
    else:
        feature_names = [f"feature_{i}" for i in range(X.shape[1])]
        X_arr = np.asarray(X, dtype=float)

    result = sk_permutation_importance(
        model, X_arr, y,
        n_repeats=n_repeats,
        random_state=random_state,
        scoring="f1_macro",
    )

    df = pd.DataFrame({
        "feature": feature_names,
        "importance_mean": result.importances_mean,
        "importance_std": result.importances_std,
    }).sort_values("importance_mean", ascending=False).reset_index(drop=True)

    return df


def per_class_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    class_names: list[str] | None = None,
) -> pd.DataFrame:
    """Compute per-class precision, recall, F1, and support.

    Args:
        y_true: True binary labels.
        y_pred: Predicted binary labels.
        class_names: Display names for classes (default: ["baseline", "stress"]).

    Returns:
        DataFrame with columns: class, precision, recall, f1, support.
    """
    if class_names is None:
        class_names = ["baseline", "stress"]

    labels = list(range(len(class_names)))
    precision = precision_score(y_true, y_pred, average=None, labels=labels, zero_division=0)
    recall = recall_score(y_true, y_pred, average=None, labels=labels, zero_division=0)
    f1 = f1_score(y_true, y_pred, average=None, labels=labels, zero_division=0)
    support = np.bincount(np.asarray(y_true, dtype=int), minlength=len(class_names))

    return pd.DataFrame({
        "class": class_names,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "support": support,
    })


def confusion_matrix_plot(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    labels: list[str],
    title: str,
    save_path: Path,
) -> None:
    """Save a labelled confusion matrix heatmap as a PNG.

    Args:
        y_true: True binary labels.
        y_pred: Predicted binary labels.
        labels: Class display names (e.g. ["baseline", "stress"]).
        title: Plot title.
        save_path: Destination path for the PNG.
    """
    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(labels))))
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(cm, cmap="Blues")
    plt.colorbar(im, ax=ax)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(title)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", fontsize=14,
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    plt.tight_layout()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(save_path, dpi=150)
    plt.close()
