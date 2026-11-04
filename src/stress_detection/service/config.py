"""Service configuration loaded from config/service.yaml.

Mirrors the style of stress_detection.config (dataclasses, repo-root-relative
paths). Window/stride/sampling are NOT duplicated here - they are pulled from
the Phase 1 config (config/default.yaml) so the streaming feature extractor
uses the exact same windowing the model was trained on.

Public entry point: get_service_config() -> ServiceConfig (singleton).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from stress_detection.config import get_config

# config.py → service → stress_detection → src → repo root
_REPO_ROOT = Path(__file__).parents[3]


@dataclass
class ServerConfig:
    host: str
    port: int
    log_level: str


@dataclass
class CsvReplayConfig:
    files: list[Path]
    loop: bool
    speed: float


@dataclass
class SerialConfig:
    port: str
    baudrate: int


@dataclass
class TcpConfig:
    host: str
    port: int


@dataclass
class SyntheticConfig:
    speed: float
    seed: int
    baseline_s: int
    stress_s: int
    recovery_s: int


@dataclass
class InputConfig:
    source: str
    synthetic: SyntheticConfig
    csv_replay: CsvReplayConfig
    serial: SerialConfig
    tcp: TcpConfig


@dataclass
class SmoothingConfig:
    method: str
    window: int
    ema_alpha: float


@dataclass
class InferenceConfig:
    model_path: Path
    smoothing: SmoothingConfig
    # Which classifier to serve: svm | random_forest | xgboost | mlp |
    # soft_voting | stacking | personalized_extra_trees.
    # Selecting a model is a config change, never a code change.
    model_type: str = "svm"
    # Used when model_path does not exist yet - e.g. an ensemble target set
    # before scripts/train_all_models.py has produced the artifact. Keeps the
    # SVM baseline serving instead of failing startup.
    fallback_model_path: Path | None = None


@dataclass
class SessionConfig:
    db_path: Path
    export_dir: Path


@dataclass
class ServiceConfig:
    service: ServerConfig
    input: InputConfig
    inference: InferenceConfig
    session: SessionConfig
    # Derived from the Phase 1 windowing config - single source of truth so the
    # live feature extractor matches the offline training pipeline exactly.
    window_s: int
    stride_s: int
    sampling_hz: int
    min_valid_bpm_fraction: float

    def to_dict(self) -> dict:
        """JSON-serialisable view (Paths → str). Used by the /config endpoint."""

        def _convert(value):
            if isinstance(value, Path):
                return str(value)
            if isinstance(value, dict):
                return {k: _convert(v) for k, v in value.items()}
            if isinstance(value, list):
                return [_convert(v) for v in value]
            return value

        return _convert(asdict(self))


_config: ServiceConfig | None = None


def _resolve(path_str: str) -> Path:
    """Resolve a config path string relative to the repo root."""
    p = Path(path_str)
    return p if p.is_absolute() else _REPO_ROOT / p


def get_service_config() -> ServiceConfig:
    """Load config/service.yaml into a typed ServiceConfig singleton."""
    global _config
    if _config is None:
        config_path = _REPO_ROOT / "config" / "service.yaml"
        with open(config_path) as f:
            raw = yaml.safe_load(f)

        win = get_config().windowing
        sampling = get_config().sampling

        _config = ServiceConfig(
            service=ServerConfig(**raw["service"]),
            input=InputConfig(
                source=raw["input"]["source"],
                synthetic=SyntheticConfig(**raw["input"]["synthetic"]),
                csv_replay=CsvReplayConfig(
                    files=[_resolve(f) for f in raw["input"]["csv_replay"]["files"]],
                    loop=bool(raw["input"]["csv_replay"]["loop"]),
                    speed=float(raw["input"]["csv_replay"]["speed"]),
                ),
                serial=SerialConfig(**raw["input"]["serial"]),
                tcp=TcpConfig(**raw["input"]["tcp"]),
            ),
            inference=InferenceConfig(
                model_path=_resolve(raw["inference"]["model_path"]),
                smoothing=SmoothingConfig(**raw["inference"]["smoothing"]),
                model_type=raw["inference"].get("model_type", "svm"),
                fallback_model_path=(
                    _resolve(raw["inference"]["fallback_model_path"])
                    if raw["inference"].get("fallback_model_path")
                    else None
                ),
            ),
            session=SessionConfig(
                db_path=_resolve(raw["session"]["db_path"]),
                export_dir=_resolve(raw["session"]["export_dir"]),
            ),
            window_s=win.window_s,
            stride_s=win.stride_s,
            sampling_hz=sampling.sensors_hz,
            min_valid_bpm_fraction=win.min_valid_bpm_fraction,
        )
    return _config


def reset_service_config() -> None:
    """Clear the cached singleton. Intended for tests that mutate config."""
    global _config
    _config = None
