"""Fitting and serialising the deployable artifacts.

Two different things are being produced by this project, and keeping them apart
is what makes the reported numbers honest:

*Reported performance* comes from ``evaluation.run_loso_evaluation`` - nested,
subject-independent, with hyperparameters re-selected inside every outer fold.
That is the number in the report.

*Deployed artifacts* come from this module. A model that ships should be fitted
on every subject available, with hyperparameters chosen by subject-grouped
``GroupKFold`` over that same data. Its grouped CV score is a selection
statistic, not a performance estimate, and is labelled as such everywhere it is
written out.

Artifacts are joblib-serialisable objects that carry their own
:class:`~stress_detection.models.ensemble.EnsembleMetadata`, so the service can
check the feature schema, label map, version and seed of whatever it loads.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.base import BaseEstimator

from .common import BASE_MODEL_NAMES, build_model, tune_model
from .dataset import Dataset
from .ensemble import (
    EnsembleMetadata,
    SoftVotingEnsemble,
    StackingEnsemble,
    build_ensemble_metadata,
    derive_weights_from_oof,
    generate_oof_probabilities,
    library_versions,
)

logger = logging.getLogger(__name__)


@dataclass
class FittedModel:
    name: str
    estimator: BaseEstimator
    params: dict
    cv_score: float | None
    fit_seconds: float


def fit_base_model(
    name: str,
    dataset: Dataset,
    *,
    tune: bool = True,
    compact: bool = False,
    n_splits: int = 5,
    n_jobs: int = -1,
) -> FittedModel:
    """Fit one base model on the whole dataset, tuning with GroupKFold.

    With ``tune=False`` the module defaults are used as-is - useful for a quick
    rebuild when the grid search has already settled.
    """
    started = time.perf_counter()
    if tune:
        estimator, params = tune_model(
            name, dataset.X, dataset.y, dataset.groups,
            compact=compact, n_splits=n_splits, n_jobs=n_jobs,
        )
        # GridSearchCV already refitted on all of (X, y).
        cv_score = _last_best_score(estimator)
    else:
        estimator = build_model(name)
        estimator.fit(dataset.X, dataset.y)
        params = {}
        cv_score = None
    elapsed = time.perf_counter() - started
    logger.info("Fitted %s in %.1fs (params=%s)", name, elapsed, params)
    return FittedModel(name, estimator, params, cv_score, elapsed)


def _last_best_score(estimator) -> float | None:
    """The grouped CV score that selected these hyperparameters (see
    ``common.tune_model``). A selection statistic, not a performance estimate."""
    return getattr(estimator, "grouped_cv_score_", None)


def fit_all_base_models(
    dataset: Dataset,
    *,
    model_names: tuple[str, ...] = BASE_MODEL_NAMES,
    tune: bool = True,
    n_jobs: int = -1,
) -> dict[str, FittedModel]:
    return {
        name: fit_base_model(name, dataset, tune=tune, n_jobs=n_jobs)
        for name in model_names
    }


def fit_soft_voting(
    dataset: Dataset,
    fitted: dict[str, FittedModel],
    *,
    weights: dict[str, float] | None = None,
    model_names: tuple[str, ...] = BASE_MODEL_NAMES,
    model_version: str = "v1",
    evaluation: dict | None = None,
) -> SoftVotingEnsemble:
    """Assemble a soft-voting artifact from already-tuned base models.

    ``weights=None`` gives the equal-weight ensemble, which §7 keeps as the
    primary soft-voting baseline.
    """
    ensemble = SoftVotingEnsemble(
        {name: build_model(name, **_strip(fitted[name].params)) for name in model_names},
        weights=weights,
        model_names=model_names,
        feature_names=dataset.feature_names,
    )
    ensemble.fit(dataset.X, dataset.y)
    ensemble.metadata = build_ensemble_metadata(
        ensemble,
        model_type="soft_voting",
        model_version=model_version,
        feature_names=dataset.feature_names,
        dataset=dataset.description,
        n_subjects=dataset.n_subjects,
        n_windows=dataset.n_windows,
        base_model_params={n: fitted[n].params for n in model_names},
        evaluation=evaluation,
    )
    return ensemble


def fit_stacking(
    dataset: Dataset,
    fitted: dict[str, FittedModel],
    *,
    model_names: tuple[str, ...] = BASE_MODEL_NAMES,
    n_oof_splits: int = 5,
    model_version: str = "v1",
    evaluation: dict | None = None,
) -> StackingEnsemble:
    """Assemble the stacking artifact: grouped OOF → LogisticRegression → refit.

    ``StackingEnsemble.fit`` does the leakage-safe work; all this adds is the
    tuned base-model hyperparameters and the artifact metadata.
    """
    ensemble = StackingEnsemble(
        {name: build_model(name, **_strip(fitted[name].params)) for name in model_names},
        model_names=model_names,
        n_oof_splits=n_oof_splits,
        feature_names=dataset.feature_names,
    )
    ensemble.fit(dataset.X, dataset.y, dataset.groups)
    ensemble.metadata = build_ensemble_metadata(
        ensemble,
        model_type="stacking",
        model_version=model_version,
        feature_names=dataset.feature_names,
        dataset=dataset.description,
        n_subjects=dataset.n_subjects,
        n_windows=dataset.n_windows,
        base_model_params={n: fitted[n].params for n in model_names},
        evaluation=evaluation,
    )
    return ensemble


def derive_soft_voting_weights(
    dataset: Dataset,
    fitted: dict[str, FittedModel],
    *,
    model_names: tuple[str, ...] = BASE_MODEL_NAMES,
    n_splits: int = 5,
) -> dict[str, float]:
    """Weights for the learned-weight soft-voting experiment.

    Derived from grouped OOF probabilities over the training data, so no
    window's own model ever votes on its weight.
    """
    base = {name: build_model(name, **_strip(fitted[name].params)) for name in model_names}
    oof = generate_oof_probabilities(
        base, dataset.X, dataset.y, dataset.groups,
        model_names=model_names, n_splits=n_splits,
    )
    return derive_weights_from_oof(oof, dataset.y, model_names)


def _strip(params: dict) -> dict:
    """Drop GridSearchCV's ``step__`` prefixes - the builders re-add them."""
    return {k.split("__", 1)[-1]: v for k, v in params.items()}


