"""Soft-voting and leakage-safe stacking ensembles over the four base models.

Both ensembles are plain Python objects that satisfy the same contract as any
single base model - ``fit`` / ``predict`` / ``predict_proba``, with
``predict_proba(X)[:, 1] == P(stress)`` - and both expose ``classes_``,
``n_features_in_`` and ``feature_names_in_`` so the service's schema guard can
validate them exactly like the SVM pipeline. That is what lets the inference
layer swap models from config without any application code changing.

Leakage safety
--------------
Stacking is the part that is easy to get wrong. The invalid recipe is:

    train every base model on all data -> predict the same data ->
    train the meta-model on those predictions

because the base predictions on their own training rows are optimistic, and the
meta-model learns to trust them. :func:`generate_oof_probabilities` instead
produces *out-of-fold* meta-features with ``GroupKFold`` over ``subject_id``:
each block of predictions is made by a clone that was fitted without that
subject. The disjointness is asserted per fold at runtime, not just documented.

``StackingEnsemble.fit`` therefore does, on whatever data it is handed:

    1. grouped OOF probabilities for all four base models
    2. fit the LogisticRegression meta-model on those OOF probabilities
    3. refit each base model on the full handed-in data (for serving)

When that data is the training portion of an outer LOSO fold, the held-out
subject took part in none of the three steps.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
from sklearn.base import BaseEstimator, clone
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from .common import (
    BASE_MODEL_NAMES,
    LABEL_MAP,
    RANDOM_SEED,
    build_model,
    grouped_cv,
    stress_proba,
)

logger = logging.getLogger(__name__)

# P(stress) >= THRESHOLD -> stress. Matches the existing application semantics
# (argmax over two classes); §10 says not to move it without an experiment.
DEFAULT_THRESHOLD = 0.5


# --------------------------------------------------------------------------
# Artifact metadata (§12, §16)
# --------------------------------------------------------------------------


@dataclass
class EnsembleMetadata:
    """Everything needed to identify and validate a serialised ensemble."""

    model_type: str                      # "soft_voting" | "stacking"
    model_version: str                   # e.g. "v3"
    feature_names: list[str]             # canonical 18, in training order
    feature_schema_version: str = "v1"
    label_map: dict[str, int] = field(default_factory=lambda: dict(LABEL_MAP))
    base_model_names: list[str] = field(default_factory=lambda: list(BASE_MODEL_NAMES))
    base_model_params: dict[str, dict] = field(default_factory=dict)
    meta_model: str | None = None
    weights: dict[str, float] | None = None
    threshold: float = DEFAULT_THRESHOLD
    random_seed: int = RANDOM_SEED
    dataset: str = ""
    n_subjects: int = 0
    n_windows: int = 0
    trained_at: str = ""
    library_versions: dict[str, str] = field(default_factory=dict)
    evaluation: dict[str, Any] = field(default_factory=dict)
    requires_calibration: bool = False
    calibration_seconds: int | None = None
    calibration_transform: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def library_versions() -> dict[str, str]:
    """Record the libraries whose pickles/ABI the artifact depends on."""
    import sklearn

    versions = {"scikit-learn": sklearn.__version__, "numpy": np.__version__}
    try:
        import xgboost

        versions["xgboost"] = xgboost.__version__
    except Exception:  # pragma: no cover - optional dependency
        pass
    return versions


# --------------------------------------------------------------------------
# Leakage-safe out-of-fold generation (§8.1)
# --------------------------------------------------------------------------


def generate_oof_probabilities(
    base_models: dict[str, BaseEstimator],
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    *,
    model_names: list[str] | tuple[str, ...] | None = None,
    n_splits: int = 5,
) -> np.ndarray:
    """Return an ``(n_samples, n_models)`` matrix of out-of-fold P(stress).

    Column ``j`` holds P(stress) for ``model_names[j]``. Every row is predicted
    by a clone fitted on folds that contain **none** of that row's subject -
    enforced by ``GroupKFold`` and re-checked with an explicit disjointness
    assertion per fold, so a future refactor cannot quietly reintroduce leakage.

    ``groups`` is mandatory. There is no ungrouped code path.
    """
    names = list(model_names or base_models.keys())
    X = np.asarray(X)
    y = np.asarray(y)
    groups = np.asarray(groups)

    oof = np.full((len(y), len(names)), np.nan, dtype=float)
    filled = np.zeros(len(y), dtype=bool)

    cv = grouped_cv(groups, n_splits)
    for fold, (train_idx, test_idx) in enumerate(cv.split(X, y, groups)):
        train_subjects = set(np.unique(groups[train_idx]).tolist())
        test_subjects = set(np.unique(groups[test_idx]).tolist())
        if train_subjects & test_subjects:
            raise AssertionError(
                "OOF leakage: subjects "
                f"{sorted(train_subjects & test_subjects)} appear in both the "
                f"fitting and prediction halves of inner fold {fold}."
            )

        for col, name in enumerate(names):
            model = clone(base_models[name])
            model.fit(X[train_idx], y[train_idx])
            oof[test_idx, col] = stress_proba(model, X[test_idx])
        filled[test_idx] = True

    if not filled.all():
        raise AssertionError(
            f"{(~filled).sum()} rows never received an OOF prediction."
        )
    return oof


def derive_weights_from_oof(
    oof: np.ndarray,
    y: np.ndarray,
    model_names: list[str] | tuple[str, ...],
) -> dict[str, float]:
    """Validation-derived soft-voting weights, normalised to sum to 1.

    Each model's weight is proportional to how far its OOF ROC-AUC sits above
    chance: ``w_i ∝ max(0, AUC_i - 0.5)``. Deliberately simple and fully
    determined by the inputs - no search, no randomness, nothing to tune. §7
    prefers exactly this over an elaborate optimiser that would be harder to
    trust and easier to overfit.

    ``oof`` must be out-of-fold probabilities from the *training* portion only,
    so the held-out LOSO subject never influences the weights (§7, §8.1).
    Degenerate case - no model beats chance - falls back to equal weights.
    """
    names = list(model_names)
    scores = []
    for col, _name in enumerate(names):
        try:
            auc = roc_auc_score(y, oof[:, col])
        except ValueError:  # single class present in y
            auc = 0.5
        scores.append(max(0.0, float(auc) - 0.5))

    total = sum(scores)
    if total <= 0:
        logger.warning(
            "derive_weights_from_oof: no base model beat chance on OOF "
            "(all AUC <= 0.5) - falling back to equal weights %r. A caller "
            "reading only the returned dict cannot tell this apart from a "
            "genuine tie between models; check this log if that distinction "
            "matters.", {name: round(1.0 / len(names), 4) for name in names},
        )
        return {name: 1.0 / len(names) for name in names}
    return {name: score / total for name, score in zip(names, scores)}


def _normalised_weights(
    weights: dict[str, float] | None, names: list[str]
) -> dict[str, float]:
    if weights is None:
        return {name: 1.0 / len(names) for name in names}
    missing = set(names) - set(weights)
    if missing:
        raise ValueError(f"Missing weights for base model(s): {sorted(missing)}")
    values = np.array([float(weights[n]) for n in names])
    if (values < 0).any():
        raise ValueError(f"Soft-voting weights must be non-negative, got {weights}")
    total = values.sum()
    if total <= 0:
        raise ValueError("Soft-voting weights sum to zero.")
    if not np.isclose(total, 1.0, atol=1e-6):
        logger.info("Normalising soft-voting weights (sum was %.6f).", total)
    return {name: float(v / total) for name, v in zip(names, values)}


# --------------------------------------------------------------------------
# Shared base
# --------------------------------------------------------------------------


class _BaseEnsemble:
    """Common plumbing: base-model storage, schema attributes, predict()."""

    def __init__(
        self,
        base_models: dict[str, BaseEstimator] | None = None,
        *,
        model_names: list[str] | tuple[str, ...] = BASE_MODEL_NAMES,
        feature_names: list[str] | None = None,
        threshold: float = DEFAULT_THRESHOLD,
        metadata: EnsembleMetadata | None = None,
    ):
        self.model_names = list(model_names)
        if base_models is None:
            base_models = {name: build_model(name) for name in self.model_names}
        missing = set(self.model_names) - set(base_models)
        if missing:
            raise ValueError(f"No estimator supplied for base model(s): {sorted(missing)}")
        self.base_models = {name: base_models[name] for name in self.model_names}
        self.threshold = float(threshold)
        self.metadata = metadata
        self.classes_ = np.array([0, 1])
        self.n_features_in_: int | None = None
        if feature_names is not None:
            self.feature_names_in_ = list(feature_names)

    # -- schema -------------------------------------------------------------

    def _record_shape(self, X: np.ndarray) -> None:
        self.n_features_in_ = int(np.asarray(X).shape[1])

    def _check_shape(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        if X.ndim != 2:
            raise ValueError(f"Expected a 2-D feature matrix, got shape {X.shape}.")
        if self.n_features_in_ is not None and X.shape[1] != self.n_features_in_:
            raise ValueError(
                f"{type(self).__name__} expects {self.n_features_in_} features, "
                f"got {X.shape[1]}."
            )
        return X

    # -- probabilities ------------------------------------------------------

    def base_probabilities(self, X: np.ndarray) -> dict[str, np.ndarray]:
        """P(stress) per base model, as ``{name: ndarray}``."""
        X = self._check_shape(X)
        return {name: stress_proba(self.base_models[name], X) for name in self.model_names}

    def _base_matrix(self, X: np.ndarray) -> np.ndarray:
        """Base probabilities as an ``(n, n_models)`` matrix in canonical order."""
        probs = self.base_probabilities(X)
        return np.column_stack([probs[name] for name in self.model_names])

    def predict_proba(self, X: np.ndarray) -> np.ndarray:  # pragma: no cover - abstract
        raise NotImplementedError

    def predict(self, X: np.ndarray) -> np.ndarray:
        """``P(stress) >= threshold -> 1 (stress)``, else 0 (baseline)."""
        p = self.predict_proba(X)[:, 1]
        return (p >= self.threshold).astype(int)


# --------------------------------------------------------------------------
# Soft voting (§7)
# --------------------------------------------------------------------------


class SoftVotingEnsemble(_BaseEnsemble):
    """Weighted average of the base models' P(stress).

        P_ensemble = w_svm*P_svm + w_rf*P_rf + w_xgb*P_xgb + w_mlp*P_mlp

    Weights are non-negative and normalised to sum to 1 at construction. The
    default is equal weighting (0.25 each), which §7 keeps as the primary
    soft-voting baseline; validation-derived weights from
    :func:`derive_weights_from_oof` are a separately labelled experiment.
    """

    def __init__(
        self,
        base_models: dict[str, BaseEstimator] | None = None,
        weights: dict[str, float] | None = None,
        **kwargs: Any,
    ):
        super().__init__(base_models, **kwargs)
        self.weights = _normalised_weights(weights, self.model_names)

    @property
    def weight_vector(self) -> np.ndarray:
        return np.array([self.weights[n] for n in self.model_names], dtype=float)

    def fit(self, X: np.ndarray, y: np.ndarray, groups: np.ndarray | None = None):
        """Fit every base model on ``(X, y)``.

        ``groups`` is accepted and ignored so callers can treat both ensembles
        uniformly; soft voting has nothing to learn that could leak - the
        weights are fixed before fitting.
        """
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        self._record_shape(X)
        for name in self.model_names:
            self.base_models[name].fit(X, y)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        p_stress = self._base_matrix(X) @ self.weight_vector
        p_stress = np.clip(p_stress, 0.0, 1.0)
        return np.column_stack([1.0 - p_stress, p_stress])


# --------------------------------------------------------------------------
# Stacking (§8)
# --------------------------------------------------------------------------


class StackingEnsemble(_BaseEnsemble):
    """Four base probabilities -> LogisticRegression meta-model -> P(stress).

    The meta-feature vector is ``[P_svm, P_rf, P_xgb, P_mlp]`` in
    :data:`~stress_detection.models.common.BASE_MODEL_NAMES` order, and that
    order is pinned in the artifact metadata so serving cannot permute it.
    """

    def __init__(
        self,
        base_models: dict[str, BaseEstimator] | None = None,
        meta_model: BaseEstimator | None = None,
        *,
        n_oof_splits: int = 5,
        **kwargs: Any,
    ):
        super().__init__(base_models, **kwargs)
        # Small, well-regularised LR: with only four correlated inputs there is
        # nothing to gain from a larger meta-model, and a linear one keeps the
        # learned base-model weighting readable via coef_.
        self.meta_model = meta_model or LogisticRegression(
            C=1.0, max_iter=1000, random_state=RANDOM_SEED
        )
        self.n_oof_splits = int(n_oof_splits)
        self.oof_probabilities_: np.ndarray | None = None

    def fit(self, X: np.ndarray, y: np.ndarray, groups: np.ndarray):
        """Leakage-safe fit. ``groups`` (subject ids) is **required**.

        See the module docstring for the three steps. Nothing in this method
        ever sees data outside ``(X, y, groups)``, so calling it with an outer
        LOSO fold's training portion keeps the held-out subject clean.
        """
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        groups = np.asarray(groups)
        if groups.shape[0] != X.shape[0]:
            raise ValueError(
                f"groups has {groups.shape[0]} entries for {X.shape[0]} samples."
            )
        self._record_shape(X)

        # 1. grouped out-of-fold meta-features
        oof = generate_oof_probabilities(
            self.base_models, X, y, groups,
            model_names=self.model_names, n_splits=self.n_oof_splits,
        )
        self.oof_probabilities_ = oof

        # 2. meta-model sees OOF predictions only - never in-sample ones
        self.meta_model.fit(oof, y)

        # 3. refit the base models on everything we were handed, for serving
        for name in self.model_names:
            self.base_models[name].fit(X, y)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.oof_probabilities_ is None:
            raise ValueError("StackingEnsemble is not fitted - call fit() first.")
        meta_X = self._base_matrix(X)
        proba = np.asarray(self.meta_model.predict_proba(meta_X))
        classes = [int(c) for c in np.asarray(self.meta_model.classes_).ravel()]
        if 1 not in classes:
            raise ValueError(
                f"Meta-model was fitted without the stress class ({classes})."
            )
        p_stress = proba[:, classes.index(1)]
        return np.column_stack([1.0 - p_stress, p_stress])

    @property
    def meta_coefficients(self) -> dict[str, float]:
        """Meta-model weight per base model - readable model attribution."""
        coefs = np.asarray(self.meta_model.coef_).ravel()
        return {name: float(c) for name, c in zip(self.model_names, coefs)}


def build_ensemble_metadata(
    ensemble: _BaseEnsemble,
    *,
    model_type: str,
    model_version: str,
    feature_names: list[str],
    dataset: str,
    n_subjects: int,
    n_windows: int,
    base_model_params: dict[str, dict] | None = None,
    evaluation: dict[str, Any] | None = None,
) -> EnsembleMetadata:
    """Assemble the §12 artifact metadata for a fitted ensemble."""
    return EnsembleMetadata(
        model_type=model_type,
        model_version=model_version,
        feature_names=list(feature_names),
        base_model_names=list(ensemble.model_names),
        base_model_params=base_model_params or {},
        meta_model=(
            type(ensemble.meta_model).__name__
            if isinstance(ensemble, StackingEnsemble)
            else None
        ),
        weights=(
            dict(ensemble.weights) if isinstance(ensemble, SoftVotingEnsemble) else None
        ),
        threshold=ensemble.threshold,
        dataset=dataset,
        n_subjects=n_subjects,
        n_windows=n_windows,
        trained_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        library_versions=library_versions(),
        evaluation=evaluation or {},
    )
