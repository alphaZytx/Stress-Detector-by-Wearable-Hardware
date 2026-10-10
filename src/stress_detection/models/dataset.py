"""Loading the combined (WESAD + project) training set.

One loader, used by every training and evaluation script, so there is exactly
one definition of "the dataset the deployed model was trained on". No feature
extraction happens here - it reads the parquet files produced by the existing
``scripts/build_features.py`` and ``scripts/build_wesad_features.py``.

Column order is taken from ``service.features.schema.FEATURE_COLUMNS``, the
canonical 22-column contract shared by the offline pipeline and the live
streamer, rather than from whatever order the parquet happens to have. The set
of columns is verified against it, so a parquet that drifted (renamed, dropped
or added a feature) fails loudly here instead of training a model whose columns
silently disagree with the service's.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from stress_detection.config import get_config
from stress_detection.service.features.schema import FEATURE_COLUMNS, META_COLUMNS

from .common import LABEL_MAP

logger = logging.getLogger(__name__)

WESAD_FEATURES = "features_wesad_v1.parquet"
PROJECT_FEATURES = "features_v1.parquet"

# The project's own recording is a single subject; WESAD supplies the other 15.
PROJECT_SUBJECT_ID = "PROJECT"


@dataclass
class Dataset:
    X: np.ndarray
    y: np.ndarray
    groups: np.ndarray
    feature_names: list[str]
    description: str

    @property
    def n_subjects(self) -> int:
        return int(len(np.unique(self.groups)))

    @property
    def n_windows(self) -> int:
        return int(len(self.y))

    def summary(self) -> dict:
        return {
            "description": self.description,
            "n_subjects": self.n_subjects,
            "n_windows": self.n_windows,
            "n_features": len(self.feature_names),
            "feature_names": list(self.feature_names),
            "class_counts": {
                "baseline": int((self.y == 0).sum()),
                "stress": int((self.y == 1).sum()),
            },
            "windows_per_subject": {
                str(s): int((self.groups == s).sum())
                for s in sorted(np.unique(self.groups))
            },
        }


def feature_data_paths() -> tuple[Path, Path]:
    features_dir = get_config().paths.data_features
    return features_dir / WESAD_FEATURES, features_dir / PROJECT_FEATURES


def missing_feature_data() -> list[Path]:
    """Which of the required parquet files are absent (§17 step 1)."""
    return [p for p in feature_data_paths() if not p.exists()]


def load_combined_dataset() -> Dataset:
    """Load the WESAD + project window table the deployed SVM was trained on.

    Mirrors ``scripts/train_combined.py``: concatenate the two feature tables,
    tag the project rows with a single subject id, keep only baseline/stress
    windows, and map labels with ``{"baseline": 0, "stress": 1}``.
    """
    wesad_path, project_path = feature_data_paths()
    missing = missing_feature_data()
    if missing:
        raise FileNotFoundError(
            "Missing feature data: "
            + ", ".join(str(p) for p in missing)
            + ". Build it first: python3 scripts/build_interim.py && "
            "python3 scripts/build_features.py (project) and "
            "python3 scripts/download_wesad.py && "
            "python3 scripts/build_wesad_interim.py && "
            "python3 scripts/build_wesad_features.py (WESAD)."
        )

    wesad_df = pd.read_parquet(wesad_path)
    project_df = pd.read_parquet(project_path).copy()
    project_df["subject_id"] = PROJECT_SUBJECT_ID

    combined = pd.concat([wesad_df, project_df], ignore_index=True)
    combined = combined[combined["label"].isin(LABEL_MAP)].copy()
    combined["y"] = combined["label"].map(LABEL_MAP)

    available = set(combined.columns) - META_COLUMNS - {"y"}
    expected = set(FEATURE_COLUMNS)
    if available != expected:
        raise ValueError(
            "Feature parquet does not match the canonical 22-column schema. "
            f"Missing: {sorted(expected - available)}; "
            f"unexpected: {sorted(available - expected)}."
        )

    # Index by the canonical order, never by the parquet's own column order.
    X = combined[FEATURE_COLUMNS].to_numpy(dtype=float)
    y = combined["y"].to_numpy(dtype=int)
    groups = combined["subject_id"].to_numpy().astype(str)

    dataset = Dataset(
        X=X,
        y=y,
        groups=groups,
        feature_names=list(FEATURE_COLUMNS),
        description=(
            f"WESAD ({len(np.unique(wesad_df['subject_id']))} subjects) + project "
            f"(1 subject, '{PROJECT_SUBJECT_ID}'); 30 s windows at 5 s stride; "
            f"{WESAD_FEATURES} + {PROJECT_FEATURES}"
        ),
    )
    logger.info(
        "Loaded %d windows, %d subjects, %d features (baseline=%d, stress=%d)",
        dataset.n_windows, dataset.n_subjects, len(dataset.feature_names),
        (y == 0).sum(), (y == 1).sum(),
    )
    return dataset
