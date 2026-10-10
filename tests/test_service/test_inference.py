import pandas as pd
import pytest

from stress_detection.config import get_config
from stress_detection.service.config import get_service_config
from stress_detection.service.inference.loader import resolve_model_path
from stress_detection.service.features.schema import FEATURE_COLUMNS
from stress_detection.service.inference.engine import InferenceEngine, Prediction


@pytest.fixture
def model_path():
    """Whatever the service is configured to serve, resolved the same way the
    app resolves it - glob expanded, falling back to the SVM baseline when the
    ensemble artifacts have not been generated yet."""
    cfg = get_service_config()
    path, _ = resolve_model_path(
        cfg.inference.model_path, cfg.inference.fallback_model_path
    )
    return path


@pytest.fixture
def feature_dict():
    """One real feature row from the WESAD feature parquet, as a 22-key dict."""
    cfg = get_service_config()
    parquet = get_config().paths.data_features / "features_wesad_v1.parquet"
    df = pd.read_parquet(parquet)
    row = df.iloc[0]
    return {c: float(row[c]) for c in FEATURE_COLUMNS}


def test_predict_returns_valid_prediction(model_path, feature_dict):
    engine = InferenceEngine(model_path, smoothing_method="ema")
    pred = engine.predict(feature_dict, timestamp_ms=12345)
    assert isinstance(pred, Prediction)
    assert pred.label in ("baseline", "stress")
    assert 0.0 <= pred.confidence <= 1.0
    assert pred.smoothed_label in ("baseline", "stress")
    assert 0.0 <= pred.smoothed_confidence <= 1.0
    assert set(pred.raw_proba.keys()) == {"baseline", "stress"}
    assert pred.raw_proba["baseline"] + pred.raw_proba["stress"] == pytest.approx(1.0, abs=1e-6)
    assert pred.timestamp_ms == 12345


def test_ema_converges_toward_running_average(model_path, feature_dict):
    engine = InferenceEngine(model_path, smoothing_method="ema", ema_alpha=0.3)
    # Drive the smoother directly with alternating high/low p(stress).
    last = None
    for i in range(20):
        p = 0.9 if i % 2 == 0 else 0.1
        last_label, last_conf = engine._smooth(p, "stress" if p > 0.5 else "baseline")
        last = engine._ema
    # Alternating 0.9/0.1 → EMA should settle near the 0.5 mean band.
    assert 0.35 < last < 0.65


def test_majority_smoothing(model_path):
    engine = InferenceEngine(model_path, smoothing_method="majority", smoothing_window=6)
    labels = ["stress"] * 4 + ["baseline"] * 2
    smoothed_label = None
    for lab in labels:
        p = 0.8 if lab == "stress" else 0.2
        smoothed_label, smoothed_conf = engine._smooth(p, lab)
    assert smoothed_label == "stress"
    assert smoothed_conf == pytest.approx(4 / 6)


def test_majority_smoothing_tie_prefers_the_most_recent_label(model_path):
    """Regression test: a 3/3 tie previously broke on Python's set-iteration
    order of the label counts, which is unspecified and could flip the
    displayed label between otherwise-identical runs. The tiebreak must now
    deterministically favour whichever tied label was seen most recently."""
    engine = InferenceEngine(model_path, smoothing_method="majority", smoothing_window=6)
    # 3 stress, then 3 baseline - tied 3/3, baseline is the most recent.
    for lab in ["stress", "stress", "stress", "baseline", "baseline", "baseline"]:
        p = 0.8 if lab == "stress" else 0.2
        smoothed_label, smoothed_conf = engine._smooth(p, lab)
    assert smoothed_label == "baseline"
    assert smoothed_conf == pytest.approx(0.5)

    engine2 = InferenceEngine(model_path, smoothing_method="majority", smoothing_window=6)
    # Same tie, opposite recency - stress is now the most recent.
    for lab in ["baseline", "baseline", "baseline", "stress", "stress", "stress"]:
        p = 0.8 if lab == "stress" else 0.2
        smoothed_label, smoothed_conf = engine2._smooth(p, lab)
    assert smoothed_label == "stress"
    assert smoothed_conf == pytest.approx(0.5)

    # Same inputs, run 20 times: the result must not vary run to run (it
    # would, intermittently, under the old set-iteration-order tiebreak).
    results = set()
    for _ in range(20):
        e = InferenceEngine(model_path, smoothing_method="majority", smoothing_window=6)
        for lab in ["stress", "stress", "stress", "baseline", "baseline", "baseline"]:
            p = 0.8 if lab == "stress" else 0.2
            smoothed_label, _ = e._smooth(p, lab)
        results.add(smoothed_label)
    assert results == {"baseline"}, f"tie-break was not deterministic: saw {results}"


def test_feature_order_invariance(model_path, feature_dict):
    """A reordered feature dict must produce the same prediction."""
    engine_a = InferenceEngine(model_path)
    pred_a = engine_a.predict(feature_dict)

    reordered = dict(reversed(list(feature_dict.items())))
    engine_b = InferenceEngine(model_path)
    pred_b = engine_b.predict(reordered)

    assert pred_a.label == pred_b.label
    assert pred_a.confidence == pytest.approx(pred_b.confidence)
    assert pred_a.raw_proba["stress"] == pytest.approx(pred_b.raw_proba["stress"])


def test_missing_feature_raises(model_path, feature_dict):
    engine = InferenceEngine(model_path)
    broken = dict(feature_dict)
    del broken["hr_mean"]
    with pytest.raises(ValueError):
        engine.predict(broken)
