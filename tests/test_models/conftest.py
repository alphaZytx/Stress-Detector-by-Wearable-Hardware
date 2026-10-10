"""Synthetic grouped fixtures for the model/ensemble tests.

Nothing here touches the real dataset: these tests must pass on a fresh clone
with no WESAD download and no trained artifacts.

The dataset deliberately encodes the subject index in **feature column 0**.
That is what lets the leakage tests observe, from inside an estimator's
``fit``, exactly which subjects it was shown - see ``test_leakage.py``.
"""

from __future__ import annotations

import numpy as np
import pytest

from stress_detection.service.features.schema import FEATURE_COLUMNS

N_FEATURES = len(FEATURE_COLUMNS)


def make_grouped_dataset(
    n_subjects: int = 6,
    n_per_subject: int = 40,
    n_features: int = N_FEATURES,
    seed: int = 0,
    separation: float = 1.6,
):
    """Return ``(X, y, groups)`` - a learnable, subject-grouped binary problem.

    Column 0 is the subject index (so a fitted estimator can be asked which
    subjects it saw). Each subject contributes both classes, so every LOSO fold
    has two classes and ROC-AUC is defined.
    """
    rng = np.random.default_rng(seed)
    X_parts, y_parts, g_parts = [], [], []

    for subject in range(n_subjects):
        half = n_per_subject // 2
        labels = np.array([0] * half + [1] * (n_per_subject - half))
        features = rng.normal(0.0, 1.0, size=(n_per_subject, n_features))
        # Class signal on a few columns, plus a per-subject offset so subjects
        # are not interchangeable (which is what makes LOSO non-trivial).
        features[:, 1:5] += separation * labels[:, None]
        features[:, 5:8] += rng.normal(0.0, 0.5, size=(1, 3))
        features[:, 0] = subject
        X_parts.append(features)
        y_parts.append(labels)
        g_parts.append(np.full(n_per_subject, f"S{subject}", dtype=object))

    return (
        np.vstack(X_parts),
        np.concatenate(y_parts),
        np.concatenate(g_parts),
    )


@pytest.fixture
def grouped_data():
    return make_grouped_dataset()


@pytest.fixture
def small_grouped_data():
    """Smaller variant for tests that fit many models."""
    return make_grouped_dataset(n_subjects=4, n_per_subject=24)
