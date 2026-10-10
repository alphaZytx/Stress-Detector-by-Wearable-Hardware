"""Serving the ensembles (§23, runtime tests) and the schema guard (§13).

Artifacts are built here from synthetic data rather than read from data/models,
so these tests pass on a fresh clone where scripts/train_all_models.py has not
been run.
"""

from __future__ import annotations

import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient

from stress_detection.models.common import BASE_MODEL_NAMES, build_model
from stress_detection.models.ensemble import (
    EnsembleMetadata,
    SoftVotingEnsemble,
    StackingEnsemble,
)
from stress_detection.service.app import create_app
from stress_detection.service.features.schema import FEATURE_COLUMNS
from stress_detection.service.inference.engine import CalibrationOffsets, InferenceEngine, Prediction
from stress_detection.service.inference.loader import (
    SUPPORTED_MODEL_TYPES,
    detect_model_type,
    load_model,
    normalise_model_type,
    resolve_model_path,
    validate_model_schema,
)

N_FEATURES = len(FEATURE_COLUMNS)


def _training_data(n_subjects: int = 4, n_per_subject: int = 30, seed: int = 0):
    rng = np.random.default_rng(seed)
    X, y, groups = [], [], []
    for subject in range(n_subjects):
        half = n_per_subject // 2
        labels = np.array([0] * half + [1] * (n_per_subject - half))
        features = rng.normal(0.0, 1.0, size=(n_per_subject, N_FEATURES))
        features[:, 1:6] += 1.8 * labels[:, None]
        X.append(features)
        y.append(labels)
        groups.append(np.full(n_per_subject, f"S{subject}", dtype=object))
    return np.vstack(X), np.concatenate(y), np.concatenate(groups)


def _metadata(model_type: str) -> EnsembleMetadata:
    return EnsembleMetadata(
        model_type=model_type,
        model_version="test",
        feature_names=list(FEATURE_COLUMNS),
        dataset="synthetic test fixture",
        n_subjects=4,
        n_windows=120,
    )


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory):
    """A stacking and a soft-voting artifact on disk, plus the fixture data."""
    directory = tmp_path_factory.mktemp("models")
    X, y, groups = _training_data()
    base = {name: build_model(name) for name in BASE_MODEL_NAMES}

    stack = StackingEnsemble(base, n_oof_splits=2, feature_names=list(FEATURE_COLUMNS))
    stack.fit(X, y, groups)
    stack.metadata = _metadata("stacking")
    stack_path = directory / "ensemble_stack_v9.joblib"
    joblib.dump(stack, stack_path)

    soft = SoftVotingEnsemble(
        {name: build_model(name) for name in BASE_MODEL_NAMES},
        feature_names=list(FEATURE_COLUMNS),
    )
    soft.fit(X, y)
    soft.metadata = _metadata("soft_voting")
    soft_path = directory / "ensemble_soft_v9.joblib"
    joblib.dump(soft, soft_path)

    return {"dir": directory, "stack": stack_path, "soft": soft_path, "X": X}


@pytest.fixture
def feature_dict(artifacts):
    return {name: float(value) for name, value in zip(FEATURE_COLUMNS, artifacts["X"][0])}


@pytest.fixture
def restore_inference_config():
    """Restore the shared config singleton so other tests are unaffected."""
    from stress_detection.service.config import get_service_config

    cfg = get_service_config()
    saved = (cfg.inference.model_path, cfg.inference.model_type,
             cfg.inference.fallback_model_path)
    yield cfg
    (cfg.inference.model_path, cfg.inference.model_type,
     cfg.inference.fallback_model_path) = saved


# --------------------------------------------------------------------------
# Schema guard (§13)
# --------------------------------------------------------------------------


