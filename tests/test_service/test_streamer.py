import pandas as pd

from stress_detection.service.config import get_service_config
from stress_detection.service.features.schema import FEATURE_COLUMNS, META_COLUMNS
from stress_detection.service.features.streamer import FeatureStreamer
from stress_detection.service.sources.base import SensorSample


def _sample(i, bpm=75.0, gsr=100.0, temp=36.5):
    """One synthetic 1-Hz sample at second i (timestamp_ms = i*1000)."""
    return SensorSample(
        timestamp_ms=i * 1000,
        bpm=bpm,
        avg_bpm=bpm,
        temp_c=temp,
        gsr=gsr + (i % 5),     # mild variation so std/peaks aren't degenerate
        source_label="baseline",
    )


def test_emits_roughly_seven_for_sixty_samples():
    cfg = get_service_config()
    s = FeatureStreamer(cfg.window_s, cfg.stride_s, cfg.sampling_hz)
    emits = [s.push(_sample(i)) for i in range(60)]
    non_null = [e for e in emits if e is not None]
    assert len(non_null) == 7


def test_first_emit_at_buffer_full():
    cfg = get_service_config()
    s = FeatureStreamer(cfg.window_s, cfg.stride_s, cfg.sampling_hz)
    first_emit_index = None
    for i in range(60):
        out = s.push(_sample(i))
        if out is not None and first_emit_index is None:
            first_emit_index = i
            break
    # window_s = 30 → 30 samples needed → first emit at index 29 (the 30th sample).
    assert first_emit_index == cfg.window_s - 1


def test_subsequent_emits_every_stride():
    cfg = get_service_config()
    s = FeatureStreamer(cfg.window_s, cfg.stride_s, cfg.sampling_hz)
    emit_indices = [i for i in range(60) if s.push(_sample(i)) is not None]
    # Differences between consecutive emit indices == stride_s (5).
    diffs = [b - a for a, b in zip(emit_indices, emit_indices[1:])]
    assert all(d == cfg.stride_s for d in diffs)


def test_all_invalid_bpm_no_emit_no_crash():
    cfg = get_service_config()
    s = FeatureStreamer(cfg.window_s, cfg.stride_s, cfg.sampling_hz)
    # bpm=None for every sample → window fails the bpm_valid gate.
    outs = [s.push(_sample(i, bpm=None)) for i in range(60)]
    assert all(o is None for o in outs)


def test_emitted_dict_has_18_keys_in_canonical_order():
    cfg = get_service_config()
    s = FeatureStreamer(cfg.window_s, cfg.stride_s, cfg.sampling_hz)
    out = None
    for i in range(40):
        out = s.push(_sample(i)) or out
    assert out is not None
    assert list(out.keys()) == FEATURE_COLUMNS
    assert len(out) == 18


def test_feature_schema_matches_parquet():
    """FEATURE_COLUMNS must match the on-disk Phase 1 feature schema exactly."""
    cfg = get_service_config()
    # model_path = <root>/data/models/<model>.joblib → parents[1] = <root>/data
    parquet = (
        cfg.inference.model_path.parents[1] / "features" / "features_v1.parquet"
    )
    df = pd.read_parquet(parquet)
    parquet_features = [c for c in df.columns if c not in META_COLUMNS]
    assert parquet_features == FEATURE_COLUMNS


def test_buffer_seconds_caps_at_window():
    cfg = get_service_config()
    s = FeatureStreamer(cfg.window_s, cfg.stride_s, cfg.sampling_hz)
    assert s.buffer_seconds == 0
    for i in range(10):
        s.push(_sample(i))
    assert s.buffer_seconds == 10
    for i in range(10, 60):
        s.push(_sample(i))
    assert s.buffer_seconds == cfg.window_s
