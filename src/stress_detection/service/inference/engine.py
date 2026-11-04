"""Inference engine - load the configured model, predict, and smooth predictions.

Smoothing is essential, not optional: ~12% per-window misclassification means
raw predictions flicker. EMA (default) smooths P(stress); majority vote is the
alternative. Smoothing lives here and only here - no model implements its own.

Model contract (deviation from the prompt, documented):
  The Phase 1 SVM pipelines were fitted on a NumPy array, so they expose
  ``n_features_in_`` (=18) and integer ``classes_`` ([0, 1]) but NOT
  ``feature_names_in_``. We therefore validate ``n_features_in_`` against the
  canonical FEATURE_COLUMNS length and feed the model a NumPy row ordered by
  FEATURE_COLUMNS (the exact training order). If a model DOES carry
  ``feature_names_in_`` (e.g. an ensemble artifact, which records it), we
  additionally assert it matches FEATURE_COLUMNS. Integer classes map
  0→baseline, 1→stress (label_map = {"baseline": 0, "stress": 1}).

Which model is served is a config question, not a code question: any of
``svm``, ``random_forest``, ``xgboost``, ``mlp``, ``soft_voting`` or
``stacking`` or ``personalized_extra_trees`` loads through the same path (see
``loader.py``) and hands back the same :class:`Prediction`. Everything
downstream - EMA, the WebSocket envelope, the dashboard - is unchanged.
"""

from __future__ import annotations

import logging
from collections import deque
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel

from stress_detection.features.calibration import (
    apply_relative_baseline,
    has_complete_baseline,
)

from ..features.schema import FEATURE_COLUMNS
from .loader import load_model

logger = logging.getLogger(__name__)

# Integer class label → human name. Matches Phase 1 training label_map.
_CLASS_NAMES = {0: "baseline", 1: "stress"}


class CalibrationOffsets(BaseModel):
    """Per-user resting means captured by the two-minute calibration screen.

    The personalized model was explicitly trained on the matching relative
    representation. Older model artifacts retain their backward-compatible
    subtraction heuristic when selected directly.
    """

    hr_baseline: float | None = None
    gsr_baseline: float | None = None
    temp_baseline: float | None = None

    def is_active(self) -> bool:
        return any(
            v is not None
            for v in (self.hr_baseline, self.gsr_baseline, self.temp_baseline)
        )

    def is_complete(self) -> bool:
        return has_complete_baseline(
            self.hr_baseline, self.gsr_baseline, self.temp_baseline
        )


class Prediction(BaseModel):
    timestamp_ms: int
    label: Literal["baseline", "stress"]
    confidence: float
    smoothed_label: Literal["baseline", "stress"]
    smoothed_confidence: float
    raw_proba: dict[str, float]
    calibration_applied: bool = False
    # Added for the ensemble work (§21). Both are additive and optional, so the
    # existing frontend contract - label, smoothed_confidence,
    # calibration_applied - is untouched. base_probabilities is populated only
    # when an ensemble is serving; a single model leaves it null.
    model_type: str = "svm"
    base_probabilities: dict[str, float] | None = None


