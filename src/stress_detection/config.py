"""Project configuration loaded from config/default.yaml.

Paths are resolved relative to the repo root, not CWD.
Call get_config() to get a singleton Config instance.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).parent.parent.parent


@dataclass
class PathsConfig:
    data_raw: Path
    data_interim: Path
    data_features: Path
    data_wesad_raw: Path
    data_models: Path
    reports: Path


@dataclass
class SamplingConfig:
    sensors_hz: int


@dataclass
class WindowingConfig:
    window_s: int
    stride_s: int
    min_valid_bpm_fraction: float


@dataclass
class Config:
    paths: PathsConfig
    sampling: SamplingConfig
    windowing: WindowingConfig
    random_seed: int


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        config_path = _REPO_ROOT / "config" / "default.yaml"
        with open(config_path) as f:
            raw = yaml.safe_load(f)
        _config = Config(
            paths=PathsConfig(
                data_raw=_REPO_ROOT / raw["paths"]["data_raw"],
                data_interim=_REPO_ROOT / raw["paths"]["data_interim"],
                data_features=_REPO_ROOT / raw["paths"]["data_features"],
                data_wesad_raw=_REPO_ROOT / raw["paths"]["data_wesad_raw"],
                data_models=_REPO_ROOT / raw["paths"]["data_models"],
                reports=_REPO_ROOT / raw["paths"]["reports"],
            ),
            sampling=SamplingConfig(**raw["sampling"]),
            windowing=WindowingConfig(**raw["windowing"]),
            random_seed=raw["random_seed"],
        )
    return _config
