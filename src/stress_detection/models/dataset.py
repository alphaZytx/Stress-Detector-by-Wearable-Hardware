"""Loading the combined (WESAD + project) training set.

One loader, used by every training and evaluation script, so there is exactly
one definition of "the dataset the deployed model was trained on". No feature
extraction happens here - it reads the parquet files produced by the existing
``scripts/build_features.py`` and ``scripts/build_wesad_features.py``.

Column order is taken from ``service.features.schema.FEATURE_COLUMNS``, the
canonical 18-column contract shared by the offline pipeline and the live
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
from stress_detection.features.calibration import (
    GSR_RELATIVE_FEATURES,
    HR_RELATIVE_FEATURES,
)
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


def missing_wesad_feature_data() -> list[Path]:
    """Return the missing inputs for WESAD-only hardware-model training."""
    wesad_path, _ = feature_data_paths()
    return [] if wesad_path.exists() else [wesad_path]


def _validate_and_build_dataset(
    frame: pd.DataFrame,
    *,
    description: str,
) -> Dataset:
    """Validate one feature table against the live 18-feature contract."""
    frame = frame[frame["label"].isin(LABEL_MAP)].copy()
    frame["y"] = frame["label"].map(LABEL_MAP)

    available = set(frame.columns) - META_COLUMNS - {"y"}
    expected = set(FEATURE_COLUMNS)
    if available != expected:
        raise ValueError(
            "Feature parquet does not match the canonical 18-column schema. "
            f"Missing: {sorted(expected - available)}; "
            f"unexpected: {sorted(available - expected)}."
        )

    dataset = Dataset(
        X=frame[FEATURE_COLUMNS].to_numpy(dtype=float),
        y=frame["y"].to_numpy(dtype=int),
        groups=frame["subject_id"].to_numpy().astype(str),
        feature_names=list(FEATURE_COLUMNS),
        description=description,
    )
    logger.info(
        "Loaded %d windows, %d subjects, %d features (baseline=%d, stress=%d)",
        dataset.n_windows,
        dataset.n_subjects,
        len(dataset.feature_names),
        (dataset.y == 0).sum(),
        (dataset.y == 1).sum(),
    )
    return dataset


def load_wesad_dataset() -> Dataset:
    """Load only WESAD subjects for the hardware-compatible model family.

    This intentionally excludes the small legacy project CSV recording. WESAD
    supplies real BVP-derived heart rate, EDA/GSR and wrist temperature; SpO2,
    ambient temperature and IR remain live display fields, not model inputs.
    """
    wesad_path, _ = feature_data_paths()
    if not wesad_path.exists():
        raise FileNotFoundError(
            f"Missing feature data: {wesad_path}. Build it with "
            "python3 scripts/build_wesad_interim.py && "
            "python3 scripts/build_wesad_features.py."
        )
    frame = pd.read_parquet(wesad_path)
    subject_count = frame["subject_id"].nunique()
    return _validate_and_build_dataset(
        frame,
        description=(
            f"WESAD-only hardware-compatible dataset ({subject_count} subjects); "
            "30 s windows at 5 s stride; BVP/heart rate, EDA/GSR and wrist "
            f"temperature; {WESAD_FEATURES}"
        ),
    )


def load_personalized_wesad_dataset(calibration_seconds: int = 120) -> Dataset:
    """Load WESAD in the representation used after live user calibration.

    For every subject, the first ``calibration_seconds`` samples of the known
    resting block supply HR, GSR and temperature baselines. Feature windows
    covered by that setup period are excluded; the remaining windows are
    converted with the same relative transform used by live inference.

    Access to the held-out person's resting block is intentional and matches
    deployment: the dashboard asks every user to complete a labelled resting
    calibration before the personalized model is enabled.
    """
    if calibration_seconds < 30:
        raise ValueError("calibration_seconds must be at least one 30-second window.")

    cfg = get_config()
    wesad_path, _ = feature_data_paths()
    interim_path = cfg.paths.data_interim / "wesad_sensors_clean.parquet"
    missing = [path for path in (wesad_path, interim_path) if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing personalized-training input(s): "
            + ", ".join(str(path) for path in missing)
        )

    frame = pd.read_parquet(wesad_path).copy()
    raw = pd.read_parquet(interim_path).copy()
    drop_indices: list[int] = []

    for subject_id, subject_rows in frame.groupby("subject_id").groups.items():
        resting = raw[
            (raw["subject_id"] == subject_id) & (raw["label"] == "baseline")
        ].sort_values("timestamp_ms").head(calibration_seconds)
        if len(resting) < calibration_seconds:
            raise ValueError(
                f"{subject_id} has only {len(resting)} resting samples; "
                f"{calibration_seconds} are required."
            )

        valid_hr = resting.loc[resting["bpm_valid"].astype(bool), "bpm"].dropna()
        if len(valid_hr) < int(0.8 * calibration_seconds):
            raise ValueError(
                f"{subject_id} calibration has only {len(valid_hr)} valid HR samples."
            )
        hr_baseline = float(valid_hr.mean())
        gsr_baseline = float(resting["gsr"].mean())
        temp_baseline = float(resting["temp_c"].mean())
        if abs(hr_baseline) < 1e-9 or abs(gsr_baseline) < 1e-9:
            raise ValueError(f"{subject_id} has a zero HR or GSR baseline.")

        rows = list(subject_rows)
        frame.loc[rows, list(HR_RELATIVE_FEATURES)] /= hr_baseline
        frame.loc[rows, list(GSR_RELATIVE_FEATURES)] /= gsr_baseline
        frame.loc[rows, "temp_mean"] -= temp_baseline

        calibration_end_ms = int(resting["timestamp_ms"].iloc[-1])
        covered = frame.loc[rows, "window_end_ms"] <= calibration_end_ms
        drop_indices.extend(frame.loc[rows].index[covered].tolist())

    frame = frame.drop(index=drop_indices).reset_index(drop=True)
    subject_count = frame["subject_id"].nunique()
    return _validate_and_build_dataset(
        frame,
        description=(
            f"WESAD personalized relative-baseline dataset ({subject_count} "
            f"subjects); {calibration_seconds} s resting calibration excluded; "
            "30 s windows at 5 s stride; relative HR/GSR and temperature delta"
        ),
    )


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
            "Feature parquet does not match the canonical 18-column schema. "
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