# --------------------------------------------------------------------------
# Serialisation (§11, §12)
# --------------------------------------------------------------------------


def save_single_model(
    fitted: FittedModel,
    dataset: Dataset,
    path: Path,
    *,
    model_version: str,
) -> Path:
    """Serialise a base model together with its §12 metadata.

    The metadata is attached to the estimator rather than written beside it, so
    the artifact stays a single joblib file and the schema guard can read the
    feature contract straight off whatever it loaded.
    """
    metadata = EnsembleMetadata(
        model_type=fitted.name,
        model_version=model_version,
        feature_names=list(dataset.feature_names),
        base_model_names=[fitted.name],
        base_model_params={fitted.name: fitted.params},
        dataset=dataset.description,
        n_subjects=dataset.n_subjects,
        n_windows=dataset.n_windows,
        trained_at=_now(),
        library_versions=library_versions(),
    )
    try:
        fitted.estimator.metadata = metadata
    except AttributeError:  # pragma: no cover - sklearn estimators allow this
        logger.warning("Could not attach metadata to %s", fitted.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(fitted.estimator, path)
    logger.info("Saved %s → %s", fitted.name, path)
    return path


def save_ensemble(ensemble, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(ensemble, path)
    logger.info("Saved %s → %s", type(ensemble).__name__, path)
    return path


def write_json(payload: Any, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as handle:
        json.dump(payload, handle, indent=2, default=_json_default)
    logger.info("Wrote %s", path)
    return path


def _json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Not JSON serialisable: {type(value)}")


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Latency benchmark (§15)
# --------------------------------------------------------------------------


def benchmark_latency(
    models: dict[str, Any], X: np.ndarray, *, n_repeats: int = 200
) -> dict[str, dict[str, float]]:
    """Single-row ``predict_proba`` latency, which is what the live loop does.

    The service scores one 18-feature window roughly every 5 s, so per-row
    latency (not throughput) is the number that matters. A few warm-up calls
    are discarded first - the first call through a fresh pipeline pays
    one-off allocation costs that never recur in the running service.
    """
    row = np.asarray(X, dtype=float)[:1]
    results: dict[str, dict[str, float]] = {}
    for name, model in models.items():
        for _ in range(5):
            model.predict_proba(row)
        timings = []
        for _ in range(n_repeats):
            started = time.perf_counter()
            model.predict_proba(row)
            timings.append((time.perf_counter() - started) * 1000.0)
        arr = np.array(timings)
        results[name] = {
            "mean_ms": float(arr.mean()),
            "median_ms": float(np.median(arr)),
            "p95_ms": float(np.percentile(arr, 95)),
            "max_ms": float(arr.max()),
            "n_repeats": int(n_repeats),
        }
        logger.info("%s: %.2f ms/prediction (median)", name, results[name]["median_ms"])
    return results