class TestSchemaGuard:
    def test_accepts_a_well_formed_ensemble(self, artifacts):
        model = joblib.load(artifacts["stack"])
        validate_model_schema(model, FEATURE_COLUMNS)

    def test_rejects_a_wrong_feature_count(self):
        X = np.random.default_rng(0).normal(size=(40, 5))
        y = np.tile([0, 1], 20)
        model = build_model("random_forest").fit(X, y)
        with pytest.raises(ValueError, match="expects 5 features"):
            validate_model_schema(model, FEATURE_COLUMNS)

    def test_rejects_a_base_model_with_the_wrong_feature_count(self, artifacts):
        """Every base model is checked, not just the ensemble wrapper."""
        model = joblib.load(artifacts["stack"])
        X = np.random.default_rng(1).normal(size=(40, 7))
        y = np.tile([0, 1], 20)
        model.base_models["mlp"] = build_model("mlp").fit(X, y)
        with pytest.raises(ValueError, match=r"\.mlp expects 7 features"):
            validate_model_schema(model, FEATURE_COLUMNS)

    def test_rejects_a_missing_base_model(self, artifacts):
        model = joblib.load(artifacts["stack"])
        model.base_models["xgboost"] = None
        with pytest.raises(ValueError, match="missing its 'xgboost' base model"):
            validate_model_schema(model, FEATURE_COLUMNS)

    def test_rejects_an_empty_ensemble(self, artifacts):
        model = joblib.load(artifacts["stack"])
        model.base_models = {}
        with pytest.raises(ValueError, match="no base models"):
            validate_model_schema(model, FEATURE_COLUMNS)

    def test_rejects_mismatched_feature_names(self, artifacts):
        model = joblib.load(artifacts["stack"])
        model.feature_names_in_ = list(reversed(FEATURE_COLUMNS))
        with pytest.raises(ValueError, match="does not match the canonical feature"):
            validate_model_schema(model, FEATURE_COLUMNS)

    def test_rejects_metadata_declaring_a_different_schema(self, artifacts):
        model = joblib.load(artifacts["stack"])
        model.metadata.feature_names = FEATURE_COLUMNS[:10]
        with pytest.raises(ValueError, match="different feature schema"):
            validate_model_schema(model, FEATURE_COLUMNS)

    def test_rejects_a_model_without_predict_proba(self):
        class NoProba:
            n_features_in_ = N_FEATURES

        with pytest.raises(ValueError, match="no predict_proba"):
            validate_model_schema(NoProba(), FEATURE_COLUMNS)


# --------------------------------------------------------------------------
# Loader (§14)
# --------------------------------------------------------------------------


class TestLoader:
    def test_supports_every_required_model_type(self):
        for wanted in ("svm", "random_forest", "xgboost", "mlp", "soft_voting", "stacking"):
            assert wanted in SUPPORTED_MODEL_TYPES

    def test_config_aliases_normalise(self):
        assert normalise_model_type("ensemble_stack") == "stacking"
        assert normalise_model_type("ensemble_soft") == "soft_voting"
        assert normalise_model_type("SVM") == "svm"

    def test_unknown_model_type_is_rejected(self):
        with pytest.raises(ValueError, match="Unsupported inference.model_type"):
            normalise_model_type("transformer")

    def test_detects_ensemble_types(self, artifacts):
        assert detect_model_type(joblib.load(artifacts["stack"])) == "stacking"
        assert detect_model_type(joblib.load(artifacts["soft"])) == "soft_voting"

    def test_detects_single_model_types(self):
        X = np.random.default_rng(2).normal(size=(40, N_FEATURES))
        y = np.tile([0, 1], 20)
        assert detect_model_type(build_model("svm").fit(X, y)) == "svm"
        assert detect_model_type(build_model("random_forest").fit(X, y)) == "random_forest"
        assert detect_model_type(build_model("mlp").fit(X, y)) == "mlp"

    def test_glob_resolves_to_the_highest_version(self, artifacts, tmp_path):
        for version in ("v1", "v2", "v10"):
            joblib.dump({"v": version}, tmp_path / f"ensemble_stack_{version}.joblib")
        path, used_fallback = resolve_model_path(tmp_path / "ensemble_stack_v*.joblib")
        assert path.name == "ensemble_stack_v10.joblib"
        assert used_fallback is False

    def test_missing_artifact_falls_back(self, artifacts, tmp_path):
        path, used_fallback = resolve_model_path(
            tmp_path / "not_here.joblib", artifacts["stack"]
        )
        assert used_fallback is True
        assert path == artifacts["stack"]

    def test_missing_artifact_without_fallback_fails_cleanly(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="No model artifact"):
            resolve_model_path(tmp_path / "nothing.joblib")

    def test_declared_type_must_match_the_artifact(self, artifacts):
        with pytest.raises(ValueError, match="Refusing to load a mismatched artifact"):
            load_model(artifacts["stack"], FEATURE_COLUMNS, expected_type="soft_voting")

    def test_matching_type_loads(self, artifacts):
        model, model_type, path = load_model(
            artifacts["stack"], FEATURE_COLUMNS, expected_type="ensemble_stack"
        )
        assert model_type == "stacking"
        assert path == artifacts["stack"]


