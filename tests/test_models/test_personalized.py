from __future__ import annotations

import joblib
import numpy as np
import pytest
from sklearn.dummy import DummyClassifier

from stress_detection.features.calibration import apply_relative_baseline
from stress_detection.models.personalized import PersonalizedStressModel
from stress_detection.service.features.schema import FEATURE_COLUMNS
from stress_detection.service.inference.engine import CalibrationOffsets, InferenceEngine
from stress_detection.service.inference.loader import detect_model_type, validate_model_schema


def test_relative_baseline_transform_matches_training_contract():
    features = {name: 2.0 for name in FEATURE_COLUMNS}
    adjusted = apply_relative_baseline(
        features, hr_baseline=4.0, gsr_baseline=2.0, temp_baseline=1.5
    )
    assert adjusted["hr_mean"] == pytest.approx(0.5)
    assert adjusted["hr_std"] == pytest.approx(0.5)
    assert adjusted["gsr_auc"] == pytest.approx(1.0)
    assert adjusted["temp_mean"] == pytest.approx(0.5)
    assert adjusted["temp_std"] == pytest.approx(2.0)
    assert adjusted["gsr_peaks"] == pytest.approx(2.0)
    assert features["hr_mean"] == 2.0  # source is not mutated


def _bundle(tmp_path):
    X = np.vstack([np.zeros(len(FEATURE_COLUMNS)), np.ones(len(FEATURE_COLUMNS))])
    y = np.array([0, 1])
    personalized = DummyClassifier(strategy="constant", constant=1).fit(X, y)
    fallback = DummyClassifier(strategy="constant", constant=0).fit(X, y)
    model = PersonalizedStressModel(
        personalized,
        fallback,
        feature_names=list(FEATURE_COLUMNS),
        fallback_model_type="soft_voting",
    )
    path = tmp_path / "personalized_extra_trees_wesad_v3.joblib"
    joblib.dump(model, path)
    return model, path


def test_personalized_bundle_schema_and_type(tmp_path):
    model, _ = _bundle(tmp_path)
    validate_model_schema(model, FEATURE_COLUMNS)
    assert detect_model_type(model) == "personalized_extra_trees"


def test_engine_uses_personalized_only_with_complete_calibration(tmp_path):
    _, path = _bundle(tmp_path)
    features = {name: 2.0 for name in FEATURE_COLUMNS}
    engine = InferenceEngine(path, model_type="personalized_extra_trees")

    fallback = engine.predict(features)
    assert fallback.label == "baseline"
    assert fallback.model_type == "soft_voting"
    assert fallback.calibration_applied is False

    incomplete = engine.predict(
        features, calibration=CalibrationOffsets(hr_baseline=80, gsr_baseline=100)
    )
    assert incomplete.label == "baseline"
    assert incomplete.calibration_applied is False

    personalized = engine.predict(
        features,
        calibration=CalibrationOffsets(
            hr_baseline=80, gsr_baseline=100, temp_baseline=30
        ),
    )
    assert personalized.label == "stress"
    assert personalized.model_type == "personalized_extra_trees"
    assert personalized.calibration_applied is True
