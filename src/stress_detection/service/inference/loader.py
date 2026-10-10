"""Model resolution, type detection, and the schema guard (§13, §14).

The service is told *which kind* of model to serve (``inference.model_type``)
and *where* it lives (``inference.model_path``). This module turns that pair
into a loaded, validated estimator, and it is deliberately strict: a model
whose feature contract does not match the canonical 22 columns is refused at
startup rather than quietly served, because a silent mismatch produces
plausible-looking probabilities computed from misaligned columns.

Fallback (§14): if the configured artifact does not exist yet - the normal
state before ``scripts/train_all_models.py`` has been run - and a fallback path
is configured and present, the fallback is loaded with a loud warning. That is
what keeps the existing SVM deployment working while the ensemble artifacts are
still being generated.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import joblib

logger = logging.getLogger(__name__)

# Config value -> canonical internal name. The aliases exist because §14 writes
# the stacking target as "ensemble_stack" while §18 calls the row "Stacking".
MODEL_TYPE_ALIASES: dict[str, str] = {
    "svm": "svm",
    "random_forest": "random_forest",
    "rf": "random_forest",
    "xgboost": "xgboost",
    "xgb": "xgboost",
    "mlp": "mlp",
    "soft_voting": "soft_voting",
    "ensemble_soft": "soft_voting",
    "stacking": "stacking",
    "ensemble_stack": "stacking",
}

SUPPORTED_MODEL_TYPES = tuple(sorted(set(MODEL_TYPE_ALIASES.values())))

_VERSION_RE = re.compile(r"_v(\d+)")


def normalise_model_type(model_type: str) -> str:
    """Map a configured ``model_type`` onto its canonical name."""
    key = str(model_type).strip().lower()
    if key not in MODEL_TYPE_ALIASES:
        raise ValueError(
            f"Unsupported inference.model_type '{model_type}'. "
            f"Supported: {', '.join(SUPPORTED_MODEL_TYPES)} "
            f"(aliases: {', '.join(sorted(MODEL_TYPE_ALIASES))})."
        )
    return MODEL_TYPE_ALIASES[key]


def resolve_model_path(model_path: Path, fallback_path: Path | None = None) -> tuple[Path, bool]:
    """Resolve ``model_path`` to a concrete file. Returns ``(path, used_fallback)``.

    A path containing a glob (``ensemble_stack_*.joblib``, as §14 writes it)
    matches the highest ``_v<N>`` version present, so bumping a model version
    needs no config edit.
    """
    resolved = _expand(model_path)
    if resolved is not None:
        return resolved, False

    if fallback_path is not None:
        fallback = _expand(fallback_path)
        if fallback is not None:
            logger.warning(
                "Configured model %s not found - falling back to %s. "
                "Run scripts/train_all_models.py to generate the ensemble artifacts.",
                model_path, fallback,
            )
            return fallback, True

    raise FileNotFoundError(
        f"No model artifact at {model_path}"
        + (f" (and no fallback at {fallback_path})" if fallback_path else "")
    )


def _expand(path: Path) -> Path | None:
    """Return a concrete existing file for ``path``, resolving globs."""
    if any(ch in str(path) for ch in "*?["):
        matches = sorted(path.parent.glob(path.name), key=_version_key)
        return matches[-1] if matches else None
    return path if path.exists() else None


def _version_key(path: Path) -> tuple[int, str]:
    match = _VERSION_RE.search(path.stem)
    return (int(match.group(1)) if match else -1, path.name)


def detect_model_type(model) -> str:
    """Best-effort canonical type name for a loaded estimator."""
    from stress_detection.models.ensemble import SoftVotingEnsemble, StackingEnsemble

    if isinstance(model, StackingEnsemble):
        return "stacking"
    if isinstance(model, SoftVotingEnsemble):
        return "soft_voting"

    metadata = getattr(model, "metadata", None)
    declared = getattr(metadata, "model_type", None)
    if declared:
        return normalise_model_type(declared)

    estimator = model
    steps = getattr(model, "named_steps", None)
    if steps:
        estimator = list(steps.values())[-1]
    by_class = {
        "SVC": "svm",
        "RandomForestClassifier": "random_forest",
        "XGBClassifier": "xgboost",
        "MLPClassifier": "mlp",
    }
    return by_class.get(type(estimator).__name__, "unknown")


def validate_model_schema(model, feature_columns: list[str], *, label: str = "model") -> None:
    """Refuse any model whose feature contract is not the canonical 22 columns.

    Checks, for the model and (recursively) for each base model of an ensemble:

    * ``n_features_in_`` equals ``len(feature_columns)`` when exposed
    * ``feature_names_in_`` equals ``feature_columns`` in order when exposed
    * ``predict_proba`` exists - the whole pipeline is probability-based

    Attributes that a model does not expose are skipped rather than guessed at;
    the Phase 1 SVM pipelines were fitted on NumPy arrays and so carry
    ``n_features_in_`` but not ``feature_names_in_``.
    """
    expected = len(feature_columns)

    n_in = getattr(model, "n_features_in_", None)
    if n_in is not None and int(n_in) != expected:
        raise ValueError(
            f"{label} expects {n_in} features but the canonical schema has "
            f"{expected}. Schema mismatch - refusing to load."
        )

    names = getattr(model, "feature_names_in_", None)
    if names is not None and list(names) != list(feature_columns):
        raise ValueError(
            f"{label} feature_names_in_ does not match the canonical feature "
            "order. Schema mismatch - refusing to load."
        )

    if not hasattr(model, "predict_proba"):
        raise ValueError(f"{label} has no predict_proba - confidence unavailable.")

    metadata = getattr(model, "metadata", None)
    meta_features = getattr(metadata, "feature_names", None)
    if meta_features is not None and list(meta_features) != list(feature_columns):
        raise ValueError(
            f"{label} artifact metadata records a different feature schema than "
            "the canonical one. Refusing to load."
        )

    base_models = getattr(model, "base_models", None)
    if isinstance(base_models, dict):
        if not base_models:
            raise ValueError(f"{label} is an ensemble with no base models.")
        for name, base in base_models.items():
            if base is None:
                raise ValueError(f"{label} is missing its '{name}' base model.")
            validate_model_schema(base, feature_columns, label=f"{label}.{name}")

        meta_model = getattr(model, "meta_model", None)
        if meta_model is not None:
            if not hasattr(meta_model, "predict_proba"):
                raise ValueError(f"{label} meta-model has no predict_proba.")
            n_meta = getattr(meta_model, "n_features_in_", None)
            if n_meta is not None and int(n_meta) != len(base_models):
                raise ValueError(
                    f"{label} meta-model expects {n_meta} inputs but the ensemble "
                    f"has {len(base_models)} base models."
                )


def load_model(
    model_path: Path,
    feature_columns: list[str],
    *,
    expected_type: str | None = None,
    fallback_path: Path | None = None,
) -> tuple[object, str, Path]:
    """Load, validate, and type-check a model artifact.

    Returns ``(model, model_type, path)``. When ``expected_type`` is given and
    the artifact on disk is a different kind of model, this raises - an
    ensemble config pointed at an SVM artifact is a configuration bug, not
    something to paper over. The one exception is the fallback path, whose type
    is reported as-is.
    """
    path, used_fallback = resolve_model_path(model_path, fallback_path)

    try:
        model = joblib.load(path)
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            f"Cannot unpickle {path.name}: {exc}. An ensemble artifact needs its "
            "base-model libraries installed (e.g. xgboost)."
        ) from exc

    validate_model_schema(model, feature_columns, label=path.name)
    actual_type = detect_model_type(model)

    if expected_type is not None and not used_fallback:
        wanted = normalise_model_type(expected_type)
        if actual_type != wanted:
            raise ValueError(
                f"inference.model_type is '{expected_type}' (→ {wanted}) but "
                f"{path.name} is a '{actual_type}' model. Refusing to load a "
                "mismatched artifact."
            )

    if used_fallback:
        logger.warning("Serving FALLBACK model %s (type=%s).", path.name, actual_type)
    return model, actual_type, path