# --------------------------------------------------------------------------
# Engine with an ensemble
# --------------------------------------------------------------------------


class TestEngineWithEnsemble:
    @pytest.mark.parametrize("kind,expected", [("stack", "stacking"), ("soft", "soft_voting")])
    def test_predicts_and_reports_its_type(self, artifacts, feature_dict, kind, expected):
        engine = InferenceEngine(artifacts[kind], model_type=expected)
        pred = engine.predict(feature_dict, timestamp_ms=999)
        assert isinstance(pred, Prediction)
        assert pred.model_type == expected
        assert pred.label in ("baseline", "stress")
        assert 0.0 <= pred.confidence <= 1.0
        assert pred.raw_proba["baseline"] + pred.raw_proba["stress"] == pytest.approx(1.0)
        assert pred.timestamp_ms == 999

    def test_exposes_per_base_model_probabilities(self, artifacts, feature_dict):
        engine = InferenceEngine(artifacts["stack"], model_type="stacking")
        pred = engine.predict(feature_dict)
        assert set(pred.base_probabilities) == set(BASE_MODEL_NAMES)
        for value in pred.base_probabilities.values():
            assert 0.0 <= value <= 1.0

    def test_ema_smoothing_still_works(self, artifacts, feature_dict):
        """Smoothing lives in the engine and is untouched by the model swap."""
        engine = InferenceEngine(artifacts["stack"], model_type="stacking",
                                 smoothing_method="ema", ema_alpha=0.3)
        last = None
        for i in range(20):
            engine._smooth(0.9 if i % 2 == 0 else 0.1, "stress" if i % 2 == 0 else "baseline")
            last = engine._ema
        assert 0.35 < last < 0.65

    def test_majority_smoothing_still_works(self, artifacts):
        engine = InferenceEngine(artifacts["stack"], model_type="stacking",
                                 smoothing_method="majority", smoothing_window=6)
        label = None
        for lab in ["stress"] * 4 + ["baseline"] * 2:
            label, confidence = engine._smooth(0.8 if lab == "stress" else 0.2, lab)
        assert label == "stress"
        assert confidence == pytest.approx(4 / 6)

    def test_calibration_still_applies(self, artifacts, feature_dict):
        engine = InferenceEngine(artifacts["stack"], model_type="stacking")
        plain = engine.predict(feature_dict)
        assert plain.calibration_applied is False

        engine = InferenceEngine(artifacts["stack"], model_type="stacking")
        calibrated = engine.predict(
            feature_dict,
            calibration=CalibrationOffsets(hr_baseline=5.0, gsr_baseline=2.0, temp_baseline=0.5),
        )
        assert calibrated.calibration_applied is True

    def test_calibration_is_applied_once(self, artifacts, feature_dict):
        """Guards against double-shifting the features (§22)."""
        engine = InferenceEngine(artifacts["stack"], model_type="stacking")
        calibration = CalibrationOffsets(hr_baseline=5.0)
        shifted, applied = engine._apply_calibration(feature_dict, calibration)
        assert applied is True
        assert shifted["hr_mean"] == pytest.approx(feature_dict["hr_mean"] - 5.0)
        # The source dict must not have been mutated in place.
        assert feature_dict["hr_mean"] != shifted["hr_mean"]

    def test_feature_order_does_not_matter(self, artifacts, feature_dict):
        forward = InferenceEngine(artifacts["stack"], model_type="stacking").predict(feature_dict)
        reversed_dict = dict(reversed(list(feature_dict.items())))
        backward = InferenceEngine(artifacts["stack"], model_type="stacking").predict(reversed_dict)
        assert forward.raw_proba["stress"] == pytest.approx(backward.raw_proba["stress"])

    def test_missing_feature_raises(self, artifacts, feature_dict):
        engine = InferenceEngine(artifacts["stack"], model_type="stacking")
        broken = dict(feature_dict)
        del broken["gsr_mean"]
        with pytest.raises(ValueError, match="missing required key"):
            engine.predict(broken)