class InferenceEngine:
    def __init__(
        self,
        model_path: Path,
        smoothing_method: str = "ema",
        smoothing_window: int = 6,
        ema_alpha: float = 0.3,
        *,
        model_type: str | None = None,
        fallback_model_path: Path | None = None,
    ):
        self.model, self.model_type, self.model_path = load_model(
            model_path,
            FEATURE_COLUMNS,
            expected_type=model_type,
            fallback_path=fallback_model_path,
        )
        # Only ensembles can report per-base-model probabilities.
        self._expose_base_probabilities = hasattr(self.model, "base_probabilities")

        self.method = smoothing_method
        self.alpha = ema_alpha
        self._labels: deque[str] = deque(maxlen=smoothing_window)
        self._ema: float | None = None
        logger.info(
            "InferenceEngine loaded %s (type=%s, method=%s, window=%d, alpha=%.2f)",
            self.model_path.name, self.model_type, smoothing_method,
            smoothing_window, ema_alpha,
        )

    def reset_smoothing(self) -> None:
        """Clear EMA/majority-vote state. Call this at the start of every new
        recording session - otherwise the first several predictions of a new
        session are smoothed using whatever state a previous session (or the
        idle stream before any session started) left behind, which can show a
        stale label right after the user clicks Start."""
        self._ema = None
        self._labels.clear()

    @staticmethod
    def _apply_calibration(
        features: dict, calibration: CalibrationOffsets
    ) -> tuple[dict, bool]:
        """Return (adjusted_features, applied). Subtracts per-user baselines from
        the relevant feature groups so the model sees deviation-from-baseline.

        Reads via .get() rather than features[k]: FEATURE_COLUMNS always
        contains these keys in normal operation, but a missing key here would
        otherwise raise a bare KeyError with no context about which feature or
        which baseline caused it. A missing key is silently skipped for that
        one feature rather than dropping the whole prediction - the caller
        already validates the full feature set in _to_row, which is where a
        genuinely incomplete feature dict should be caught and reported."""
        adjusted = features.copy()
        applied = False
        if calibration.hr_baseline is not None:
            for k in ("hr_mean", "hr_min", "hr_max"):
                if k in features:
                    adjusted[k] = features[k] - calibration.hr_baseline
            applied = True
        if calibration.gsr_baseline is not None:
            for k in ("gsr_mean", "gsr_min", "gsr_max"):
                if k in features:
                    adjusted[k] = features[k] - calibration.gsr_baseline
            applied = True
        if calibration.temp_baseline is not None:
            for k in ("temp_mean",):
                if k in features:
                    adjusted[k] = features[k] - calibration.temp_baseline
            applied = True
        return adjusted, applied

    def _to_row(self, features: dict) -> np.ndarray:
        try:
            return np.array([[float(features[c]) for c in FEATURE_COLUMNS]])
        except KeyError as exc:
            raise ValueError(f"Feature dict missing required key: {exc}") from exc

    def _smooth(self, p_stress: float, label: str) -> tuple[str, float]:
        if self.method == "majority":
            self._labels.append(label)
            counts = {lab: self._labels.count(lab) for lab in set(self._labels)}
            top_count = max(counts.values())
            tied = [lab for lab, c in counts.items() if c == top_count]
            if len(tied) == 1:
                smoothed_label = tied[0]
            else:
                # A tie (e.g. a window of 6 split 3/3) previously broke on
                # Python's set-iteration order of `counts`, which is
                # unspecified and could flip the displayed label between
                # otherwise-identical calls. Break ties deterministically by
                # preferring whichever tied label occurs most recently in the
                # window - i.e. the most up-to-date read of a genuinely
                # ambiguous state, not an arbitrary hash-order artifact.
                smoothed_label = next(
                    lab for lab in reversed(self._labels) if lab in tied
                )
            smoothed_conf = counts[smoothed_label] / len(self._labels)
            return smoothed_label, smoothed_conf

        # Default: EMA on P(stress).
        if self._ema is None:
            self._ema = p_stress
        else:
            self._ema = self.alpha * p_stress + (1 - self.alpha) * self._ema
        smoothed_label = "stress" if self._ema > 0.5 else "baseline"
        smoothed_conf = max(self._ema, 1 - self._ema)
        return smoothed_label, smoothed_conf

    def predict(
        self,
        features: dict,
        timestamp_ms: int = 0,
        *,
        calibration: CalibrationOffsets | None = None,
    ) -> Prediction:
        """Predict + smooth for one feature vector.

        Args:
            features: 18-key feature dict from FeatureStreamer (any key order).
            timestamp_ms: stream time of the window (carried into the Prediction).
            calibration: optional per-user baselines. When present and non-null,
                the relevant features are shifted by the user's baseline before
                inference (deviation-from-baseline). Otherwise pass-through.
        """
        calibration_applied = False
        personalized_active = False
        is_personalized_bundle = hasattr(
            self.model, "predict_proba_personalized"
        )
        if is_personalized_bundle:
            if calibration is not None and calibration.is_complete():
                features = apply_relative_baseline(
                    features,
                    hr_baseline=float(calibration.hr_baseline),
                    gsr_baseline=float(calibration.gsr_baseline),
                    temp_baseline=float(calibration.temp_baseline),
                )
                calibration_applied = True
                personalized_active = True
        elif calibration is not None and calibration.is_active():
            # Preserve the older heuristic for legacy absolute-value artifacts.
            features, calibration_applied = self._apply_calibration(
                features, calibration
            )

        row = self._to_row(features)
        if personalized_active:
            proba = self.model.predict_proba_personalized(row)[0]
            active_model = self.model.personalized_model
            active_model_type = "personalized_extra_trees"
        elif is_personalized_bundle:
            proba = self.model.predict_proba(row)[0]
            active_model = self.model.fallback_model
            active_model_type = self.model.fallback_model_type
        else:
            proba = self.model.predict_proba(row)[0]
            active_model = self.model
            active_model_type = self.model_type
        classes = list(self.model.classes_)

        raw_proba = {
            _CLASS_NAMES[int(c)]: float(p) for c, p in zip(classes, proba)
        }
        best_idx = int(np.argmax(proba))
        label = _CLASS_NAMES[int(classes[best_idx])]
        confidence = float(proba[best_idx])
        p_stress = raw_proba.get("stress", 0.0)

        # Per-base-model diagnostics for the dashboard's model panel. Best
        # effort: a broken base model must not take the live stream down when
        # the ensemble itself already produced a usable probability.
        base_probabilities: dict[str, float] | None = None
        if hasattr(active_model, "base_probabilities"):
            try:
                base_probabilities = {
                    name: float(p[0])
                    for name, p in active_model.base_probabilities(row).items()
                }
            except Exception:  # noqa: BLE001
                logger.exception("Could not read per-base-model probabilities")

        smoothed_label, smoothed_conf = self._smooth(p_stress, label)

        return Prediction(
            timestamp_ms=timestamp_ms,
            label=label,
            confidence=confidence,
            smoothed_label=smoothed_label,
            smoothed_confidence=smoothed_conf,
            raw_proba=raw_proba,
            calibration_applied=calibration_applied,
            model_type=active_model_type,
            base_probabilities=base_probabilities,
        )