# --------------------------------------------------------------------------
# Wire contract (§21) and app startup
# --------------------------------------------------------------------------


class TestWireContract:
    def test_prediction_keeps_every_existing_field(self, artifacts, feature_dict):
        """The dashboard's contract - label, smoothed_confidence, calibration_applied."""
        engine = InferenceEngine(artifacts["stack"], model_type="stacking")
        payload = engine.predict(feature_dict).model_dump()
        for key in (
            "timestamp_ms", "label", "confidence", "smoothed_label",
            "smoothed_confidence", "raw_proba", "calibration_applied",
        ):
            assert key in payload
        assert payload["model_type"] == "stacking"
        assert set(payload["base_probabilities"]) == set(BASE_MODEL_NAMES)

    def test_single_model_leaves_base_probabilities_null(self, tmp_path, feature_dict):
        X, y, _ = _training_data()
        path = tmp_path / "svm_combined_v9.joblib"
        joblib.dump(build_model("svm").fit(X, y), path)
        payload = InferenceEngine(path, model_type="svm").predict(feature_dict).model_dump()
        assert payload["model_type"] == "svm"
        assert payload["base_probabilities"] is None


class TestServiceStartup:
    def test_starts_with_the_svm_configuration(self, service_cfg, restore_inference_config, tmp_path):
        X, y, _ = _training_data()
        path = tmp_path / "svm_combined_v9.joblib"
        joblib.dump(build_model("svm").fit(X, y), path)
        service_cfg.inference.model_path = path
        service_cfg.inference.model_type = "svm"
        service_cfg.inference.fallback_model_path = None

        with TestClient(create_app(service_cfg)) as client:
            assert client.get("/health").json() == {"status": "ok"}
            assert client.app.state.runtime.engine.model_type == "svm"

    def test_starts_with_the_ensemble_configuration(self, service_cfg, restore_inference_config, artifacts):
        service_cfg.inference.model_path = artifacts["dir"] / "ensemble_stack_v*.joblib"
        service_cfg.inference.model_type = "ensemble_stack"
        service_cfg.inference.fallback_model_path = None

        with TestClient(create_app(service_cfg)) as client:
            assert client.get("/health").json() == {"status": "ok"}
            assert client.app.state.runtime.engine.model_type == "stacking"

    def test_falls_back_to_the_svm_when_the_ensemble_is_absent(
        self, service_cfg, restore_inference_config, tmp_path
    ):
        """§14: the app keeps working before the ensemble artifacts exist."""
        X, y, _ = _training_data()
        fallback = tmp_path / "svm_combined_v9.joblib"
        joblib.dump(build_model("svm").fit(X, y), fallback)
        service_cfg.inference.model_path = tmp_path / "ensemble_stack_v*.joblib"
        service_cfg.inference.model_type = "stacking"
        service_cfg.inference.fallback_model_path = fallback

        with TestClient(create_app(service_cfg)) as client:
            assert client.get("/health").json() == {"status": "ok"}
            assert client.app.state.runtime.engine.model_type == "svm"
